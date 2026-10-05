# api/app/jobs/games.py
#
# Games job: fetches the days shown on the cadences of ADR 0007 and
# publishes the games feed. Stars, highlights and the highlights search URL
# are inputs, supplied by other jobs.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/api/games.md

import datetime as dt
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from app.feeds.games import GamesFeed, GameStatus, Highlight, Stars
from app.settings import Settings
from app.sources import game_detail, scoreboard
from app.sources.game_detail import GameDetail
from app.sources.http import SourceError
from app.sources.scoreboard import ScoreboardGame
from app.storage.feeds import publish_feed
from app.storage.state import StateStore

JOB = "games"
FEED = "games"
EASTERN = ZoneInfo("America/New_York")
DAYS_AROUND = 3
LIVE_INTERVAL = dt.timedelta(seconds=30)
START_CHECK_INTERVAL = dt.timedelta(minutes=1)
FINAL_DETAIL_RETRY = dt.timedelta(minutes=5)

StarsProvider = Callable[[ScoreboardGame], Stars | None]
SearchUrlProvider = Callable[[ScoreboardGame], str | None]
HighlightsProvider = Callable[[ScoreboardGame], list[Highlight]]
FetchGames = Callable[
    [httpx.AsyncClient, dt.date, Settings], Awaitable[list[ScoreboardGame]]
]
FetchGameDetail = Callable[[httpx.AsyncClient, str, Settings], Awaitable[GameDetail]]

_NOT_STARTED = (GameStatus.SCHEDULED, GameStatus.DELAYED)
_UNFINISHED = (GameStatus.SCHEDULED, GameStatus.LIVE, GameStatus.DELAYED)


def no_stars(game: ScoreboardGame) -> Stars | None:
    """Default when no stars provider is given: every game then lacks its stars."""
    return None


def no_highlights_search_url(game: ScoreboardGame) -> str | None:
    """Default when no search URL provider is given: every final game then lacks it."""
    return None


def no_highlights(game: ScoreboardGame) -> list[Highlight]:
    """Default when no highlights provider is given."""
    return []


def eastern_date(now: dt.datetime) -> dt.date:
    if now.utcoffset() is None:
        raise ValueError("time must be timezone aware")
    return now.astimezone(EASTERN).date()


def final_winner(game: ScoreboardGame) -> str | None:
    """The code of the team with more points in a final game; None on a tie or before the final."""
    if game.status is not GameStatus.FINAL or game.score is None:
        return None
    if game.score.home > game.score.away:
        return game.home.code
    if game.score.away > game.score.home:
        return game.away.code
    return None


def days_shown(today: dt.date) -> list[dt.date]:
    return [
        today + dt.timedelta(days=offset)
        for offset in range(-DAYS_AROUND, DAYS_AROUND + 1)
    ]


class FeedBuildError(Exception):
    """The games feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_games_feed(
    generated_at: dt.datetime,
    days: Sequence[tuple[dt.date, Sequence[ScoreboardGame]]],
    details: Mapping[str, GameDetail],
    stars: StarsProvider,
    highlights_search_url: SearchUrlProvider,
    highlights: HighlightsProvider = no_highlights,
) -> GamesFeed:
    built_days: list[dict[str, Any]] = []
    for day, games in days:
        built_games: list[dict[str, Any]] = []
        for game in games:
            data = game.model_dump(by_alias=False)
            data["stars"] = stars(game)
            data["highlights_search_url"] = highlights_search_url(game)
            data["highlights"] = highlights(game)
            data["winner"] = final_winner(game)
            detail = details.get(game.id)
            if detail is not None:
                data["leaders"] = detail.leaders
                data["team_stats"] = detail.team_stats
            built_games.append(data)
        built_days.append({"date": day, "games": built_games})
    try:
        return GamesFeed.model_validate(
            {"generated_at": generated_at, "days": built_days}
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise FeedBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class GamesJob:
    name = JOB

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: httpx.AsyncClient,
        *,
        fetch_games: FetchGames = scoreboard.fetch_games,
        fetch_game_detail: FetchGameDetail = game_detail.fetch_game_detail,
        stars: StarsProvider = no_stars,
        highlights_search_url: SearchUrlProvider = no_highlights_search_url,
        highlights: HighlightsProvider = no_highlights,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._fetch_games = fetch_games
        self._fetch_game_detail = fetch_game_detail
        self._stars = stars
        self._highlights_search_url = highlights_search_url
        self._highlights = highlights
        self._published_highlights: dict[str, list[Highlight]] = {}
        self._published_stars: dict[str, Stars | None] = {}
        self._games: dict[dt.date, list[ScoreboardGame]] = {}
        self._fetched_at: dict[dt.date, dt.datetime] = {}
        self._details: dict[str, GameDetail] = {}
        self._daily_fetched_at: dt.datetime | None = None
        self._catch_up: set[str] = set()
        self._final_attempts: dict[str, dt.datetime] = {}

    def final_games(self) -> list[ScoreboardGame]:
        return [
            game
            for day in sorted(self._games)
            for game in self._games[day]
            if game.status is GameStatus.FINAL
        ]

    def _current_stars(self) -> dict[str, Stars | None]:
        return {
            game.id: self._stars(game)
            for day in sorted(self._games)
            for game in self._games[day]
        }

    def _current_highlights(self) -> dict[str, list[Highlight]]:
        return {
            game.id: self._highlights(game)
            for day in sorted(self._games)
            for game in self._games[day]
        }

    def _daily_due(self, now: dt.datetime, today: dt.date) -> bool:
        if self._daily_fetched_at is None:
            return True
        morning = dt.datetime.combine(
            today, self._settings.daily_fetch_time, tzinfo=EASTERN
        )
        return now >= morning > self._daily_fetched_at

    def _days_due(self, now: dt.datetime) -> list[dt.date]:
        due: list[dt.date] = []
        for day in sorted(self._games):
            games = self._games[day]
            age = now - self._fetched_at[day]
            live = any(g.status is GameStatus.LIVE for g in games)
            started = any(
                g.status in _NOT_STARTED and g.start_time <= now for g in games
            )
            if (live and age >= LIVE_INTERVAL) or (
                started and age >= START_CHECK_INTERVAL
            ):
                due.append(day)
        return due

    async def _refresh_day(self, day: dt.date, now: dt.datetime) -> None:
        games = await self._fetch_games(self._client, day, self._settings)
        previous = {g.id: g.status for g in self._games.get(day, [])}
        for game in games:
            if previous.get(game.id) in _UNFINISHED and game.status is GameStatus.FINAL:
                self._store.set_final_time(game.id, now)
                self._catch_up.add(game.id)
        self._games[day] = games
        self._fetched_at[day] = now

    def _final_detail_wanted(self, game: ScoreboardGame, now: dt.datetime) -> bool:
        if game.status is not GameStatus.FINAL:
            return False
        if game.id in self._details and game.id not in self._catch_up:
            return False
        attempted = self._final_attempts.get(game.id)
        return attempted is None or now - attempted >= FINAL_DETAIL_RETRY

    async def run(self, now: dt.datetime) -> None:
        today = eastern_date(now)
        daily = self._daily_due(now, today)
        due = days_shown(today) if daily else self._days_due(now)
        calls = 0
        try:
            for day in due:
                calls += 1
                await self._refresh_day(day, now)
            if daily:
                shown = set(days_shown(today))
                self._games = {d: g for d, g in self._games.items() if d in shown}
                self._fetched_at = {
                    d: t for d, t in self._fetched_at.items() if d in shown
                }
                kept = {g.id for games in self._games.values() for g in games}
                self._details = {i: d for i, d in self._details.items() if i in kept}
                self._catch_up &= kept
                self._final_attempts = {
                    i: t for i, t in self._final_attempts.items() if i in kept
                }
                self._daily_fetched_at = now
            for day in sorted(self._games):
                for game in self._games[day]:
                    if game.status is GameStatus.LIVE and day in due:
                        calls += 1
                        self._details[game.id] = await self._fetch_game_detail(
                            self._client, game.id, self._settings
                        )
            final_failure: str | None = None
            for day in sorted(self._games):
                for game in self._games[day]:
                    if not self._final_detail_wanted(game, now):
                        continue
                    calls += 1
                    try:
                        self._details[game.id] = await self._fetch_game_detail(
                            self._client, game.id, self._settings
                        )
                    except SourceError as error:
                        self._final_attempts[game.id] = now
                        final_failure = str(error)
                    else:
                        self._catch_up.discard(game.id)
                        self._final_attempts.pop(game.id, None)
            if final_failure is not None:
                self._store.record_failure(JOB, now, final_failure)
        except SourceError as error:
            self._store.record_failure(JOB, now, str(error))
            return
        if (
            calls == 0
            and self._current_highlights() == self._published_highlights
            and self._current_stars() == self._published_stars
        ):
            return
        try:
            feed = build_games_feed(
                now,
                [(day, self._games[day]) for day in sorted(self._games)],
                self._details,
                self._stars,
                self._highlights_search_url,
                highlights=self._highlights,
            )
        except FeedBuildError as error:
            self._store.record_failure(JOB, now, error.reason)
            return
        if publish_feed(self._settings.data_dir, FEED, feed):
            self._published_highlights = self._current_highlights()
            self._published_stars = self._current_stars()
            self._store.record_success(JOB, now)
        else:
            self._store.record_failure(JOB, now, "feed not written")
