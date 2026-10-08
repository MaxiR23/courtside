# api/app/jobs/games.py
#
# Games job: fetches the days shown on the cadences of rules C and E of
# docs/source-rules.md and publishes the games feed. The feed's today is the US Eastern date; after
# midnight the previous day stays today while any of its games is live, then
# the window moves. The morning run refreshes the days shown and runs the
# cleanup. Stars, highlights and the highlights search URL
# are inputs, supplied by other jobs. The first feed after a start waits until
# every team has a star, so no published game ever lacks one.
#
# A final game's detail is fetched when it becomes final and, after a failure,
# 2, 4 and 6 hours after its final time; the failed attempts are stored.
# The final time is the client clock read right after the scoreboard response
# that shows the game final arrives (a cached response included), not the time
# the run started, and the due check reads the same clock. The cache stores a
# fetch with its send time, and an attempt asks for a fetch at or after its
# due time, so a first attempt is never served a detail sent before the final
# status was observed, such as a live snapshot fetched during the same run.
#
# The game detail feed kind reads the games of the days shown through
# shown_games and refreshed_at; after_run lets it start the final builds and
# the cleanup.
#
# Once a day, with the daily fetch, the final times and failed stats attempts of
# games dated more than 30 days ago are deleted from the job state; highlights
# are kept.
#
# SEE: docs/source-rules.md, docs/adr/0007-backend-runtime-and-data-pipeline.md,
# docs/api/games.md,
# docs/adr/0010-final-game-attempts.md, docs/adr/0011-state-retention.md,
# docs/adr/0013-day-change.md, docs/adr/0014-star-guarantees.md

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.feeds.games import (
    GamesFeed,
    GameStatus,
    Highlight,
    Stars,
    StatsAvailability,
)
from app.jobs.on_demand import MISSING_WAIT_SECONDS
from app.settings import Settings
from app.sources import game_detail, scoreboard
from app.sources.game_detail import GameDetail
from app.sources.http import Freshness, SourceClient, SourceError
from app.sources.scoreboard import ScoreboardGame
from app.storage.feeds import publish_feed
from app.storage.state import StateStore

JOB = "games"
FEED = "games"
EASTERN = ZoneInfo("America/New_York")
DAYS_AROUND = 3
LIVE_INTERVAL = dt.timedelta(seconds=30)
NOBODY_INTERVAL = dt.timedelta(minutes=2)
START_CHECK_INTERVAL = dt.timedelta(minutes=1)
STATS_ATTEMPT_DELAYS = (
    dt.timedelta(0),
    dt.timedelta(hours=2),
    dt.timedelta(hours=4),
    dt.timedelta(hours=6),
)
MAX_STATS_ATTEMPTS = len(STATS_ATTEMPT_DELAYS)
STATE_RETENTION = dt.timedelta(days=30)

StarsProvider = Callable[[ScoreboardGame], Stars | None]
StarsReady = Callable[[], bool]
SearchUrlProvider = Callable[[ScoreboardGame], str | None]
HighlightsProvider = Callable[[ScoreboardGame], list[Highlight]]
PresenceCheck = Callable[[dt.datetime], bool]
AfterRun = Callable[[], None]
FetchGames = Callable[
    [SourceClient, dt.date, Settings], Awaitable[list[ScoreboardGame]]
]
FetchGameDetail = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[GameDetail]
]

_NOT_STARTED = (GameStatus.SCHEDULED, GameStatus.DELAYED)
_UNFINISHED = (GameStatus.SCHEDULED, GameStatus.LIVE, GameStatus.DELAYED)


def no_stars(game: ScoreboardGame) -> Stars | None:
    """Default when no stars provider is given: every game then lacks its stars."""
    return None


def stars_always_ready() -> bool:
    """Default when no readiness check is given: publication is never held."""
    return True


def always_present(now: dt.datetime) -> bool:
    """Default when no presence check is given: the live cadence is always 30 seconds."""
    return True


def no_after_run() -> None:
    """Default when no after-run hook is given."""


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


def stats_availability(
    game: ScoreboardGame, has_detail: bool, out_of_attempts: bool
) -> StatsAvailability | None:
    """Whether a final game's stats are in the feed; None before the final."""
    if game.status is not GameStatus.FINAL:
        return None
    if has_detail:
        return StatsAvailability.AVAILABLE
    if out_of_attempts:
        return StatsAvailability.UNAVAILABLE
    return StatsAvailability.PENDING


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
    out_of_stats_attempts: AbstractSet[str] = frozenset(),
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
            data["stats_availability"] = stats_availability(
                game, detail is not None, game.id in out_of_stats_attempts
            )
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
        client: SourceClient,
        *,
        fetch_games: FetchGames = scoreboard.fetch_games,
        fetch_game_detail: FetchGameDetail = game_detail.fetch_game_detail,
        stars: StarsProvider = no_stars,
        stars_ready: StarsReady = stars_always_ready,
        highlights_search_url: SearchUrlProvider = no_highlights_search_url,
        highlights: HighlightsProvider = no_highlights,
        present: PresenceCheck = always_present,
        after_run: AfterRun = no_after_run,
    ) -> None:
        self._present = present
        self._after_run = after_run
        self._lock = asyncio.Lock()
        self._refresh: asyncio.Task[None] | None = None
        self._requested = False
        self._settings = settings
        self._store = store
        self._client = client
        self._fetch_games = fetch_games
        self._fetch_game_detail = fetch_game_detail
        self._stars = stars
        self._stars_ready = stars_ready
        self._has_published = False
        self._highlights_search_url = highlights_search_url
        self._highlights = highlights
        self._published_highlights: dict[str, list[Highlight]] = {}
        self._published_stars: dict[str, Stars | None] = {}
        self._games: dict[dt.date, list[ScoreboardGame]] = {}
        self._fetched_at: dict[dt.date, dt.datetime] = {}
        self._details: dict[str, GameDetail] = {}
        self._daily_fetched_at: dt.datetime | None = None
        self._catch_up: set[str] = set()
        self._today: dt.date | None = None

    def final_games(self) -> list[ScoreboardGame]:
        return [
            game
            for day in sorted(self._games)
            for game in self._games[day]
            if game.status is GameStatus.FINAL
        ]

    def shown_games(self) -> list[ScoreboardGame] | None:
        """The games of every day shown, in day order; None until each day shown has been fetched."""
        if self._today is None:
            return None
        shown = days_shown(self._today)
        if any(day not in self._games for day in shown):
            return None
        return [game for day in shown for game in self._games[day]]

    def loaded_game(self, game_id: str) -> ScoreboardGame | None:
        """The game with this id in any day held now, shown or not; None when no day holds it."""
        for games in self._games.values():
            for game in games:
                if game.id == game_id:
                    return game
        return None

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

    def _has_live(self, day: dt.date) -> bool:
        return any(g.status is GameStatus.LIVE for g in self._games.get(day, []))

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
            interval = (
                LIVE_INTERVAL
                if self._requested or self._present(now)
                else NOBODY_INTERVAL
            )
            if (live and age >= interval) or (started and age >= START_CHECK_INTERVAL):
                due.append(day)
        return due

    async def _refresh_day(self, day: dt.date, now: dt.datetime) -> None:
        games = await self._fetch_games(self._client, day, self._settings)
        final_at = self._client.clock()
        previous = {g.id: g.status for g in self._games.get(day, [])}
        for game in games:
            before = previous.get(game.id)
            if game.status is GameStatus.FINAL and before is not GameStatus.FINAL:
                going_final = before in _UNFINISHED
                self._store.set_final_time(
                    game.id,
                    eastern_date(game.start_time),
                    final_at,
                    first_seen=not going_final,
                )
                if going_final:
                    self._catch_up.add(game.id)
        self._games[day] = games
        self._fetched_at[day] = now

    def _final_detail_due(self, game: ScoreboardGame) -> dt.datetime | None:
        """The due time of this final game's detail attempt when it is due now."""
        if game.status is not GameStatus.FINAL:
            return None
        if game.id in self._details and game.id not in self._catch_up:
            return None
        final_time = self._store.final_time(game.id)
        if final_time is None:
            return None
        failed = self._store.failed_stats_attempts(game.id)
        if failed >= MAX_STATS_ATTEMPTS:
            return None
        due_at = final_time + STATS_ATTEMPT_DELAYS[failed]
        return due_at if self._client.clock() >= due_at else None

    def refreshed_at(self, game_id: str) -> dt.datetime | None:
        """When the day that holds the game was last fetched; None for an unknown game."""
        for day, games in self._games.items():
            if any(game.id == game_id for game in games):
                return self._fetched_at.get(day)
        return None

    async def refresh_live(
        self, game_id: str | None = None, *, wait: float = MISSING_WAIT_SECONDS
    ) -> None:
        """Refreshes now when the live data is LIVE_INTERVAL old or more, once for all callers.

        With a game id, only that game's day counts, and only when it is live.
        Waits up to `wait` seconds; a failure or a timeout never raises.
        """
        now = self._client.clock()
        stale = False
        for day, games in self._games.items():
            if game_id is None:
                live = any(g.status is GameStatus.LIVE for g in games)
            else:
                live = any(
                    g.id == game_id and g.status is GameStatus.LIVE for g in games
                )
            if live and now - self._fetched_at[day] >= LIVE_INTERVAL:
                stale = True
        if not stale:
            return
        task = self._refresh
        if task is None:
            task = asyncio.create_task(self._run_requested(now))
            self._refresh = task

            def done(finished: asyncio.Task[None]) -> None:
                if self._refresh is finished:
                    self._refresh = None
                if finished.cancelled():
                    return
                error = finished.exception()
                if error is not None:
                    self._store.record_failure(
                        JOB, now, f"unexpected error: {type(error).__name__}"
                    )

            task.add_done_callback(done)
        try:
            await asyncio.wait_for(asyncio.shield(task), wait)
        except Exception:  # noqa: BLE001 - a request never fails because of the refresh
            return

    async def run(self, now: dt.datetime) -> None:
        async with self._lock:
            await self._run_with_hook(now)

    async def _run_requested(self, now: dt.datetime) -> None:
        """A run started by a request: live days are due at the live cadence even with nobody present."""
        async with self._lock:
            self._requested = True
            try:
                await self._run_with_hook(now)
            finally:
                self._requested = False

    async def _run_with_hook(self, now: dt.datetime) -> None:
        try:
            await self._run(now)
        finally:
            self._after_run()

    async def _run(self, now: dt.datetime) -> None:
        today = eastern_date(now)
        if self._today is None:
            self._today = today
        daily = self._daily_due(now, today)
        due = self._days_due(now)
        refreshed: list[dt.date] = []
        moved = False
        calls = 0
        try:
            for day in due:
                calls += 1
                await self._refresh_day(day, now)
                refreshed.append(day)
            if self._today < today and not self._has_live(self._today):
                self._today = today
                moved = True
            shown = days_shown(self._today)
            if daily:
                rest = [d for d in shown if d not in refreshed]
            else:
                rest = [d for d in shown if d not in self._games]
            for day in rest:
                calls += 1
                await self._refresh_day(day, now)
                refreshed.append(day)
            kept_days = set(shown)
            self._games = {d: g for d, g in self._games.items() if d in kept_days}
            self._fetched_at = {
                d: t for d, t in self._fetched_at.items() if d in kept_days
            }
            kept = {g.id for games in self._games.values() for g in games}
            self._details = {i: d for i, d in self._details.items() if i in kept}
            self._catch_up &= kept
            if daily:
                self._store.prune_final_times(today - STATE_RETENTION)
                self._daily_fetched_at = now
            for day in sorted(self._games):
                for game in self._games[day]:
                    if game.status is GameStatus.LIVE and day in refreshed:
                        calls += 1
                        self._details[game.id] = await self._fetch_game_detail(
                            self._client, game.id, self._settings, LIVE_INTERVAL
                        )
            final_failure: str | None = None
            for day in sorted(self._games):
                for game in self._games[day]:
                    due_at = self._final_detail_due(game)
                    if due_at is None:
                        continue
                    calls += 1
                    try:
                        self._details[game.id] = await self._fetch_game_detail(
                            self._client, game.id, self._settings, due_at
                        )
                    except SourceError as error:
                        self._store.record_failed_stats_attempt(
                            game.id, eastern_date(game.start_time)
                        )
                        final_failure = str(error)
                    else:
                        self._catch_up.discard(game.id)
            if final_failure is not None:
                self._store.record_failure(JOB, now, final_failure)
        except SourceError as error:
            self._store.record_failure(JOB, now, str(error))
            return
        if not self._stars_ready():
            return
        if (
            self._has_published
            and calls == 0
            and not moved
            and self._current_highlights() == self._published_highlights
            and self._current_stars() == self._published_stars
        ):
            return
        out = {
            g.id
            for g in self.final_games()
            if g.id not in self._details
            and self._store.failed_stats_attempts(g.id) >= MAX_STATS_ATTEMPTS
        }
        try:
            feed = build_games_feed(
                now,
                [(day, self._games[day]) for day in sorted(self._games)],
                self._details,
                self._stars,
                self._highlights_search_url,
                highlights=self._highlights,
                out_of_stats_attempts=out,
            )
        except FeedBuildError as error:
            self._store.record_failure(JOB, now, error.reason)
            return
        if publish_feed(self._settings.data_dir, FEED, feed):
            self._published_highlights = self._current_highlights()
            self._published_stars = self._current_stars()
            self._has_published = True
            self._store.record_success(JOB, now)
        else:
            self._store.record_failure(JOB, now, "feed not written")
