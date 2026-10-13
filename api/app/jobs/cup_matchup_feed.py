# api/app/jobs/cup_matchup_feed.py
#
# Cup matchup feed builder and kind: one feed per bracket slot, the data of the
# matchup panel and the player card. The builder is a pure function from what
# the adapters returned to the feed; it reads no clock and no source. The slot
# is read from the stored Cup feed: its game is the header as the Cup feed
# stored it, and a side's team is the side's team, else its projected team, else
# none (a side with no team has only its label and its rule). Per team the path
# lists every Cup game of the team's schedule by start time, with the result and
# the scores once final; the injuries are the team's entries of the league
# injuries; the roster is ordered as the team feed orders it with its card
# fields and its per game averages rounded to one decimal. The starters are the
# rank 1 player of each of the five positions of the depth chart who is on the
# roster, and a stat leader is every player at the highest rounded average of
# the roster. A team with no averages or no chart marks no leader or no starter.
# CupMatchupFeeds is the feed kind of the on-demand cache: the ids are the 7
# slot ids, a feed is stored at feeds/cup-matchups/{id}.json only when requested
# and the Cup feed is built first when it is missing or stale. It expires 1 hour
# after a final game of either team or of its path that follows the build, when
# the Cup feed is rebuilt after it, and 7 days after the build (rule G). A
# failed Cup feed, roster, schedule or injuries read fails the build; a failed
# averages or depth chart read only removes the leaders or the starters. The
# feed is never deleted.
#
# SEE: docs/api/cup-matchup.md, docs/adr/0029-cup-matchup-feed.md,
# api/app/jobs/cup_feed.py

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.feeds.cup import BracketSlot, SlotId, SlotSide
from app.feeds.cup_matchup import CupMatchupFeed
from app.feeds.game_detail import GameResult
from app.feeds.games import GameStatus
from app.feeds.opponent import Opponent
from app.jobs import cup_feed
from app.jobs.cup_feed import CupFeeds, status_of
from app.jobs.games import GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    FetchInjuries,
    FetchRoster,
    TeamBuildError,
    eastern_date,
    feed_expired,
    roster_order,
    roster_player,
    season_label,
    team_injuries,
)
from app.settings import Settings
from app.sources import depth_chart, league_injuries, team_players, team_schedule
from app.sources.cup import cup_round
from app.sources.depth_chart import POSITIONS, DepthChart
from app.sources.http import SourceClient, SourceError
from app.sources.league_injuries import LeagueInjuries
from app.sources.team_players import PlayerAverages, Roster
from app.sources.team_schedule import SeasonSchedule
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "cup-matchups"
SLOT_IDS = frozenset(slot.value for slot in SlotId)
STATS = ("points", "rebounds", "assists")

FetchSeasonSchedule = Callable[..., Awaitable[SeasonSchedule]]
FetchAverages = Callable[
    [SourceClient, str, int, Settings], Awaitable[list[PlayerAverages]]
]
FetchDepthChart = Callable[[SourceClient, str, int, Settings], Awaitable[DepthChart]]


class MatchupBuildError(Exception):
    """The Cup matchup feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class MatchupSources:
    """What the matchup build reads. Never reaches a feed."""

    season: str
    slot: BracketSlot
    rosters: Mapping[str, Roster]
    schedules: Mapping[str, SeasonSchedule]
    injuries: LeagueInjuries
    averages: Mapping[str, Sequence[PlayerAverages] | None]
    charts: Mapping[str, DepthChart | None]


def side_team(side: SlotSide) -> tuple[Opponent | None, bool]:
    """The side's team and whether it is a projection: the team of the side,
    else its projected team, else none."""
    if side.team is not None:
        return side.team, False
    if side.projected is not None:
        return side.projected.team, True
    return None, False


def _code_of(team: Opponent) -> str:
    if team.guest or team.code is None:
        raise MatchupBuildError("a Cup team is outside the league")
    return team.code


def _path(schedule: SeasonSchedule) -> list[dict[str, Any]]:
    games = [
        (stage, game)
        for game in schedule.games
        if (stage := cup_round(game.note)) is not None
    ]
    games.sort(key=lambda pair: (pair[1].start_time, pair[1].game_id))
    path: list[dict[str, Any]] = []
    for stage, game in games:
        status = status_of(game)
        final = status is GameStatus.FINAL
        path.append(
            {
                "game_id": game.game_id,
                "stage": stage,
                "start_time": game.start_time,
                "opponent": game.opponent,
                "is_home": game.is_home,
                "status": status,
                "result": (GameResult.WIN if game.won else GameResult.LOSS)
                if final
                else None,
                "team_score": game.team_score if final else None,
                "opponent_score": game.opponent_score if final else None,
                "detail_available": False,
            }
        )
    return path


def _starters(chart: DepthChart | None, roster_ids: set[str]) -> set[str]:
    if chart is None:
        return set()
    first = {
        chart.positions[position][0]
        for position in POSITIONS
        if chart.positions.get(position)
    }
    return first & roster_ids


def _averages(
    found: Sequence[PlayerAverages] | None,
) -> dict[str, dict[str, float]]:
    return {
        player.player_id: {stat: round(getattr(player, stat), 1) for stat in STATS}
        for player in found or []
    }


def _team(code: str, sources: MatchupSources, today: dt.date) -> dict[str, Any]:
    roster = sources.rosters[code]
    entries = sorted(roster.entries, key=lambda entry: roster_order(entry.jersey))
    by_id = {entry.player_id: entry for entry in roster.entries}
    averages = _averages(sources.averages.get(code))
    on_roster = [values for player_id, values in averages.items() if player_id in by_id]
    best = (
        {stat: max(values[stat] for values in on_roster) for stat in STATS}
        if on_roster
        else {}
    )
    starters = _starters(sources.charts.get(code), set(by_id))
    players: list[dict[str, Any]] = []
    for entry in entries:
        mine = averages.get(entry.player_id)
        players.append(
            {
                **roster_player(entry, today, sources.injuries),
                "averages": mine,
                "starter": entry.player_id in starters,
                "leader": {
                    stat: mine is not None and mine[stat] == best.get(stat)
                    for stat in STATS
                },
            }
        )
    return {
        "path": _path(sources.schedules[code]),
        "injuries": team_injuries(code, sources.injuries, by_id),
        "roster": players,
    }


def build_matchup_feed(sources: MatchupSources, *, now: dt.datetime) -> CupMatchupFeed:
    """Build the matchup feed of one slot; raise MatchupBuildError when it is not
    valid."""
    slot = sources.slot
    today = eastern_date(now)
    sides: dict[str, dict[str, Any]] = {}
    try:
        for name, side in (("top", slot.top), ("bottom", slot.bottom)):
            team, projected = side_team(side)
            sides[name] = {
                "label": side.label,
                "rule": side.rule,
                "known": side.known,
                "projected": projected,
                "team": team,
                "details": None
                if team is None
                else _team(_code_of(team), sources, today),
            }
    except TeamBuildError as error:
        raise MatchupBuildError(error.reason) from None
    try:
        return CupMatchupFeed.model_validate(
            {
                "season": sources.season,
                "id": slot.id,
                "round": slot.round,
                "conference": slot.conference,
                "game": slot.game,
                **sides,
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise MatchupBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class CupMatchupFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        stars: StarsJob,
        cups: CupFeeds,
        *,
        fetch_roster: FetchRoster = team_players.fetch_roster,
        fetch_season_schedule: FetchSeasonSchedule = (
            team_schedule.fetch_season_schedule
        ),
        fetch_league_injuries: FetchInjuries = league_injuries.fetch_league_injuries,
        fetch_season_averages: FetchAverages = team_players.fetch_season_averages,
        fetch_depth_chart: FetchDepthChart = depth_chart.fetch_depth_chart,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._games = games
        self._stars = stars
        self._cups = cups
        self._fetch_roster = fetch_roster
        self._fetch_season_schedule = fetch_season_schedule
        self._fetch_league_injuries = fetch_league_injuries
        self._fetch_season_averages = fetch_season_averages
        self._fetch_depth_chart = fetch_depth_chart
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if feed_id not in SLOT_IDS:
            return IdStatus.UNKNOWN
        if (
            self._stars.current_season() is None
            and read_by_id(self._settings.data_dir, KIND, feed_id) is None
        ):
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    def depends_on(self, feed_id: str) -> tuple[str, str] | None:
        return (cup_feed.KIND, cup_feed.FEED_ID)

    async def _averages(
        self, roster: Roster, season: int
    ) -> list[PlayerAverages] | None:
        try:
            return await self._fetch_season_averages(
                self._client, roster.team_id, season, self._settings
            )
        except SourceError:
            return None

    async def _chart(self, code: str, season: int) -> DepthChart | None:
        try:
            return await self._fetch_depth_chart(
                self._client, code, season, self._settings
            )
        except SourceError:
            return None

    async def build(self, feed_id: str) -> CupMatchupFeed:
        season = self._stars.current_season()
        if season is None:
            raise MatchupBuildError("season not known yet")
        cup = self._cups.stored()
        if cup is None:
            raise MatchupBuildError("Cup feed is not stored")
        if cup.season != season_label(season):
            raise MatchupBuildError("Cup feed is of another season")
        slot = next((s for s in cup.bracket if s.id.value == feed_id), None)
        if slot is None:
            raise MatchupBuildError(f"slot {feed_id} is not in the Cup feed")
        teams = [team for team, _ in (side_team(slot.top), side_team(slot.bottom))]
        codes = sorted({_code_of(team) for team in teams if team is not None})
        client, settings = self._client, self._settings
        rosters: dict[str, Roster] = {}
        schedules: dict[str, SeasonSchedule] = {}
        averages: dict[str, Sequence[PlayerAverages] | None] = {}
        charts: dict[str, DepthChart | None] = {}
        injuries = LeagueInjuries(teams={})
        if codes:
            injuries = await self._fetch_league_injuries(client, settings)
            found_rosters, found_schedules = await asyncio.gather(
                asyncio.gather(
                    *(self._fetch_roster(client, code, settings) for code in codes)
                ),
                asyncio.gather(
                    *(
                        self._fetch_season_schedule(
                            client, code, season, settings, playoffs=False
                        )
                        for code in codes
                    )
                ),
            )
            rosters = dict(zip(codes, found_rosters, strict=True))
            schedules = dict(zip(codes, found_schedules, strict=True))
            found_averages, found_charts = await asyncio.gather(
                asyncio.gather(*(self._averages(rosters[c], season) for c in codes)),
                asyncio.gather(*(self._chart(code, season) for code in codes)),
            )
            averages = dict(zip(codes, found_averages, strict=True))
            charts = dict(zip(codes, found_charts, strict=True))
        return build_matchup_feed(
            MatchupSources(
                season=cup.season,
                slot=slot,
                rosters=rosters,
                schedules=schedules,
                injuries=injuries,
                averages=averages,
                charts=charts,
            ),
            now=self._client.clock(),
        )

    def final_times(self, feed: CupMatchupFeed) -> list[dt.datetime]:
        """The final times of the games that can expire a feed: the final games of
        either team and the games of their paths."""
        codes = {
            side.team.code for side in (feed.top, feed.bottom) if side.team is not None
        }
        ids = {
            game.id
            for game in self._games.final_games()
            if game.away.code in codes or game.home.code in codes
        }
        for side in (feed.top, feed.bottom):
            if side.details is not None:
                ids |= {game.game_id for game in side.details.path}
        times = (self._store.final_time(game_id) for game_id in sorted(ids))
        return [time for time in times if time is not None]

    def is_fresh(
        self, feed: CupMatchupFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        cup = self._store.feed_build(cup_feed.KIND, cup_feed.FEED_ID)
        if cup is not None and cup.last_build is not None and cup.last_build > built_at:
            return False
        return not feed_expired(built_at, now, self.final_times(feed))

    def serve_with(self, feed_id: str, feed: CupMatchupFeed) -> CupMatchupFeed:
        ids = {game.id for game in self._games.loaded_games()}
        data = feed.model_dump(by_alias=False)
        if data["game"] is not None:
            data["game"]["detail_available"] = data["game"]["id"] in ids
        for name in ("top", "bottom"):
            details = data[name]["details"]
            if details is not None:
                for game in details["path"]:
                    game["detail_available"] = game["game_id"] in ids
        return CupMatchupFeed.model_validate(data)

    def keep(self, feed_id: str) -> bool:
        return feed_id in SLOT_IDS

    def kind(self) -> FeedKind[CupMatchupFeed]:
        return FeedKind(
            KIND,
            CupMatchupFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            depends_on=self.depends_on,
        )
