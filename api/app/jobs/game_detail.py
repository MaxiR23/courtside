# api/app/jobs/game_detail.py
#
# Game detail job: builds and publishes one detail feed per game of the days
# shown, each at feeds/games/{id}.json. Cadences: a live game every 30 seconds;
# a final game at its final time and, after a failure, 2, 4 and 6 hours after
# it, never after a success; any other status every hour. Standings and league
# injuries are fetched once per run, and a team schedule at most once per run,
# only when a game is due. A failed build keeps that game's last valid feed and
# never blocks the other games. A feed is republished with no source call when
# its stars, highlights or highlights search URL change. The feeds of games
# no longer in the days shown are deleted. Final attempts are kept in memory:
# after a restart a final game is built once more.
#
# SEE: docs/adr/0019-game-detail-route-and-feed.md,
# docs/adr/0010-final-game-attempts.md, docs/api/game-detail.md

import datetime as dt
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx
from pydantic import ValidationError

from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GameStatus
from app.jobs.games import (
    LIVE_INTERVAL,
    STATS_ATTEMPT_DELAYS,
    HighlightsProvider,
    SearchUrlProvider,
    StarsProvider,
    final_winner,
    no_highlights,
    no_highlights_search_url,
    no_stars,
)
from app.settings import Settings
from app.sources import game_detail, league_injuries, standings, team_schedule
from app.sources.game_detail import GameDetailSections
from app.sources.http import SourceError
from app.sources.league_injuries import LeagueInjuries
from app.sources.scoreboard import ScoreboardGame
from app.sources.standings import LeagueStandings
from app.sources.team_schedule import TeamSchedule
from app.storage.feeds import (
    delete_game_detail,
    publish_game_detail,
    published_game_details,
)
from app.storage.state import StateStore

JOB = "game-detail"
FEED = "game-detail"
OTHER_INTERVAL = dt.timedelta(hours=1)
MAX_FINAL_ATTEMPTS = len(STATS_ATTEMPT_DELAYS)

GamesProvider = Callable[[], Sequence[ScoreboardGame] | None]
FetchSections = Callable[
    [httpx.AsyncClient, str, Settings], Awaitable[GameDetailSections]
]
FetchStandings = Callable[[httpx.AsyncClient, Settings], Awaitable[LeagueStandings]]
FetchInjuries = Callable[[httpx.AsyncClient, Settings], Awaitable[LeagueInjuries]]
FetchTeamSchedule = Callable[
    [httpx.AsyncClient, str, Settings], Awaitable[TeamSchedule]
]


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
                    "score": meeting.score,
                    "arena": arena,
                }
            )
        season_series = {
            "total_games": sections.season_series.total_games,
            "away_wins": sections.season_series.away_wins,
            "home_wins": sections.season_series.home_wins,
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


class GameDetailJob:
    name = JOB

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: httpx.AsyncClient,
        *,
        games: GamesProvider,
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
        self._games = games
        self._fetch_sections = fetch_sections
        self._fetch_standings = fetch_standings
        self._fetch_injuries = fetch_injuries
        self._fetch_team_schedule = fetch_team_schedule
        self._stars = stars
        self._highlights = highlights
        self._highlights_search_url = highlights_search_url
        self._attempted_at: dict[str, dt.datetime] = {}
        self._final_failures: dict[str, int] = {}
        self._final_built: set[str] = set()
        self._published: dict[str, GameDetailFeed] = {}
        self._inputs: dict[str, tuple[Any, Any, Any]] = {}

    def _due(self, game: ScoreboardGame, now: dt.datetime) -> bool:
        last = self._attempted_at.get(game.id)
        if game.status is GameStatus.LIVE:
            return last is None or now - last >= LIVE_INTERVAL
        if game.status is GameStatus.FINAL:
            if game.id in self._final_built:
                return False
            final_time = self._store.final_time(game.id)
            failed = self._final_failures.get(game.id, 0)
            return (
                final_time is not None
                and failed < MAX_FINAL_ATTEMPTS
                and now >= final_time + STATS_ATTEMPT_DELAYS[failed]
            )
        return last is None or now - last >= OTHER_INTERVAL

    def _forget(self, game_id: str) -> None:
        self._attempted_at.pop(game_id, None)
        self._final_failures.pop(game_id, None)
        self._final_built.discard(game_id)
        self._published.pop(game_id, None)
        self._inputs.pop(game_id, None)

    def _fail(self, game: ScoreboardGame) -> None:
        if game.status is GameStatus.FINAL:
            self._final_failures[game.id] = self._final_failures.get(game.id, 0) + 1

    async def run(self, now: dt.datetime) -> None:
        games = self._games()
        if games is None:
            return
        data_dir = self._settings.data_dir
        shown = {game.id for game in games}
        for game_id in published_game_details(data_dir) - shown:
            delete_game_detail(data_dir, game_id)
        for game_id in [i for i in self._published if i not in shown]:
            self._forget(game_id)

        due = [game for game in games if self._due(game, now)]
        attempted = {game.id for game in due}
        published = False
        first_failure: str | None = None
        if due:
            try:
                league_standings = await self._fetch_standings(
                    self._client, self._settings
                )
                league_injuries_ = await self._fetch_injuries(
                    self._client, self._settings
                )
            except SourceError as error:
                for game in due:
                    self._attempted_at[game.id] = now
                    self._fail(game)
                self._store.record_failure(JOB, now, str(error))
                due = []
            else:
                schedules: dict[str, TeamSchedule | SourceError] = {}

                async def schedule_of(code: str) -> TeamSchedule:
                    if code not in schedules:
                        try:
                            schedules[code] = await self._fetch_team_schedule(
                                self._client, code, self._settings
                            )
                        except SourceError as error:
                            schedules[code] = error
                    cached = schedules[code]
                    if isinstance(cached, SourceError):
                        raise cached
                    return cached

                for game in due:
                    self._attempted_at[game.id] = now
                    try:
                        sections = await self._fetch_sections(
                            self._client, game.id, self._settings
                        )
                        away_schedule = await schedule_of(game.away.code)
                        home_schedule = await schedule_of(game.home.code)
                        feed = build_game_detail_feed(
                            game,
                            sections,
                            league_standings,
                            league_injuries_,
                            away_schedule,
                            home_schedule,
                            stars=self._stars,
                            highlights=self._highlights,
                            highlights_search_url=self._highlights_search_url,
                        )
                        reason = (
                            None
                            if publish_game_detail(data_dir, feed)
                            else "feed not written"
                        )
                    except (SourceError, DetailBuildError) as error:
                        reason = (
                            error.reason
                            if isinstance(error, DetailBuildError)
                            else str(error)
                        )
                    if reason is None:
                        self._published[game.id] = feed
                        self._inputs[game.id] = (
                            self._stars(game),
                            self._highlights(game) or None,
                            self._highlights_search_url(game),
                        )
                        if game.status is GameStatus.FINAL:
                            self._final_built.add(game.id)
                        published = True
                    else:
                        self._fail(game)
                        if first_failure is None:
                            first_failure = f"game {game.id}: {reason}"

        for game in games:
            current = self._published.get(game.id)
            if game.id in attempted or current is None:
                continue
            stars = self._stars(game)
            highlights = self._highlights(game) or None
            search_url = self._highlights_search_url(game)
            if self._inputs[game.id] == (stars, highlights, search_url):
                continue
            updated = GameDetailFeed.model_validate(
                {
                    **current.model_dump(by_alias=False),
                    "stars": stars,
                    "highlights": highlights,
                    "highlights_search_url": search_url,
                }
            )
            if publish_game_detail(data_dir, updated):
                self._published[game.id] = updated
                self._inputs[game.id] = (stars, highlights, search_url)
                published = True

        if first_failure is not None:
            self._store.record_failure(JOB, now, first_failure)
        if published:
            self._store.record_success(JOB, now)
