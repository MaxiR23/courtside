# api/app/jobs/season_rosters.py
#
# The box-score roster of one team in one past season (ADR 0053): the players
# with a stat line in the team's final regular-season and playoff games, read
# from the box scores and from nothing else. Name and photo come from the newest
# game of the player; jersey and position from the newest game that has a value,
# else they are null.
#
# The season team and player feeds, the playoffs and the Finals use it in place
# of the season roster the provider sends, which holds only today's players of
# a franchise. A game is read once and kept in the state database (past_games),
# so the opponent's roster, and the same team of another feed, read no request;
# a stored past game detail is reused with no request too (its players carry no
# jersey or position). A stored body or past game detail of another or no
# build version is read again (ADR 0055). The dates of the final games are registered in the same
# table, which makes their past game detail reachable (ADR 0041, ADR 0053).
# At most MAX_GAME_READS summaries are read at once, and a failed read fails the
# roster.
#
# SEE: docs/api/team.md, docs/adr/0053-season-level-rules-for-past-seasons.md,
# api/app/jobs/season_team_feed.py

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.feeds.game_detail import PastGameDetailFeed, TeamBoxScore
from app.jobs import past_game_detail_feed
from app.jobs.on_demand import is_current_build, with_build_version
from app.jobs.team_feed import _played, eastern_date, roster_order
from app.settings import Settings
from app.sources import game_detail, team_schedule
from app.sources.game_detail import BoxScoreRosterEntry, GamePlayers
from app.sources.http import Freshness, SourceClient
from app.sources.team_schedule import ScheduledGame, SeasonSchedule
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

MAX_GAME_READS = 8

FetchSeasonSchedule = Callable[..., Awaitable[SeasonSchedule]]
FetchGamePlayers = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[GamePlayers]
]


def _stored_detail_players(settings: Settings, game_id: str) -> GamePlayers | None:
    body = read_by_id(settings.data_dir, past_game_detail_feed.KIND, game_id)
    if body is None:
        return None
    try:
        feed = PastGameDetailFeed.model_validate_json(body)
    except ValidationError:
        return None
    if feed.box_score is None or not is_current_build(feed):
        return None

    def players(side: TeamBoxScore) -> list[BoxScoreRosterEntry]:
        return [
            BoxScoreRosterEntry(
                player_id=player.player_id,
                display_name=player.display_name,
                jersey=None,
                position_abbreviation=None,
                headshot_url=str(player.photo_url) if player.photo_url else None,
            )
            for player in side.players
        ]

    teams: dict[str, list[BoxScoreRosterEntry]] = {}
    for opponent, side in (
        (feed.away, feed.box_score.away),
        (feed.home, feed.box_score.home),
    ):
        if not opponent.guest and opponent.code is not None:
            teams[opponent.code] = players(side)
    return GamePlayers(teams=teams)


class SeasonRosters:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        *,
        fetch_season_schedule: FetchSeasonSchedule = team_schedule.fetch_season_schedule,
        fetch_game_players: FetchGamePlayers = game_detail.fetch_past_game_players,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._fetch_season_schedule = fetch_season_schedule
        self._fetch_game_players = fetch_game_players
        self._reads = asyncio.Semaphore(MAX_GAME_READS)
        # Games being loaded, so that two rosters asking for one game share it.
        self._pending: dict[str, asyncio.Future[GamePlayers]] = {}

    async def final_games(self, code: str, season: int) -> list[ScheduledGame]:
        """The final games of the team's regular season and playoffs, oldest
        first; their dates are registered. A SourceError propagates."""
        regular, playoffs = await asyncio.gather(
            *(
                self._fetch_season_schedule(
                    self._client,
                    code,
                    season,
                    self._settings,
                    playoffs=is_playoffs,
                    by_id_first=True,
                )
                for is_playoffs in (False, True)
            )
        )
        games = sorted(
            (g for g in (*regular.games, *playoffs.games) if _played(g)),
            key=lambda game: game.start_time,
        )
        self._store.set_past_game_dates(
            {game.game_id: eastern_date(game.start_time) for game in games}
        )
        return games

    async def roster(self, code: str, season: int) -> list[BoxScoreRosterEntry]:
        games = await self.final_games(code, season)
        loaded = await asyncio.gather(
            *(
                self.game_players(game.game_id, eastern_date(game.start_time))
                for game in games
            )
        )
        found: dict[str, dict[str, Any]] = {}
        for game, players in reversed(list(zip(games, loaded, strict=True))):
            for entry in players.teams.get(code, []):
                known = found.get(entry.player_id)
                if known is None:
                    found[entry.player_id] = {
                        "name": entry.display_name,
                        "photo": entry.headshot_url,
                        "jersey": entry.jersey,
                        "position": entry.position_abbreviation,
                        "last_played": game.start_time,
                    }
                    continue
                if known["jersey"] is None:
                    known["jersey"] = entry.jersey
                if known["position"] is None:
                    known["position"] = entry.position_abbreviation
        roster = [
            BoxScoreRosterEntry(
                player_id=player_id,
                display_name=str(values["name"]),
                jersey=values["jersey"],
                position_abbreviation=values["position"],
                headshot_url=values["photo"],
                last_played=values["last_played"],
            )
            for player_id, values in found.items()
        ]
        return sorted(roster, key=lambda entry: roster_order(entry.jersey))

    async def game_players(self, game_id: str, game_date: dt.date) -> GamePlayers:
        """The league players of a final game: from the state database, else from
        a stored past game detail, else from one read of its summary."""
        pending = self._pending.get(game_id)
        if pending is None:
            pending = asyncio.ensure_future(self._load(game_id, game_date))
            self._pending[game_id] = pending
            pending.add_done_callback(lambda _: self._pending.pop(game_id, None))
        return await asyncio.shield(pending)

    async def _load(self, game_id: str, game_date: dt.date) -> GamePlayers:
        body = self._store.past_game_players(game_id)
        if body is not None:
            try:
                stored = GamePlayers.model_validate_json(body)
            except ValidationError:
                pass
            else:
                if is_current_build(stored):
                    return stored
        players = _stored_detail_players(self._settings, game_id)
        if players is None:
            async with self._reads:
                players = await self._fetch_game_players(
                    self._client,
                    game_id,
                    self._settings,
                    past_game_detail_feed.PAST_FRESH,
                )
        players = with_build_version(players)
        self._store.set_past_game_players(game_id, game_date, players.model_dump_json())
        return players
