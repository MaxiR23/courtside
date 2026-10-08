# api/app/jobs/game_detail_feed.py
#
# Game detail feed kind of the on-demand cache: builds one detail feed per game
# of the days shown when it is requested, stored at feeds/games/{id}.json. A
# pre-game feed expires 12, 6 or 3 hours after its build by the time left to
# tip-off (rule G); a live feed is fresh until the games job refreshes its day
# again, and a request that finds it stale waits for the rebuild, so a score is
# never older than 30 seconds; a final feed is never built by a request: the
# games job starts its build at the final time and, after a failure, 2, 4 and 6
# hours after it (ADR 0010), through after_games_run. A stored feed has no
# stars, highlights or highlights search URL: serve_with adds them when it is
# served. After a day change whose new-day fetch fails, the games already loaded
# keep being served and an id not loaded is not ready until every day shown is
# loaded. The feeds of games no longer in the days shown are deleted by the
# cache's cleanup, run when the set of games shown changes.
#
# SEE: docs/source-rules.md, docs/adr/0020-source-rules.md,
# docs/adr/0010-final-game-attempts.md, docs/api/game-detail.md

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GameStatus
from app.jobs.games import (
    LIVE_INTERVAL,
    STATS_ATTEMPT_DELAYS,
    GamesJob,
    HighlightsProvider,
    SearchUrlProvider,
    StarsProvider,
    final_winner,
    no_highlights,
    no_highlights_search_url,
    no_stars,
)
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.settings import Settings
from app.sources import game_detail, league_injuries, standings, team_schedule
from app.sources.game_detail import GameDetailSections
from app.sources.http import Freshness, SourceClient
from app.sources.league_injuries import LeagueInjuries
from app.sources.scoreboard import ScoreboardGame
from app.sources.standings import LeagueStandings
from app.sources.team_schedule import TeamSchedule
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "games"
PRE_GAME_FRESH = dt.timedelta(hours=1)

FetchSections = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[GameDetailSections]
]
FetchStandings = Callable[[SourceClient, Settings], Awaitable[LeagueStandings]]
FetchInjuries = Callable[[SourceClient, Settings], Awaitable[LeagueInjuries]]
FetchTeamSchedule = Callable[[SourceClient, str, Settings], Awaitable[TeamSchedule]]


class DetailBuildError(Exception):
    """The game detail feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_game_detail_feed(
    game: ScoreboardGame,
    sections: GameDetailSections,
    standings: LeagueStandings,
    injuries: LeagueInjuries,
    away_schedule: TeamSchedule,
    home_schedule: TeamSchedule,
    *,
    stars: StarsProvider,
    highlights: HighlightsProvider,
    highlights_search_url: SearchUrlProvider,
) -> GameDetailFeed:
    away, home = game.away.code, game.home.code
    for code in (away, home):
        if code not in standings.teams:
            raise DetailBuildError(f"team {code} has no standing")

    season_series: dict[str, Any] | None = None
    if sections.season_series is not None:
        meetings: list[dict[str, Any]] = []
        for meeting in sections.season_series.games:
            arena = away_schedule.arenas.get(meeting.game_id) or (
                home_schedule.arenas.get(meeting.game_id)
            )
            if arena is None and meeting.game_id == game.id:
                arena = game.venue
            if arena is None:
                raise DetailBuildError(f"series game {meeting.game_id} has no arena")
            meetings.append(
                {
                    "date": meeting.date,
                    "away": meeting.away,
                    "home": meeting.home,
                    "is_current": meeting.is_current,
                    "score": meeting.score,
                    "winner": meeting.winner,
                    "arena": arena,
                }
            )
        season_series = {
            "total_games": sections.season_series.total_games,
            "away_wins": sections.season_series.away_wins,
            "home_wins": sections.season_series.home_wins,
            "leader": sections.season_series.leader,
            "games": meetings,
        }

    data: dict[str, Any] = {
        "id": game.id,
        "status": game.status,
        "start_time": game.start_time,
        "broadcast": game.broadcast,
        "period": game.period,
        "clock": game.clock,
        "line_score": game.line_score,
        "score": game.score,
        "winner": final_winner(game),
        "venue": sections.venue,
        "team_stats": sections.team_stats,
        "box_score": sections.box_score,
        "win_probability": sections.win_probability,
        "win_probability_leader": sections.win_probability_leader,
        "win_probability_periods": sections.win_probability_periods,
        "videos": sections.videos,
        "away": {
            **game.away.model_dump(by_alias=False),
            "record": standings.teams[away].record,
        },
        "home": {
            **game.home.model_dump(by_alias=False),
            "record": standings.teams[home].record,
        },
        "standings": {"away": standings.teams[away], "home": standings.teams[home]},
        "injuries": {
            "away": injuries.teams.get(away, []),
            "home": injuries.teams.get(home, []),
        },
        "last_games": {
            "away": away_schedule.last_games,
            "home": home_schedule.last_games,
        },
        "season_series": season_series,
        "stars": stars(game),
        "highlights": highlights(game) or None,
        "highlights_search_url": highlights_search_url(game),
    }
    try:
        return GameDetailFeed.model_validate(data)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise DetailBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


def pre_game_expiry(start_time: dt.datetime, built_at: dt.datetime) -> dt.timedelta:
    """How long after its build a pre-game detail expires (rule G)."""
    away = start_time - built_at
    if away > dt.timedelta(hours=48):
        return dt.timedelta(hours=12)
    if away >= dt.timedelta(hours=12):
        return dt.timedelta(hours=6)
    return dt.timedelta(hours=3)


def final_slot(final_time: dt.datetime, now: dt.datetime) -> dt.datetime | None:
    """The latest final attempt time that has passed, or None before the final time."""
    passed = [
        final_time + delay
        for delay in STATS_ATTEMPT_DELAYS
        if final_time + delay <= now
    ]
    return max(passed) if passed else None


class GameDetailFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        *,
        fetch_sections: FetchSections = game_detail.fetch_game_detail_sections,
        fetch_standings: FetchStandings = standings.fetch_standings,
        fetch_injuries: FetchInjuries = league_injuries.fetch_league_injuries,
        fetch_team_schedule: FetchTeamSchedule = team_schedule.fetch_team_schedule,
        stars: StarsProvider = no_stars,
        highlights: HighlightsProvider = no_highlights,
        highlights_search_url: SearchUrlProvider = no_highlights_search_url,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._cache = cache
        self._games = games
        self._fetch_sections = fetch_sections
        self._fetch_standings = fetch_standings
        self._fetch_injuries = fetch_injuries
        self._fetch_team_schedule = fetch_team_schedule
        self._stars = stars
        self._highlights = highlights
        self._highlights_search_url = highlights_search_url
        self._cleaned: frozenset[str] | None = None
        self._final_stored: set[str] = set()
        cache.register(self.kind())

    def _game(self, game_id: str) -> ScoreboardGame | None:
        return self._games.loaded_game(game_id)

    def check(self, game_id: str) -> IdStatus:
        game = self._game(game_id)
        if game is None:
            if self._games.shown_games() is None:
                return IdStatus.NOT_READY
            return IdStatus.UNKNOWN
        if (
            game.status is GameStatus.FINAL
            and read_by_id(self._settings.data_dir, KIND, game_id) is None
        ):
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    async def build(self, game_id: str) -> GameDetailFeed:
        game = self._game(game_id)
        if game is None:
            raise DetailBuildError(f"game {game_id} is not shown")
        freshness: Freshness
        if game.status is GameStatus.LIVE:
            freshness = LIVE_INTERVAL
        elif game.status is GameStatus.FINAL:
            final_time = self._store.final_time(game_id)
            slot = (
                final_slot(final_time, self._client.clock())
                if final_time is not None
                else None
            )
            if slot is None:
                raise DetailBuildError(f"game {game_id} has no final attempt due")
            freshness = slot
        else:
            freshness = PRE_GAME_FRESH
        sections = await self._fetch_sections(
            self._client, game_id, self._settings, freshness
        )
        league_standings = await self._fetch_standings(self._client, self._settings)
        injuries = await self._fetch_injuries(self._client, self._settings)
        away_schedule = await self._fetch_team_schedule(
            self._client, game.away.code, self._settings
        )
        home_schedule = await self._fetch_team_schedule(
            self._client, game.home.code, self._settings
        )
        return build_game_detail_feed(
            game,
            sections,
            league_standings,
            injuries,
            away_schedule,
            home_schedule,
            stars=no_stars,
            highlights=no_highlights,
            highlights_search_url=no_highlights_search_url,
        )

    def is_fresh(
        self, feed: GameDetailFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        game = self._game(feed.id)
        if game is None or game.status is GameStatus.FINAL:
            return True
        if feed.status != game.status:
            return False
        if game.status is GameStatus.LIVE:
            refreshed = self._games.refreshed_at(game.id)
            return refreshed is None or built_at >= refreshed
        return now - built_at < pre_game_expiry(feed.start_time, built_at)

    def serve_with(self, game_id: str, feed: GameDetailFeed) -> GameDetailFeed:
        game = self._game(game_id)
        if game is None:
            return feed
        return GameDetailFeed.model_validate(
            {
                **feed.model_dump(by_alias=False),
                "stars": self._stars(game),
                "highlights": self._highlights(game) or None,
                "highlights_search_url": self._highlights_search_url(game),
            }
        )

    def keep(self, game_id: str) -> bool:
        return self._games.shown_games() is None or self._game(game_id) is not None

    def wait_when_stale(self, game_id: str) -> bool:
        game = self._game(game_id)
        return game is not None and game.status is GameStatus.LIVE

    def kind(self) -> FeedKind[GameDetailFeed]:
        return FeedKind(
            KIND,
            GameDetailFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            wait_when_stale=self.wait_when_stale,
        )

    def after_games_run(self) -> None:
        """The games job's after_run hook: the cleanup and the due final builds."""
        shown = self._games.shown_games()
        if shown is None:
            return
        ids = frozenset(game.id for game in shown)
        if ids != self._cleaned:
            self._cache.cleanup()
            self._cleaned = ids
        self._final_stored &= ids
        now = self._client.clock()
        for game in shown:
            if game.status is not GameStatus.FINAL or game.id in self._final_stored:
                continue
            body = read_by_id(self._settings.data_dir, KIND, game.id)
            if body is not None:
                try:
                    stored = GameDetailFeed.model_validate_json(body)
                except ValidationError:
                    stored = None
                if stored is not None and stored.status is GameStatus.FINAL:
                    self._final_stored.add(game.id)
                    continue
            final_time = self._store.final_time(game.id)
            if final_time is None:
                continue
            slot = final_slot(final_time, now)
            if slot is None:
                continue
            state = self._store.feed_build(KIND, game.id)
            if state is not None and (
                state.last_failure is not None and state.last_failure >= slot
            ):
                continue
            self._cache.refresh(KIND, game.id)
