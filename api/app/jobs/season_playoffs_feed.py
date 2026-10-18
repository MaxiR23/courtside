# api/app/jobs/season_playoffs_feed.py
#
# Playoffs feed of a past season (ADR 0046): the playoffs feed's shape, built by
# the playoffs feed builder from the sources of that season, under a declared
# read budget of READ_BUDGET source reads (ADR 0058). The reads are the season
# standings, the postseason schedule of each team that can have played a series
# (the first 8 of each conference, 10 from 2021), the play-in window and its
# scoreboard days (from 2021), the postseason leaders, the season awards, the
# postseason record of the two finalists and the game detail of the Finals games.
# It reads no postseason window, no bracket scoreboard day, no team info, no
# roster and no game detail outside the Finals. The names of leaders and award
# winners come from the box scores of the Finals games and from the stored past
# game players of the games it read; a player no read names is left out, and a
# block left with no player is null. The colors come from the team info the
# source cache already holds, else they are null. The league sides are named from
# the standings payload (payload_names), with the season code and the historical
# flag (ADR 0054), with no season team read. A season before 2021 has no play-in,
# so that window is not read and the play-in block is null. Leaders, awards and
# the finalists' records are null only when the source answers 404; any other
# failed read fails the build, because the feed is kept for good. A read past the
# budget or a rate limit (429, 503) fails the build before it stores anything. A
# past playoffs feed is stored only when it builds as complete: a postseason that
# is not complete, or whose rounds cannot be derived, fails the build, logs the
# reason and stores nothing. Game detail is never available.
#
# SeasonPlayoffsFeeds is the feed kind of the on-demand cache: the id is the
# season's end year, the feed is stored at feeds/season-playoffs/{season}.json
# only when requested. A season is valid from 1994 to the season before the
# current one (past_season_status). The current season is resolved before the
# cache (target) to the current playoffs feed (ADR 0042). A feed is built once
# and kept (rule G): it is never deleted, and rebuilt only when its build version
# is not the current one (ADR 0053).
#
# SEE: docs/api/playoffs.md, docs/adr/0046-season-playoffs-feeds.md,
# docs/adr/0058-bounded-past-competition-reads.md, api/app/jobs/playoffs_feed.py

import asyncio
import datetime as dt
import functools
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from typing import Any

from pydantic import ValidationError

from app.feeds.game_detail import Conference
from app.feeds.games import GameStatus
from app.feeds.playoffs import PlayoffsFeed, PlayoffsState
from app.jobs import past_game_detail_feed, playoffs_feed
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.playoffs_feed import (
    CODES,
    FetchAwards,
    FetchLeaders,
    FetchRecord,
    FetchSeasonType,
    PlayoffsBuildError,
    PlayoffsSources,
    _unique_games,
    build_playoffs_feed,
    postseason_days,
)
from app.jobs.season_standings_feed import past_season_status
from app.jobs.standings_feed import seed_of
from app.jobs.stars import StarsJob
from app.jobs.team_feed import eastern_date
from app.jobs.team_names import TeamNamesFeeds, named_sides, payload_names
from app.settings import Settings
from app.sources import (
    division_standings,
    game_detail,
    postseason_leaders,
    postseason_scoreboard,
    season_awards,
    season_types,
    team_info,
    team_postseason,
)
from app.sources.division_standings import DivisionEntry, DivisionStandings
from app.sources.game_detail import BoxScoreRosterEntry, GamePlayers
from app.sources.http import (
    Freshness,
    ReadBudget,
    SourceClient,
    SourceError,
    within_budget,
)
from app.sources.postseason_scoreboard import PostseasonGame
from app.sources.season_types import PLAY_IN
from app.sources.team_players import RosterEntry
from app.sources.teams import SeasonTeamName
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

KIND = "season-playoffs"
FIRST_PLAY_IN_SEASON = 2021
NOT_FOUND = 404
FINALS_GAMES = 7
# The most source reads one build sends (ADR 0058): 1 standings + 20 team
# schedules + 1 play-in window + 5 play-in days (the window's Eastern dates, its end
# included) + 1 leaders + 26 awards (the index
# and 25 documents) + 2 finalist records + 7 Finals game details.
READ_BUDGET = 63

FetchSeasonGames = Callable[..., Awaitable[list[PostseasonGame]]]
FetchSchedule = Callable[..., Awaitable[list[PostseasonGame]]]
FetchGamePlayers = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[GamePlayers]
]


async def none_on_404[T](read: Awaitable[T]) -> T | None:
    """The result of a read, or none when the source answers 404; any other
    failure is raised."""
    try:
        return await read
    except SourceError as error:
        if error.status_code == NOT_FOUND:
            return None
        raise


def schedule_teams(standings: DivisionStandings, year: int) -> list[str]:
    """The teams whose postseason schedule is read: per conference the seeded
    teams in seed order, then the unseeded ones by best record (ties by the
    conference order), keeping the first 8 (10 from 2021)."""
    limit = 10 if year >= FIRST_PLAY_IN_SEASON else 8

    def key(entry: DivisionEntry) -> tuple[bool, int, int, int]:
        return (
            seed_of(entry) is None,
            seed_of(entry) or 0,
            -(entry.wins - entry.losses),
            entry.conference_order,
        )

    codes: list[str] = []
    for conference in Conference:
        entries = sorted(
            (e for e in standings.teams.values() if e.conference is conference),
            key=key,
        )
        codes.extend(entry.code for entry in entries[:limit])
    return codes


def finals_games(
    games: Sequence[PostseasonGame], conferences: dict[str, Conference]
) -> list[PostseasonGame]:
    """The unique postseason games of the only pair of teams from different
    conferences, in start order; any other count of such pairs fails."""
    by_pair: dict[frozenset[str], list[PostseasonGame]] = {}
    for game in _unique_games(games):
        if game.season_type != season_types.POSTSEASON:
            continue
        home, away = game.game.home.code, game.game.away.code
        if home is None or away is None:
            continue
        by_pair.setdefault(frozenset({home, away}), []).append(game)
    across = [
        found
        for pair, found in by_pair.items()
        if len({conferences.get(code) for code in pair}) > 1
    ]
    if len(across) != 1:
        raise PlayoffsBuildError(
            f"the Finals is not the only series across the conferences: {len(across)}"
        )
    return across[0]


def series_winner(games: Sequence[PostseasonGame]) -> str | None:
    """The team with more wins in the series object of the latest final game
    whose series is completed; none when no series is completed or it is tied."""
    for game in sorted(
        games, key=lambda g: (g.game.start_time, g.game.id), reverse=True
    ):
        series = game.series
        if (
            game.game.status is GameStatus.FINAL
            and series is not None
            and series.completed
        ):
            ranked = sorted(series.wins.items(), key=lambda item: -item[1])
            if len(ranked) < 2 or ranked[0][1] == ranked[1][1]:
                return None
            return ranked[0][0]
    return None


def box_players(
    found: Iterable[tuple[GamePlayers, dt.datetime]],
) -> dict[str, tuple[str, BoxScoreRosterEntry]]:
    """The team and entry of each player of the games given, each game with its
    start time. A player traded during the season is on two teams: the team of
    his newest game wins (ADR 0053)."""
    players: dict[str, tuple[str, BoxScoreRosterEntry]] = {}
    for game_players, started in found:
        for code, entries in game_players.teams.items():
            for entry in entries:
                known = players.get(entry.player_id)
                if known is None or _newer(entry, known[1], started):
                    players[entry.player_id] = (
                        code,
                        entry.model_copy(update={"last_played": started}),
                    )
    return players


class SeasonPlayoffsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        names: TeamNamesFeeds,
        *,
        fetch_season_type: FetchSeasonType = season_types.fetch_season_type,
        fetch_postseason_games: FetchSeasonGames = (
            postseason_scoreboard.fetch_postseason_games
        ),
        fetch_postseason_schedule: FetchSchedule = (
            postseason_scoreboard.fetch_postseason_schedule
        ),
        fetch_division_standings: Any = division_standings.fetch_division_standings,
        fetch_postseason_leaders: FetchLeaders = (
            postseason_leaders.fetch_postseason_leaders
        ),
        fetch_season_awards: FetchAwards = season_awards.fetch_season_awards,
        fetch_team_postseason_record: FetchRecord = (
            team_postseason.fetch_team_postseason_record
        ),
        fetch_game_players: FetchGamePlayers = game_detail.fetch_past_game_players,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._names = names
        self._fetch_season_type = fetch_season_type
        self._fetch_postseason_games = fetch_postseason_games
        self._fetch_postseason_schedule = fetch_postseason_schedule
        self._fetch_division_standings = fetch_division_standings
        self._fetch_postseason_leaders = fetch_postseason_leaders
        self._fetch_season_awards = fetch_season_awards
        self._fetch_team_postseason_record = fetch_team_postseason_record
        self._fetch_game_players = fetch_game_players
        cache.register(self.kind())

    def check(self, season: str) -> IdStatus:
        return past_season_status(season, self._stars.current_season())

    def target(self, season: str) -> tuple[str, str]:
        """The (kind, id) a route season maps to: the current season is the
        current playoffs feed."""
        current = self._stars.current_season()
        if current is not None and season == str(current):
            return playoffs_feed.KIND, playoffs_feed.FEED_ID
        return KIND, season

    def _stored_players(
        self, games: Sequence[PostseasonGame]
    ) -> list[tuple[GamePlayers, dt.datetime]]:
        """The stored past game players of the games read; a body that is invalid
        or of another build is left out. Reads nothing from the source."""
        found: list[tuple[GamePlayers, dt.datetime]] = []
        for game in games:
            body = self._store.past_game_players(game.game.id)
            if body is None:
                continue
            try:
                stored = GamePlayers.model_validate_json(body)
            except ValidationError:
                continue
            if is_current_build(stored):
                found.append((stored, game.game.start_time))
        return found

    async def _read(self, season: str) -> tuple[PlayoffsSources, DivisionStandings]:
        year = int(season)
        client, settings = self._client, self._settings
        play_in_read = (
            self._fetch_season_type(client, year, PLAY_IN, settings)
            if year >= FIRST_PLAY_IN_SEASON
            else _none()
        )
        play_in, standings, leaders, awards = await asyncio.gather(
            play_in_read,
            self._fetch_division_standings(client, settings, season=year),
            none_on_404(self._fetch_postseason_leaders(client, year, settings)),
            none_on_404(self._fetch_season_awards(client, year, settings)),
        )
        read_day = functools.partial(self._fetch_postseason_games, by_id_first=True)
        schedules, days = await asyncio.gather(
            asyncio.gather(
                *(
                    self._fetch_postseason_schedule(client, code, year, settings)
                    for code in schedule_teams(standings, year)
                )
            ),
            asyncio.gather(
                *(
                    read_day(client, day, settings)
                    for day in postseason_days(play_in, None)
                )
            ),
        )
        games = [game for group in (*schedules, *days) for game in group]
        conferences = {code: e.conference for code, e in standings.teams.items()}
        finals = finals_games(games, conferences)
        finalists = sorted(
            {finals[0].game.home.code or "", finals[0].game.away.code or ""}
        )
        records, finals_players = await asyncio.gather(
            asyncio.gather(
                *(
                    none_on_404(
                        self._fetch_team_postseason_record(client, code, year, settings)
                    )
                    for code in finalists
                )
            ),
            asyncio.gather(
                *(
                    self._fetch_game_players(
                        client, game.game.id, settings, past_game_detail_feed.PAST_FRESH
                    )
                    for game in finals
                    if game.game.status is GameStatus.FINAL
                )
            ),
        )
        read = [game for game in finals if game.game.status is GameStatus.FINAL]
        players = box_players(
            [
                *self._stored_players(_unique_games(games)),
                *(
                    (found, game.game.start_time)
                    for found, game in zip(finals_players, read, strict=True)
                ),
            ]
        )
        by_code = dict(zip(finalists, records, strict=True))
        colors = {
            code: team_info.cached_team_info(client, code, settings) for code in CODES
        }
        sources = PlayoffsSources(
            season=year,
            today=eastern_date(client.clock()),
            play_in=play_in,
            postseason=None,
            standings=standings,
            colors=colors,
            games=games,
            players=dict[str, tuple[str, RosterEntry | BoxScoreRosterEntry]](players),
            leaders=leaders,
            awards=awards,
            champion_record=by_code.get(series_winner(finals) or ""),
            past=True,
        )
        return sources, standings

    async def _build(self, season: str) -> PlayoffsFeed:
        try:
            sources, standings = await self._read(season)
            feed = build_playoffs_feed(sources)
            if feed.state is not PlayoffsState.COMPLETE:
                raise PlayoffsBuildError(f"the {season} postseason is not complete")
        except PlayoffsBuildError as error:
            logger.warning("season playoffs: %s not built: %s", season, error.reason)
            raise
        identities = {
            code: SeasonTeamName(
                abbreviation=entry.abbreviation,
                name=entry.name,
                location=entry.location,
            )
            for code, entry in standings.teams.items()
            if entry.abbreviation
        }
        runs = {code: found for code in CODES if (found := self._names.stored(code))}
        return with_build_version(named_sides(feed, payload_names(identities, runs)))

    async def build(self, season: str) -> PlayoffsFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET),
            f"season playoffs: {season}",
            lambda: self._build(season),
        )

    def stored(self, season: str) -> PlayoffsFeed | None:
        """The stored playoffs feed of a season, or none when missing or invalid."""
        body = read_by_id(self._settings.data_dir, KIND, season)
        if body is None:
            return None
        try:
            return PlayoffsFeed.model_validate_json(body)
        except ValidationError:
            return None

    def is_fresh(
        self, feed: PlayoffsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[PlayoffsFeed]:
        return FeedKind(
            KIND,
            PlayoffsFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )


def _newer(
    entry: BoxScoreRosterEntry, known: BoxScoreRosterEntry, started: dt.datetime
) -> bool:
    return known.last_played is None or started > known.last_played


async def _none() -> None:
    return None


def stored_player_ids(body: bytes) -> set[str]:
    """The player ids a stored past playoffs feed names in its leaders and awards
    (the reader the core past player ids index is given, ADR 0059)."""
    feed = PlayoffsFeed.model_validate_json(body)
    ids = {leader.player_id for group in feed.leaders or [] for leader in group.leaders}
    ids |= {winner.player_id for award in feed.awards or [] for winner in award.winners}
    return ids
