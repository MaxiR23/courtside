# api/tests/jobs/test_games.py
#
# Tests for the games job.
#
# Tested:
# - Lists every game of the days held in day order, and none before the first run
# - Today is the US Eastern date, across the daylight saving change
# - Rejects a naive time
# - The days shown are today and three days on each side, in order
# - Builds a valid feed, and reports the reason when stars, a search URL or a live detail is missing
# - Daily fetch of the seven days, no refetch before midnight, retry after a failure
# - The day changes at US Eastern midnight: the window moves on the first run after it with no live game of the previous day, fetching only the new day
# - While a game of the previous day is live, that day stays today with its live cadence; the run that sees its last live game end moves the window
# - The morning run refreshes the days shown without moving the window and keeps the cleanup
# - A failed fetch of the new day keeps the last valid feed and the move completes on the next run
# - Start checks every minute from the start time, also while delayed
# - Live refresh every thirty seconds, with each live game's detail
# - Final time and one more detail when a game becomes final, no more checks afterwards
# - A game first seen final takes that moment as its final time; a stored final time is never overwritten
# - Stats availability: available with a detail, pending without one, unavailable out of attempts, none before the final
# - Postponed and canceled games are never checked
# - A run with nothing due makes no request and records nothing
# - The builder puts each game's highlights from the provider in the feed, and none without a provider
# - Lists only the final games of the days held, in day order
# - Lists no shown games before the first run or while a day shown failed to fetch, and the games of every day shown in day order
# - Republishes the feed with no source call when a final game's highlights change, and not when they are unchanged
# - Republishes the feed with no source call when a game's stars change, publishes as soon as the last missing star arrives, and does not republish when stars are unchanged
# - The winner of each final game comes from its final score: home, away, none on a tie or before the final; a tied final game makes the feed invalid
# - Publishes no feed and records no success while a team has no star
# - Publishes the first feed with every star on the first run after every team has one, even with nothing due and with no games in the window
# - A successful run publishes a valid feed and records success
# - A failing final game detail never blocks live details: the last live detail is published, and a final game with no detail is published as pending
# - A failing final detail is fetched again only 2, 4 and 6 hours after the final time, then the game is unavailable; failed attempts survive a restart
# - Stores the US Eastern date of each game seen final
# - The daily run deletes the final time and stats attempts of a game 31 days old, keeps one 30 days old, and never touches highlights
# - The cleanup runs only with the daily fetch
# - A failed scoreboard fetch, live detail fetch or invalid feed keeps the last valid feed and records the reason
# - Asks a live game's detail with a thirty second maximum age, and a final game's detail attempt fetched at or after its due time, never with a maximum age
# - A live day is refreshed every 2 minutes with nobody present and every 30 seconds with someone present
# - A request that finds live data 30 seconds old or more refreshes once, also with concurrent requests, and not under 30 seconds
# - A detail request refreshes only when its game is live, and nothing refreshes with no live game
# - A failed or unexpectedly failing request refresh is recorded and never raises
# - A request refresh that outlives its wait still completes
# - The live refresh stops with no live game and resumes at the start time of the next game
# - refreshed_at is the time the day was last fetched, and none for an unknown game
# - The after-run hook is called after every run, also after a failed fetch
# - A request refresh never runs at the same time as a scheduled run
#
# What is covered:
# - Pure logic: happy path, edge cases, error case
# - Job: successful publication, failed run keeps the last valid feed
#
# Adapters are fakes passed to the job and times are passed to run(), which also
# sets the client clock, so no test uses the real clock. Every test runs in an empty respx mock: a real request fails.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_games.py
#
# SEE: api/app/jobs/games.py

import asyncio
import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import HttpUrl

from app.feeds.games import (
    GamesFeed,
    GameStatus,
    Highlight,
    Leader,
    Leaders,
    LineScore,
    Score,
    Star,
    Stars,
    StatsAvailability,
    Team,
    TeamStats,
)
from app.jobs.games import (
    JOB,
    LIVE_INTERVAL,
    NOBODY_INTERVAL,
    STATS_ATTEMPT_DELAYS,
    FeedBuildError,
    GamesJob,
    build_games_feed,
    days_shown,
    eastern_date,
    final_winner,
    stats_availability,
)
from app.jobs.presence import Presence
from app.settings import Settings
from app.sources.game_detail import GameDetail
from app.sources.http import Freshness, SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.storage.feeds import read_feed
from app.storage.state import StateStore

TODAY = dt.date(2026, 10, 5)
# 12:00 US Eastern (EDT) on TODAY.
NOON = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.UTC)
NEXT_DAY = TODAY + dt.timedelta(days=1)
# 00:10 US Eastern (EDT) on NEXT_DAY.
AFTER_MIDNIGHT = dt.datetime(2026, 10, 6, 4, 10, tzinfo=dt.UTC)
# 06:00 US Eastern (EDT) on NEXT_DAY.
NEXT_MORNING = dt.datetime(2026, 10, 6, 10, 0, tzinfo=dt.UTC)
SEARCH_URL = "https://example.com/search?q=game"
PHOTO = HttpUrl("https://example.com/p.png")


def team(code: str) -> Team:
    return Team(code=code, name=code.title(), city=code.title())


def star(code: str) -> Star:
    return Star(
        player_id=f"s{code}",
        first_name="A",
        last_name="B",
        team_code=code,
        photo_url=PHOTO,
        short_name="A. B",
    )


STARS = Stars(away=star("BOS"), home=star("NYK"))


def leader(code: str) -> Leader:
    return Leader(
        player_id=f"l{code}",
        display_name="A B",
        team_code=code,
        photo_url=PHOTO,
        points=20,
        rebounds=5,
        assists=5,
    )


STATS = TeamStats(
    field_goal_pct=0.5, three_point_pct=0.4, rebounds=40, assists=20, turnovers=10
)
DETAIL = GameDetail.model_validate(
    {
        "leaders": Leaders(away=leader("BOS"), home=leader("NYK")),
        "team_stats": {"away": STATS, "home": STATS},
    }
)


def game(
    game_id: str,
    status: GameStatus,
    start: dt.datetime = NOON - dt.timedelta(hours=3),
    score: Score | None = None,
) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": team("BOS"),
        "home": team("NYK"),
        "status": status,
        "start_time": start,
        "venue": "Arena",
    }
    if status is GameStatus.LIVE:
        data.update(period=2, clock="5:00")
    if status in (GameStatus.LIVE, GameStatus.FINAL):
        data["line_score"] = LineScore(away=[20, 20], home=[18, 20])
        data["score"] = score or Score(away=40, home=38)
    return ScoreboardGame.model_validate(data)


class FakeSources:
    def __init__(self) -> None:
        self.games: dict[dt.date, list[ScoreboardGame]] = {}
        self.day_errors: dict[dt.date, SourceError] = {}
        self.detail_errors: dict[str, SourceError] = {}
        self.game_calls: list[dt.date] = []
        self.detail_calls: list[str] = []
        self.fresh_calls: list[tuple[str, Freshness]] = []
        self.gate: asyncio.Event | None = None
        self.unexpected: Exception | None = None

    async def fetch_games(
        self, client: httpx.AsyncClient, day: dt.date, settings: Settings
    ) -> list[ScoreboardGame]:
        self.game_calls.append(day)
        if self.gate is not None:
            await self.gate.wait()
        if self.unexpected is not None:
            raise self.unexpected
        if day in self.day_errors:
            raise self.day_errors[day]
        return list(self.games.get(day, []))

    async def fetch_game_detail(
        self,
        client: httpx.AsyncClient,
        game_id: str,
        settings: Settings,
        fresh: Freshness,
    ) -> GameDetail:
        self.detail_calls.append(game_id)
        self.fresh_calls.append((game_id, fresh))
        if game_id in self.detail_errors:
            raise self.detail_errors[game_id]
        return DETAIL


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def sources() -> FakeSources:
    return FakeSources()


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]


class ClockedGamesJob(GamesJob):
    """A games job whose client clock reads the time passed to the run in progress."""

    def __init__(self, settings: Settings, store: StateStore, **kwargs: Any) -> None:
        self.clock_now = NOON
        super().__init__(
            settings,
            store,
            create_client(store, clock=lambda: self.clock_now),
            **kwargs,
        )

    async def run(self, now: dt.datetime) -> None:
        self.clock_now = now
        await super().run(now)


def make_job(
    settings: Settings,
    store: StateStore,
    sources: FakeSources,
    *,
    with_inputs: bool = True,
    highlights: Any = None,
    stars: Any = None,
    stars_ready: Any = None,
    **more: Any,
) -> ClockedGamesJob:
    extra: dict[str, Any] = dict(more)
    if with_inputs:
        extra |= {
            "stars": lambda _: STARS,
            "highlights_search_url": lambda _: SEARCH_URL,
        }
    if highlights is not None:
        extra["highlights"] = highlights
    if stars is not None:
        extra["stars"] = stars
    if stars_ready is not None:
        extra["stars_ready"] = stars_ready
    return ClockedGamesJob(
        settings,
        store,
        fetch_games=sources.fetch_games,
        fetch_game_detail=sources.fetch_game_detail,
        **extra,
    )


def published_days(settings: Settings) -> list[dt.date]:
    published = read_feed(settings.data_dir, "games")
    assert published is not None
    return [d.date for d in GamesFeed.model_validate_json(published).days]


def reason(store: StateStore) -> str | None:
    return store.job_states()[0].last_failure_reason


# Group 1: pure helpers


def test_today_is_the_us_eastern_date_of_the_current_time() -> None:
    now = dt.datetime(2026, 10, 6, 3, 0, tzinfo=dt.UTC)

    assert eastern_date(now) == dt.date(2026, 10, 5)


def test_today_follows_the_daylight_saving_change() -> None:
    before = dt.datetime(2026, 11, 1, 3, 30, tzinfo=dt.UTC)  # 23:30 EDT, Oct 31
    after = dt.datetime(2026, 11, 2, 4, 30, tzinfo=dt.UTC)  # 23:30 EST, Nov 1

    assert eastern_date(before) == dt.date(2026, 10, 31)
    assert eastern_date(after) == dt.date(2026, 11, 1)


def test_rejects_a_naive_time() -> None:
    with pytest.raises(ValueError):
        eastern_date(dt.datetime.fromisoformat("2026-10-05T12:00:00"))


def test_days_shown_are_today_and_three_days_on_each_side_in_order() -> None:
    days = days_shown(TODAY)

    assert len(days) == 7
    assert days[0] == dt.date(2026, 10, 2)
    assert days[3] == TODAY
    assert days[-1] == dt.date(2026, 10, 8)


# Group 2: builder


def build(  # type: ignore[no-untyped-def]
    *games: ScoreboardGame,
    details: dict[str, GameDetail] | None = None,
    **extra: Any,
):
    return build_games_feed(
        NOON,
        [(TODAY, list(games)), (TODAY + dt.timedelta(days=1), [])],
        details or {},
        lambda _: STARS,
        lambda _: SEARCH_URL,
        **extra,
    )


HIGHLIGHT = Highlight(
    title="Full game",
    channel="Channel",
    thumbnail_url=HttpUrl("https://example.com/t.jpg"),
    embed_url=HttpUrl("https://example.com/e"),
)


def test_builder_puts_each_games_highlights_from_the_provider_in_the_feed() -> None:
    feed = build(
        game("1", GameStatus.FINAL),
        game("2", GameStatus.FINAL),
        details={"1": DETAIL, "2": DETAIL},
        highlights=lambda g: [HIGHLIGHT] if g.id == "1" else [],
    )

    first, second = feed.days[0].games
    assert first.highlights == [HIGHLIGHT]
    assert second.highlights == []


def test_builder_gives_no_highlights_without_a_provider() -> None:
    feed = build(game("1", GameStatus.FINAL), details={"1": DETAIL})

    assert feed.days[0].games[0].highlights == []


def test_builds_a_valid_feed_from_games_details_stars_and_search_urls() -> None:
    feed = build(
        game("1", GameStatus.SCHEDULED, NOON + dt.timedelta(hours=3)),
        game("2", GameStatus.LIVE),
        game("3", GameStatus.FINAL),
        details={"2": DETAIL, "3": DETAIL},
    )

    assert isinstance(feed, GamesFeed)
    assert [len(day.games) for day in feed.days] == [3, 0]
    assert feed.days[0].games[1].leaders == DETAIL.leaders


def test_reports_the_reason_when_a_game_has_no_stars() -> None:
    with pytest.raises(FeedBuildError) as raised:
        build_games_feed(
            NOON,
            [(TODAY, [game("1", GameStatus.SCHEDULED)])],
            {},
            lambda _: None,
            lambda _: SEARCH_URL,
        )

    assert raised.value.reason.startswith("invalid feed:")
    assert "stars" in raised.value.reason


def test_reports_the_reason_when_a_final_game_has_no_search_url() -> None:
    with pytest.raises(FeedBuildError) as raised:
        build_games_feed(
            NOON,
            [(TODAY, [game("1", GameStatus.FINAL)])],
            {"1": DETAIL},
            lambda _: STARS,
            lambda _: None,
        )

    assert raised.value.reason.startswith("invalid feed:")
    assert raised.value.reason.endswith("games.0")


def test_the_winner_is_the_home_team_when_it_has_more_points() -> None:
    final = game("1", GameStatus.FINAL, score=Score(away=98, home=104))

    assert final_winner(final) == "NYK"


def test_the_winner_is_the_away_team_when_it_has_more_points() -> None:
    assert final_winner(game("1", GameStatus.FINAL)) == "BOS"


def test_a_tied_final_score_has_no_winner() -> None:
    final = game("1", GameStatus.FINAL, score=Score(away=100, home=100))

    assert final_winner(final) is None


def test_a_game_that_is_not_final_has_no_winner() -> None:
    assert final_winner(game("1", GameStatus.LIVE)) is None


def test_builder_sets_the_winner_of_each_final_game_and_none_otherwise() -> None:
    feed = build(
        game("1", GameStatus.SCHEDULED, NOON + dt.timedelta(hours=3)),
        game("2", GameStatus.LIVE),
        game("3", GameStatus.FINAL, score=Score(away=90, home=95)),
        details={"2": DETAIL, "3": DETAIL},
    )

    assert [g.winner for g in feed.days[0].games] == [None, None, "NYK"]


def test_stats_availability_is_available_with_a_detail_pending_without_one_and_unavailable_out_of_attempts() -> (
    None
):
    final = game("1", GameStatus.FINAL)

    assert stats_availability(final, True, False) is StatsAvailability.AVAILABLE
    assert stats_availability(final, True, True) is StatsAvailability.AVAILABLE
    assert stats_availability(final, False, False) is StatsAvailability.PENDING
    assert stats_availability(final, False, True) is StatsAvailability.UNAVAILABLE


def test_a_game_that_is_not_final_has_no_stats_availability() -> None:
    assert stats_availability(game("1", GameStatus.LIVE), True, False) is None


def test_builder_publishes_a_final_game_without_a_detail_as_pending_with_no_leaders_or_team_stats() -> (
    None
):
    feed = build(game("1", GameStatus.FINAL))

    published = feed.days[0].games[0]
    assert published.stats_availability is StatsAvailability.PENDING
    assert published.leaders is None
    assert published.team_stats is None


def test_builder_marks_a_final_game_out_of_attempts_as_unavailable() -> None:
    feed = build(game("1", GameStatus.FINAL), out_of_stats_attempts={"1"})

    assert feed.days[0].games[0].stats_availability is StatsAvailability.UNAVAILABLE


def test_reports_the_reason_when_a_final_game_is_tied() -> None:
    with pytest.raises(FeedBuildError) as raised:
        build(
            game("1", GameStatus.FINAL, score=Score(away=100, home=100)),
            details={"1": DETAIL},
        )

    assert raised.value.reason.startswith("invalid feed:")


def test_reports_the_reason_when_a_live_game_has_no_detail() -> None:
    with pytest.raises(FeedBuildError) as raised:
        build(game("1", GameStatus.LIVE))

    assert raised.value.reason.startswith("invalid feed:")


# Group 3: daily cadence


@pytest.mark.anyio
async def test_fetches_the_seven_days_shown_on_the_first_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    await make_job(settings, store, sources).run(NOON)

    assert sources.game_calls == days_shown(TODAY)


@pytest.mark.anyio
async def test_does_not_fetch_the_days_again_before_the_next_morning(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()

    await job.run(NOON + dt.timedelta(hours=10))

    assert sources.game_calls == []


@pytest.mark.anyio
async def test_moves_the_window_after_midnight_and_refreshes_the_seven_days_at_the_morning_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()
    # 05:59 US Eastern (EDT) is 09:59 UTC.
    await job.run(dt.datetime(2026, 10, 6, 9, 59, tzinfo=dt.UTC))
    assert sources.game_calls == [TODAY + dt.timedelta(days=4)]
    sources.game_calls.clear()

    await job.run(NEXT_MORNING)

    assert sources.game_calls == days_shown(NEXT_DAY)


@pytest.mark.anyio
async def test_does_not_move_the_window_before_midnight(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()

    await job.run(NOON + dt.timedelta(hours=10))

    assert sources.game_calls == []
    assert published_days(settings) == days_shown(TODAY)


@pytest.mark.anyio
async def test_moves_the_window_after_midnight_when_no_game_of_the_previous_day_is_live(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()

    await job.run(AFTER_MIDNIGHT)

    assert sources.game_calls == [TODAY + dt.timedelta(days=4)]
    assert published_days(settings) == days_shown(NEXT_DAY)


@pytest.mark.anyio
async def test_keeps_the_previous_day_as_today_and_its_live_cadence_while_one_of_its_games_is_live(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    start = dt.datetime(2026, 10, 6, 2, 0, tzinfo=dt.UTC)
    sources.games[TODAY] = [game("1", GameStatus.LIVE, start=start)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()
    sources.detail_calls.clear()

    await job.run(AFTER_MIDNIGHT)

    assert sources.game_calls == [TODAY]
    assert sources.detail_calls == ["1"]
    assert published_days(settings) == days_shown(TODAY)

    await job.run(AFTER_MIDNIGHT + dt.timedelta(seconds=30))

    assert sources.game_calls == [TODAY, TODAY]
    assert published_days(settings) == days_shown(TODAY)


@pytest.mark.anyio
async def test_moves_the_window_on_the_run_that_sees_the_last_live_game_of_the_previous_day_end(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [
        game("1", GameStatus.LIVE),
        game("2", GameStatus.LIVE),
    ]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.games[TODAY] = [game("1", GameStatus.FINAL), game("2", GameStatus.LIVE)]
    await job.run(AFTER_MIDNIGHT)
    assert published_days(settings) == days_shown(TODAY)
    sources.games[TODAY] = [game("1", GameStatus.FINAL), game("2", GameStatus.FINAL)]
    sources.game_calls.clear()

    await job.run(AFTER_MIDNIGHT + dt.timedelta(seconds=30))

    assert sources.game_calls == [TODAY, TODAY + dt.timedelta(days=4)]
    assert published_days(settings) == days_shown(NEXT_DAY)
    assert store.final_time("2") == AFTER_MIDNIGHT + dt.timedelta(seconds=30)


@pytest.mark.anyio
async def test_the_morning_run_refreshes_the_days_shown_without_moving_the_window(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    start = dt.datetime(2026, 10, 6, 2, 0, tzinfo=dt.UTC)
    sources.games[TODAY] = [game("1", GameStatus.LIVE, start=start)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    await job.run(AFTER_MIDNIGHT)
    sources.game_calls.clear()

    await job.run(NEXT_MORNING)

    assert sorted(sources.game_calls) == days_shown(TODAY)
    assert published_days(settings) == days_shown(TODAY)


@pytest.mark.anyio
async def test_the_cleanup_still_runs_with_the_morning_run_after_the_window_moved(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    seed_old_game(store, 32)

    await job.run(AFTER_MIDNIGHT)
    assert store.final_time("old") == NOON

    await job.run(NEXT_MORNING)
    assert store.final_time("old") is None


@pytest.mark.anyio
async def test_a_failed_fetch_of_the_new_day_keeps_the_last_valid_feed_and_moves_on_the_next_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.day_errors[TODAY + dt.timedelta(days=4)] = SourceError(
        "scoreboard", "request failed"
    )
    job = make_job(settings, store, sources)
    await job.run(NOON)
    before = read_feed(settings.data_dir, "games")

    await job.run(AFTER_MIDNIGHT)

    assert before is not None
    assert read_feed(settings.data_dir, "games") == before
    assert reason(store) == "scoreboard: request failed"
    del sources.day_errors[TODAY + dt.timedelta(days=4)]

    await job.run(AFTER_MIDNIGHT + dt.timedelta(seconds=30))

    assert published_days(settings) == days_shown(NEXT_DAY)


@pytest.mark.anyio
async def test_retries_the_daily_fetch_on_the_next_run_after_it_fails(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.day_errors[TODAY] = SourceError("scoreboard", "request failed")
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()
    del sources.day_errors[TODAY]

    await job.run(NOON + dt.timedelta(seconds=30))

    assert sources.game_calls == days_shown(TODAY)


# Group 4: start checks


@pytest.mark.anyio
async def test_does_not_check_a_game_before_its_start_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [
        game("1", GameStatus.SCHEDULED, NOON + dt.timedelta(minutes=5))
    ]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()

    await job.run(NOON + dt.timedelta(minutes=4))

    assert sources.game_calls == []


@pytest.mark.anyio
async def test_checks_a_game_every_minute_from_its_start_time_until_it_is_live(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    start = NOON + dt.timedelta(minutes=5)
    sources.games[TODAY] = [game("1", GameStatus.SCHEDULED, start)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    await job.run(start)
    sources.game_calls.clear()

    await job.run(start + dt.timedelta(seconds=30))
    assert sources.game_calls == []
    await job.run(start + dt.timedelta(seconds=60))

    assert sources.game_calls == [TODAY]


@pytest.mark.anyio
async def test_keeps_checking_a_delayed_game_every_minute(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.DELAYED)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()

    await job.run(NOON + dt.timedelta(minutes=1))
    await job.run(NOON + dt.timedelta(minutes=2))

    assert sources.game_calls == [TODAY, TODAY]


# Group 5: live cadence


@pytest.mark.anyio
async def test_refreshes_the_day_and_each_live_game_detail_every_thirty_seconds(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE), game("2", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()
    sources.detail_calls.clear()

    await job.run(NOON + dt.timedelta(seconds=29))
    assert sources.game_calls == []
    await job.run(NOON + dt.timedelta(seconds=30))

    assert sources.game_calls == [TODAY]
    assert sources.detail_calls == ["1", "2"]


# Group 6: final, postponed and canceled


@pytest.mark.anyio
async def test_stores_the_final_time_and_fetches_the_detail_once_more_when_a_game_becomes_final(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.detail_calls.clear()
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    later = NOON + dt.timedelta(seconds=30)

    await job.run(later)

    assert store.final_time("1") == later
    assert sources.detail_calls == ["1"]


@pytest.mark.anyio
async def test_stops_checking_a_game_once_it_is_final(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    await job.run(NOON + dt.timedelta(seconds=30))
    sources.game_calls.clear()
    sources.detail_calls.clear()

    await job.run(NOON + dt.timedelta(minutes=10))

    assert sources.game_calls == []
    assert sources.detail_calls == []


@pytest.mark.anyio
async def test_never_checks_postponed_or_canceled_games(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [
        game("1", GameStatus.POSTPONED),
        game("2", GameStatus.CANCELED),
    ]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()

    await job.run(NOON + dt.timedelta(minutes=10))

    assert sources.game_calls == []
    assert sources.detail_calls == []


@pytest.mark.anyio
async def test_fetches_the_detail_once_for_a_final_game_without_one(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    job = make_job(settings, store, sources)

    await job.run(NOON)
    await job.run(NOON + dt.timedelta(minutes=1))

    assert sources.detail_calls == ["1"]


@pytest.mark.anyio
async def test_stores_the_first_time_a_game_is_seen_final_as_its_final_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]

    await make_job(settings, store, sources).run(NOON)

    assert store.final_time("1") == NOON
    assert store.first_seen_final("1") is True


@pytest.mark.anyio
async def test_never_overwrites_a_stored_final_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    earlier = NOON - dt.timedelta(hours=1)
    store.set_final_time("1", TODAY, earlier, first_seen=True)
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]

    await make_job(settings, store, sources).run(NOON)
    assert store.final_time("1") == earlier

    await make_job(settings, store, sources).run(NOON + dt.timedelta(hours=1))
    assert store.final_time("1") == earlier


@pytest.mark.anyio
async def test_a_game_seen_going_final_has_a_final_time_that_was_not_first_seen(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]

    await job.run(NOON + dt.timedelta(seconds=30))

    assert store.first_seen_final("1") is False


def published_game(settings: Settings, index: int = 0) -> Any:
    published = read_feed(settings.data_dir, "games")
    assert published is not None
    return GamesFeed.model_validate_json(published).days[3].games[index]


def hours(count: float) -> dt.timedelta:
    return dt.timedelta(hours=count)


@pytest.mark.anyio
async def test_a_final_game_without_a_detail_is_published_as_pending(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "unexpected payload")

    await make_job(settings, store, sources).run(NOON)

    published = published_game(settings)
    assert published.score is not None
    assert published.stats_availability is StatsAvailability.PENDING
    assert published.leaders is None
    assert published.team_stats is None
    assert store.job_states()[0].last_success == NOON
    assert reason(store) == "game detail: unexpected payload"


@pytest.mark.anyio
@pytest.mark.parametrize("slot", [2, 4, 6])
async def test_fetches_a_failing_final_detail_again_only_at_two_four_and_six_hours(
    settings: Settings, store: StateStore, sources: FakeSources, slot: int
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "unexpected payload")
    job = make_job(settings, store, sources)
    for earlier in range(0, slot, 2):
        await job.run(NOON + hours(earlier))
    calls = len(sources.detail_calls)
    assert calls == slot // 2

    await job.run(NOON + hours(slot) - dt.timedelta(minutes=1))
    assert len(sources.detail_calls) == calls
    await job.run(NOON + hours(slot))
    assert len(sources.detail_calls) == calls + 1
    await job.run(NOON + hours(slot) + dt.timedelta(minutes=30))
    assert len(sources.detail_calls) == calls + 1


@pytest.mark.anyio
async def test_after_the_six_hour_attempt_fails_the_game_is_unavailable_and_never_fetched_again(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "unexpected payload")
    job = make_job(settings, store, sources)
    for slot in (0, 2, 4, 6):
        await job.run(NOON + hours(slot))

    await job.run(NOON + hours(7))
    await job.run(NOON + hours(9))

    assert sources.detail_calls == ["1"] * 4
    published = published_game(settings)
    assert published.stats_availability is StatsAvailability.UNAVAILABLE
    assert published.leaders is None
    assert published.team_stats is None
    assert store.failed_stats_attempts("1") == 4


@pytest.mark.anyio
async def test_a_successful_retry_publishes_the_game_as_available_with_its_stats(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "unexpected payload")
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.detail_errors.clear()

    await job.run(NOON + hours(2))
    await job.run(NOON + hours(4))

    published = published_game(settings)
    assert published.stats_availability is StatsAvailability.AVAILABLE
    assert published.leaders == DETAIL.leaders
    assert published.team_stats is not None
    assert sources.detail_calls == ["1", "1"]


@pytest.mark.anyio
async def test_failed_stats_attempts_survive_a_restart(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "unexpected payload")
    first = make_job(settings, store, sources)
    await first.run(NOON)
    await first.run(NOON + hours(2))
    sources.detail_calls.clear()

    second = make_job(settings, store, sources)
    await second.run(NOON + hours(2) + dt.timedelta(minutes=1))
    assert sources.detail_calls == []
    await second.run(NOON + hours(4))

    assert sources.detail_calls == ["1"]
    assert store.final_time("1") == NOON
    assert store.failed_stats_attempts("1") == 3


@pytest.mark.anyio
async def test_a_game_seen_going_final_whose_last_fetch_fails_is_fetched_again_at_two_hours(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "request timed out")
    final = NOON + dt.timedelta(seconds=30)
    await job.run(final)
    sources.detail_calls.clear()

    await job.run(final + hours(2) - dt.timedelta(minutes=1))
    assert sources.detail_calls == []
    await job.run(final + hours(2))

    assert sources.detail_calls == ["1"]
    assert published_game(settings).stats_availability is StatsAvailability.AVAILABLE


def test_stats_attempts_are_at_the_final_time_and_two_four_and_six_hours_after() -> (
    None
):
    assert STATS_ATTEMPT_DELAYS == (dt.timedelta(0), hours(2), hours(4), hours(6))


# Group 7: nothing due


@pytest.mark.anyio
async def test_a_run_with_nothing_due_makes_no_request_and_records_nothing(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [
        game("1", GameStatus.SCHEDULED, NOON + dt.timedelta(hours=5))
    ]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    states = store.job_states()
    published = read_feed(settings.data_dir, "games")
    sources.game_calls.clear()

    await job.run(NOON + dt.timedelta(minutes=5))

    assert sources.game_calls == []
    assert sources.detail_calls == []
    assert respx.mock.calls.call_count == 0
    assert store.job_states() == states
    assert read_feed(settings.data_dir, "games") == published


@pytest.mark.anyio
async def test_lists_only_the_final_games_of_the_days_held_in_day_order(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("2", GameStatus.FINAL), game("3", GameStatus.LIVE)]
    sources.games[TODAY - dt.timedelta(days=1)] = [game("1", GameStatus.FINAL)]
    job = make_job(settings, store, sources)

    assert job.final_games() == []
    await job.run(NOON)

    assert [g.id for g in job.final_games()] == ["1", "2"]


@pytest.mark.anyio
async def test_lists_every_game_of_the_days_held_in_day_order_and_none_before_the_first_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("2", GameStatus.FINAL), game("3", GameStatus.LIVE)]
    sources.games[TODAY - dt.timedelta(days=1)] = [game("1", GameStatus.FINAL)]
    job = make_job(settings, store, sources)

    assert job.loaded_games() == []
    await job.run(NOON)

    assert [g.id for g in job.loaded_games()] == ["1", "2", "3"]


@pytest.mark.anyio
async def test_lists_no_shown_games_before_the_first_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    assert job.shown_games() is None


@pytest.mark.anyio
async def test_lists_no_shown_games_while_a_day_shown_failed_to_fetch(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.day_errors[NEXT_DAY] = SourceError("scoreboard", "down")
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert job.shown_games() is None


@pytest.mark.anyio
async def test_lists_the_games_of_every_day_shown_in_day_order(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("2", GameStatus.FINAL), game("3", GameStatus.LIVE)]
    sources.games[TODAY - dt.timedelta(days=1)] = [game("1", GameStatus.FINAL)]
    job = make_job(settings, store, sources)

    await job.run(NOON)

    shown = job.shown_games()
    assert shown is not None and [g.id for g in shown] == ["1", "2", "3"]


@pytest.mark.anyio
async def test_republishes_with_no_source_call_when_a_final_games_highlights_change(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    found: dict[str, list[Highlight]] = {}
    job = make_job(settings, store, sources, highlights=lambda g: found.get(g.id, []))
    await job.run(NOON)
    sources.game_calls.clear()
    sources.detail_calls.clear()
    found["1"] = [HIGHLIGHT]
    later = NOON + dt.timedelta(minutes=5)

    await job.run(later)

    assert sources.game_calls == []
    assert sources.detail_calls == []
    published = read_feed(settings.data_dir, "games")
    assert published is not None
    feed = GamesFeed.model_validate_json(published)
    assert feed.days[3].games[0].highlights == [HIGHLIGHT]
    assert store.job_states()[0].last_success == later


@pytest.mark.anyio
async def test_does_not_republish_when_nothing_is_due_and_highlights_are_unchanged(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    found = {"1": [HIGHLIGHT]}
    job = make_job(settings, store, sources, highlights=lambda g: found[g.id])
    await job.run(NOON)
    published = read_feed(settings.data_dir, "games")
    states = store.job_states()

    await job.run(NOON + dt.timedelta(minutes=5))

    assert read_feed(settings.data_dir, "games") == published
    assert store.job_states() == states


@pytest.mark.anyio
async def test_publishes_no_feed_while_a_team_has_no_star_and_records_no_success(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.SCHEDULED)]
    job = make_job(settings, store, sources, stars_ready=lambda: False)

    await job.run(NOON)

    assert sources.game_calls
    assert read_feed(settings.data_dir, "games") is None
    assert store.job_states() == []


@pytest.mark.anyio
async def test_publishes_a_feed_with_every_star_on_the_first_run_after_every_team_has_one(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.SCHEDULED)]
    ready = {"value": False}
    job = make_job(settings, store, sources, stars_ready=lambda: ready["value"])
    await job.run(NOON)
    sources.game_calls.clear()
    ready["value"] = True
    later = NOON + dt.timedelta(seconds=30)

    await job.run(later)

    assert sources.game_calls == []
    published = read_feed(settings.data_dir, "games")
    assert published is not None
    feed = GamesFeed.model_validate_json(published)
    games = [g for day in feed.days for g in day.games]
    assert games and all(g.stars == STARS for g in games)
    assert store.job_states()[0].last_success == later


@pytest.mark.anyio
async def test_publishes_the_first_feed_once_ready_even_with_no_games_in_the_window(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    ready = {"value": False}
    job = make_job(settings, store, sources, stars_ready=lambda: ready["value"])
    await job.run(NOON)
    assert read_feed(settings.data_dir, "games") is None
    ready["value"] = True

    await job.run(NOON + dt.timedelta(seconds=30))

    assert read_feed(settings.data_dir, "games") is not None


@pytest.mark.anyio
async def test_republishes_with_no_source_call_when_a_games_stars_change(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    current = {"stars": STARS}
    job = make_job(settings, store, sources, stars=lambda _: current["stars"])
    await job.run(NOON)
    sources.game_calls.clear()
    sources.detail_calls.clear()
    other = Stars(
        away=star("BOS").model_copy(update={"player_id": "other"}), home=star("NYK")
    )
    current["stars"] = other
    later = NOON + dt.timedelta(minutes=5)

    await job.run(later)

    assert sources.game_calls == []
    assert sources.detail_calls == []
    published = read_feed(settings.data_dir, "games")
    assert published is not None
    feed = GamesFeed.model_validate_json(published)
    assert feed.days[3].games[0].stars == other
    assert store.job_states()[0].last_success == later


@pytest.mark.anyio
async def test_publishes_the_feed_as_soon_as_the_last_missing_star_arrives(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    current: dict[str, Stars | None] = {"stars": None}
    job = make_job(settings, store, sources, stars=lambda _: current["stars"])
    await job.run(NOON)
    assert read_feed(settings.data_dir, "games") is None
    reason = store.job_states()[0].last_failure_reason
    assert reason is not None
    assert reason.startswith("invalid feed:")
    sources.game_calls.clear()
    sources.detail_calls.clear()
    current["stars"] = STARS
    later = NOON + dt.timedelta(seconds=30)

    await job.run(later)

    assert sources.game_calls == []
    assert sources.detail_calls == []
    published = read_feed(settings.data_dir, "games")
    assert published is not None
    feed = GamesFeed.model_validate_json(published)
    assert feed.days[3].games[0].stars == STARS
    assert store.job_states()[0].last_success == later


@pytest.mark.anyio
async def test_does_not_republish_when_nothing_is_due_and_stars_are_unchanged(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    job = make_job(settings, store, sources, stars=lambda _: STARS)
    await job.run(NOON)
    published = read_feed(settings.data_dir, "games")
    states = store.job_states()

    await job.run(NOON + dt.timedelta(minutes=5))

    assert read_feed(settings.data_dir, "games") == published
    assert store.job_states() == states


# Group 8: publication and failures


@pytest.mark.anyio
async def test_a_successful_run_publishes_a_valid_feed_and_records_success(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE), game("2", GameStatus.FINAL)]

    await make_job(settings, store, sources).run(NOON)

    published = read_feed(settings.data_dir, "games")
    assert published is not None
    feed = GamesFeed.model_validate_json(published)
    assert len(feed.days) == 7
    published_game = next(g for d in feed.days for g in d.games if g.id == "2")
    assert published_game.winner == "BOS"
    state = store.job_states()[0]
    assert state.name == JOB
    assert state.last_success == NOON


@pytest.mark.anyio
async def test_a_failed_scoreboard_fetch_keeps_the_last_valid_feed_and_records_the_reason(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    before = read_feed(settings.data_dir, "games")
    sources.day_errors[TODAY + dt.timedelta(days=1)] = SourceError(
        "scoreboard", "request failed"
    )

    await job.run(dt.datetime(2026, 10, 6, 10, 0, tzinfo=dt.UTC))

    assert before is not None
    assert read_feed(settings.data_dir, "games") == before
    assert reason(store) == "scoreboard: request failed"


@pytest.mark.anyio
async def test_a_failed_live_detail_fetch_keeps_the_last_valid_feed_and_records_the_reason(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    before = read_feed(settings.data_dir, "games")
    sources.detail_errors["1"] = SourceError("game detail", "request timed out")

    await job.run(NOON + dt.timedelta(seconds=30))

    assert before is not None
    assert read_feed(settings.data_dir, "games") == before
    assert reason(store) == "game detail: request timed out"


@pytest.mark.anyio
async def test_a_feed_without_stars_keeps_the_last_valid_feed_and_records_the_reason(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    before = read_feed(settings.data_dir, "games")
    sources.games[TODAY] = [game("1", GameStatus.SCHEDULED, NOON)]
    bare = make_job(settings, store, sources, with_inputs=False)

    await bare.run(NOON)

    assert before is not None
    assert read_feed(settings.data_dir, "games") == before
    failure = reason(store)
    assert failure is not None and failure.startswith("invalid feed:")
    assert "stars" in failure


def final_with_live(sources: FakeSources) -> None:
    sources.games[TODAY - dt.timedelta(days=2)] = [game("old", GameStatus.FINAL)]
    sources.games[TODAY] = [game("live", GameStatus.LIVE)]
    sources.detail_errors["old"] = SourceError("game detail", "unexpected payload")


@pytest.mark.anyio
async def test_a_failing_final_detail_never_blocks_the_live_detail_or_requests_every_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    final_with_live(sources)
    job = make_job(settings, store, sources)

    for step in range(5):
        await job.run(NOON + dt.timedelta(seconds=30 * step))

    assert sources.detail_calls.count("live") == 5
    assert sources.detail_calls.count("old") == 1
    assert reason(store) == "game detail: unexpected payload"
    assert read_feed(settings.data_dir, "games") is not None


@pytest.mark.anyio
async def test_a_game_that_turns_final_with_a_failing_last_fetch_is_published_with_its_last_live_detail(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "request timed out")
    later = NOON + dt.timedelta(seconds=30)

    await job.run(later)

    published = read_feed(settings.data_dir, "games")
    assert published is not None
    feed = GamesFeed.model_validate_json(published)
    assert feed.generated_at == later
    assert feed.days[3].games[0].leaders == DETAIL.leaders
    assert feed.days[3].games[0].stats_availability is StatsAvailability.AVAILABLE
    assert store.job_states()[0].last_success == later
    assert reason(store) == "game detail: request timed out"


@pytest.mark.anyio
async def test_stores_the_us_eastern_date_of_a_game_seen_final(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    late = dt.datetime(2026, 10, 6, 2, 0, tzinfo=dt.UTC)
    sources.games[TODAY] = [
        game("1", GameStatus.FINAL),
        game("2", GameStatus.FINAL, start=late),
    ]

    await make_job(settings, store, sources).run(NOON)

    assert store.game_date("1") == TODAY
    assert store.game_date("2") == TODAY


def seed_old_game(store: StateStore, days: int) -> None:
    day = TODAY - dt.timedelta(days=days)
    store.set_final_time("old", day, NOON, first_seen=True)
    store.record_failed_stats_attempt("old", day)


@pytest.mark.anyio
async def test_the_morning_run_deletes_the_final_time_and_stats_attempts_of_a_game_31_days_old(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    seed_old_game(store, 31)

    await make_job(settings, store, sources).run(NOON)

    assert store.final_time("old") is None
    assert store.first_seen_final("old") is False
    assert store.failed_stats_attempts("old") == 0


@pytest.mark.anyio
async def test_the_morning_run_keeps_a_game_30_days_old(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    seed_old_game(store, 30)

    await make_job(settings, store, sources).run(NOON)

    assert store.final_time("old") == NOON
    assert store.first_seen_final("old") is True
    assert store.failed_stats_attempts("old") == 1


@pytest.mark.anyio
async def test_the_cleanup_runs_only_with_the_daily_fetch(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    seed_old_game(store, 31)

    await job.run(NOON + dt.timedelta(seconds=30))
    await job.run(NOON + dt.timedelta(hours=10))
    assert store.final_time("old") == NOON

    await job.run(dt.datetime(2026, 10, 6, 10, 0, tzinfo=dt.UTC))
    assert store.final_time("old") is None


@pytest.mark.anyio
async def test_the_morning_run_never_deletes_highlights_or_highlight_attempts(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    seed_old_game(store, 31)
    store.record_highlight_attempt("old", TODAY - dt.timedelta(days=31))
    store.set_highlight("old", HIGHLIGHT)

    await make_job(settings, store, sources).run(NOON)

    assert store.highlight_attempts("old") == 1
    assert store.highlights() == {"old": HIGHLIGHT}


@pytest.mark.anyio
async def test_asks_a_live_games_detail_with_a_thirty_second_maximum_age(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]

    await make_job(settings, store, sources).run(NOON)

    assert sources.fresh_calls == [("1", LIVE_INTERVAL)]
    assert LIVE_INTERVAL == dt.timedelta(seconds=30)


@pytest.mark.anyio
async def test_asks_a_final_games_detail_attempt_fetched_at_or_after_its_due_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    sources.detail_errors["1"] = SourceError("game detail", "unexpected payload")
    job = make_job(settings, store, sources)

    await job.run(NOON)
    final_time = store.final_time("1")
    assert final_time is not None
    await job.run(NOON + hours(2))

    assert sources.fresh_calls == [
        ("1", final_time + STATS_ATTEMPT_DELAYS[0]),
        ("1", final_time + STATS_ATTEMPT_DELAYS[1]),
    ]
    assert final_time + STATS_ATTEMPT_DELAYS[1] == final_time + hours(2)


@pytest.mark.anyio
async def test_never_asks_a_final_detail_with_a_maximum_age(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.fresh_calls.clear()
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]

    await job.run(NOON + LIVE_INTERVAL)

    final_time = store.final_time("1")
    assert final_time is not None
    assert sources.fresh_calls == [("1", final_time)]
    assert isinstance(sources.fresh_calls[0][1], dt.datetime)


# Group 7: presence, requests and the live cadence


def seconds(count: int) -> dt.timedelta:
    return dt.timedelta(seconds=count)


async def settle() -> None:
    for _ in range(10):
        await asyncio.sleep(0)


@pytest.mark.anyio
async def test_refreshes_a_live_day_every_two_minutes_with_nobody_present(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE), game("2", GameStatus.LIVE)]
    job = make_job(settings, store, sources, present=lambda now: False)
    await job.run(NOON)
    sources.game_calls.clear()
    sources.detail_calls.clear()

    for offset in (30, 60, 90):
        await job.run(NOON + seconds(offset))
    assert (sources.game_calls, sources.detail_calls) == ([], [])
    await job.run(NOON + seconds(120))

    assert NOBODY_INTERVAL == dt.timedelta(minutes=2)
    assert sources.game_calls == [TODAY]
    assert sources.detail_calls == ["1", "2"]


@pytest.mark.anyio
async def test_refreshes_a_live_day_every_thirty_seconds_with_someone_present(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    near = Presence(clock=lambda: NOON)
    near.seen()
    old = Presence(clock=lambda: NOON - dt.timedelta(minutes=6))
    old.seen()

    for presence, expected in ((near, [TODAY]), (old, [])):
        sources.game_calls.clear()
        job = make_job(settings, store, sources, present=presence.present)
        await job.run(NOON)
        sources.game_calls.clear()
        await job.run(NOON + seconds(30))
        assert sources.game_calls == expected
        if not expected:
            await job.run(NOON + seconds(120))
            assert sources.game_calls == [TODAY]


@pytest.mark.anyio
async def test_a_request_with_live_data_thirty_seconds_old_refreshes_once_even_with_concurrent_requests(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE), game("2", GameStatus.LIVE)]
    job = make_job(settings, store, sources, present=lambda now: False)
    await job.run(NOON)
    sources.game_calls.clear()
    sources.detail_calls.clear()
    job.clock_now = NOON + seconds(31)
    sources.gate = asyncio.Event()

    first = asyncio.create_task(job.refresh_live())
    second = asyncio.create_task(job.refresh_live())
    await settle()
    sources.gate.set()
    await asyncio.gather(first, second)
    await job.refresh_live()

    assert sources.game_calls == [TODAY]
    assert sources.detail_calls == ["1", "2"]


@pytest.mark.anyio
async def test_a_request_with_live_data_under_thirty_seconds_old_does_not_refresh(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()
    job.clock_now = NOON + seconds(29)

    await job.refresh_live()
    await job.refresh_live("1")

    assert sources.game_calls == []


@pytest.mark.anyio
async def test_a_detail_request_refreshes_only_when_its_game_is_live(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    later = NOON + dt.timedelta(hours=2)
    sources.games[TODAY] = [
        game("1", GameStatus.LIVE),
        game("2", GameStatus.SCHEDULED, start=later),
    ]
    job = make_job(settings, store, sources, present=lambda now: False)
    await job.run(NOON)
    sources.game_calls.clear()
    job.clock_now = NOON + seconds(31)

    await job.refresh_live("2")
    await job.refresh_live("unknown")
    assert sources.game_calls == []
    await job.refresh_live("1")

    assert sources.game_calls == [TODAY]


@pytest.mark.anyio
async def test_a_request_with_no_live_game_does_not_refresh(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.FINAL)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()
    job.clock_now = NOON + dt.timedelta(hours=1)

    await job.refresh_live()

    assert sources.game_calls == []


@pytest.mark.anyio
async def test_a_request_refresh_that_fails_records_the_failure_and_returns(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    job.clock_now = NOON + seconds(31)
    sources.day_errors[TODAY] = SourceError("scoreboard", "down")

    await job.refresh_live()

    assert reason(store) is not None
    assert "down" in (reason(store) or "")
    del sources.day_errors[TODAY]
    sources.unexpected = RuntimeError("boom")
    job.clock_now = NOON + seconds(62)

    await job.refresh_live()
    await settle()

    assert reason(store) == "unexpected error: RuntimeError"


@pytest.mark.anyio
async def test_a_request_refresh_outlives_its_wait_and_still_completes(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    first = read_feed(settings.data_dir, "games")
    job.clock_now = NOON + seconds(31)
    sources.games[TODAY] = [game("1", GameStatus.LIVE, score=Score(away=50, home=48))]
    sources.gate = asyncio.Event()

    await job.refresh_live(wait=0.01)

    assert read_feed(settings.data_dir, "games") == first
    sources.gate.set()
    await settle()
    second = read_feed(settings.data_dir, "games")
    assert second is not None
    assert second != first
    assert b'"away":50' in second.replace(b" ", b"")


@pytest.mark.anyio
async def test_stops_the_live_refresh_with_no_live_game_and_resumes_at_the_next_start_time(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    start = NOON + dt.timedelta(hours=3)
    sources.games[TODAY] = [
        game("1", GameStatus.LIVE),
        game("2", GameStatus.SCHEDULED, start=start),
    ]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.games[TODAY] = [
        game("1", GameStatus.FINAL),
        game("2", GameStatus.SCHEDULED, start=start),
    ]
    await job.run(NOON + seconds(30))
    sources.game_calls.clear()

    moment = NOON + seconds(60)
    while moment < start:
        await job.run(moment)
        moment += seconds(30)
    assert sources.game_calls == []
    await job.run(start)

    assert sources.game_calls == [TODAY]


@pytest.mark.anyio
async def test_refreshed_at_is_the_time_its_day_was_last_fetched_and_none_for_an_unknown_game(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    assert job.refreshed_at("1") is None
    await job.run(NOON)
    assert job.refreshed_at("1") == NOON
    await job.run(NOON + seconds(30))

    assert job.refreshed_at("1") == NOON + seconds(30)
    assert job.refreshed_at("unknown") is None


@pytest.mark.anyio
async def test_calls_the_after_run_hook_after_every_run_also_after_a_failed_fetch(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    calls: list[int] = []
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources, after_run=lambda: calls.append(1))

    await job.run(NOON)
    await job.run(NOON + seconds(30))
    sources.day_errors[TODAY] = SourceError("scoreboard", "down")
    await job.run(NOON + seconds(60))

    assert len(calls) == 3


@pytest.mark.anyio
async def test_a_request_refresh_never_runs_at_the_same_time_as_a_scheduled_run(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.games[TODAY] = [game("1", GameStatus.LIVE)]
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.game_calls.clear()
    later = NOON + seconds(31)
    job.clock_now = later
    sources.gate = asyncio.Event()
    scheduled = asyncio.create_task(job.run(later))
    await settle()
    assert sources.game_calls == [TODAY]

    request = asyncio.create_task(job.refresh_live())
    await settle()
    assert sources.game_calls == [TODAY]
    sources.gate.set()
    await asyncio.gather(scheduled, request)

    assert sources.game_calls == [TODAY]
