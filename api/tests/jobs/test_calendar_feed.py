# api/tests/jobs/test_calendar_feed.py
#
# Tests for the calendar feed builder and its feed kind.
#
# Tested:
# - The builder converts an entry at 03:30Z to the previous US Eastern day, sorts, removes repeated days and labels 1999 as 1998-99
# - The builder gives a lockout season a first day in February and keeps the gap of a July and August season
# - The builder takes the window days sorted from the days given, and wraps an invalid feed in a build error
# - The kind: windowDays come from the stored games feed and are empty without one
# - The kind: 1993, the season after the current one, abc, 01999, 19999 and 2027 with a trailing newline answer unknown with no source request, 1994 and the current season are known, and an unknown current season is not ready
# - The kind: a request builds and stores a valid feed and a second request reads storage
# - The kind: the current season is fresh before 24 hours and stale at 24 hours
# - The kind: a past season built after its last day is fresh years later, and one built while it was current is rebuilt after 24 hours
# - The kind: a failed read with nothing stored answers unavailable, and a failed rebuild keeps the stored feed
# - The kind: the cleanup keeps every calendar
# - seasons_until runs from the current season down to 1994, labelled, and the builder sets seasons from the current season
# - A past calendar stored while 2027 was current is served with seasons from 2028 once the stars report 2028, with no rebuild and no source call
# - feed_id resolves current to the current season, to None while it is unknown, and leaves an end year unchanged
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_calendar_feed.py
#
# SEE: api/app/jobs/calendar_feed.py

import asyncio
import datetime as dt
from pathlib import Path
from typing import cast

import pytest

from app.feeds.calendar import CalendarFeed
from app.feeds.games import GamesFeed
from app.jobs.calendar_feed import (
    CURRENT_FRESH_FOR,
    KIND,
    CalendarBuildError,
    CalendarFeeds,
    build_calendar_feed,
    seasons_until,
)
from app.jobs.on_demand import (
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.storage.feeds import publish_feed, read_by_id
from app.storage.state import StateStore

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
YEAR = dt.timedelta(days=365)
SECOND = dt.timedelta(seconds=1)


def at(year: int, month: int, day: int, hour: int = 8, minute: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.UTC)


def test_an_entry_at_0330z_is_the_previous_eastern_day_sorted_and_unique() -> None:
    moments = [
        at(1999, 2, 7),
        at(1999, 2, 6, 3, 30),
        at(1999, 2, 7, 12),
        at(1999, 2, 5),
    ]

    feed = build_calendar_feed(NOW, 1999, moments, [], 2027)

    assert feed.days == [dt.date(1999, 2, 5), dt.date(1999, 2, 7)]
    assert feed.first_day == dt.date(1999, 2, 5)
    assert feed.last_day == dt.date(1999, 2, 7)
    assert feed.season == 1999
    assert feed.season_label == "1998-99"
    assert feed.generated_at == NOW
    assert feed.window_days == []


def test_a_lockout_season_starts_in_february() -> None:
    feed = build_calendar_feed(NOW, 1999, [at(1999, 2, 5), at(1999, 5, 5)], [], 2027)

    assert feed.first_day == dt.date(1999, 2, 5)


def test_a_july_and_august_season_keeps_the_gap() -> None:
    moments = [at(2020, 3, 10), at(2020, 3, 11), at(2020, 7, 31), at(2020, 8, 1)]

    feed = build_calendar_feed(NOW, 2020, moments, [], 2027)

    assert feed.days == [
        dt.date(2020, 3, 10),
        dt.date(2020, 3, 11),
        dt.date(2020, 7, 31),
        dt.date(2020, 8, 1),
    ]
    assert feed.last_day == dt.date(2020, 8, 1)


def test_the_window_days_are_sorted() -> None:
    window = [dt.date(2026, 10, 9), dt.date(2026, 10, 8)]

    feed = build_calendar_feed(NOW, 2026, [at(2026, 10, 8)], window, 2026)

    assert feed.window_days == sorted(window)


def test_an_invalid_feed_is_wrapped_in_a_build_error() -> None:
    with pytest.raises(CalendarBuildError) as raised:
        build_calendar_feed(NOW, 2026, [], [], 2026)
    with pytest.raises(CalendarBuildError):
        build_calendar_feed(NOW, 1993, [at(1993, 2, 5)], [], 2026)

    assert raised.value.reason.startswith("invalid feed: ")


def test_seasons_until_runs_newest_first_down_to_1994() -> None:
    seasons = seasons_until(2027)

    assert seasons[0] == {"season": 2027, "season_label": "2026-27"}
    assert seasons[-1] == {"season": 1994, "season_label": "1993-94"}
    assert [item["season"] for item in seasons] == list(range(2027, 1993, -1))
    assert seasons_until(1994) == [{"season": 1994, "season_label": "1993-94"}]


def test_the_builder_sets_the_seasons_from_the_current_season() -> None:
    feed = build_calendar_feed(NOW, 1999, [at(1999, 2, 5)], [], 2028)

    assert feed.seasons[0].season == 2028
    assert feed.seasons[0].season_label == "2027-28"
    assert feed.seasons[-1].season == 1994


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027

    def current_season(self) -> int | None:
        return self.season


class CalendarKit:
    """A feed cache and the calendar kind over one client and one clock, with a
    fake calendar adapter that counts its calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.calls: list[int] = []
        self.failing = False
        self.moments: list[dt.datetime] = [at(2026, 10, 20), at(2027, 4, 10)]
        self.stars = FakeStars()
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.calendars = CalendarFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_calendar=self.fetch_season_calendar,
        )

    async def fetch_season_calendar(
        self, client: SourceClient, season: int, settings: Settings
    ) -> list[dt.datetime]:
        self.calls.append(season)
        if self.failing:
            raise SourceError("test", "calendar is down")
        return list(self.moments)

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, season: int, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, str(season))
        await self.settle()
        return body

    def stored_calendar(self, season: int) -> CalendarFeed | None:
        body = read_by_id(self.path, KIND, str(season))
        return None if body is None else CalendarFeed.model_validate_json(body)


@pytest.fixture
def kit(tmp_path: Path) -> CalendarKit:
    return CalendarKit(tmp_path)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "feed_id", ["1993", "2028", "abc", "01999", "19999", "", "2027\n"]
)
async def test_an_invalid_early_or_future_season_is_unknown_with_no_source_request(
    kit: CalendarKit, feed_id: str
) -> None:
    assert kit.calendars.check(feed_id) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, feed_id)

    assert kit.calls == []


@pytest.mark.anyio
async def test_the_first_and_the_current_season_are_known(kit: CalendarKit) -> None:
    assert kit.calendars.check("1994") is IdStatus.KNOWN
    assert kit.calendars.check("2027") is IdStatus.KNOWN
    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_current_season_is_not_ready(kit: CalendarKit) -> None:
    kit.stars.season = None

    assert kit.calendars.check("2027") is IdStatus.NOT_READY
    assert kit.calendars.check("1993") is IdStatus.UNKNOWN
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2027")
    assert kit.calls == []


@pytest.mark.anyio
async def test_a_request_builds_and_stores_a_valid_feed_and_a_second_reads_storage(
    kit: CalendarKit,
) -> None:
    first = await kit.serve(2027)
    second = await kit.serve(2027)

    assert first == second
    assert kit.calls == [2027]
    stored = kit.stored_calendar(2027)
    assert stored is not None
    assert stored.season_label == "2026-27"
    assert stored.days == [dt.date(2026, 10, 20), dt.date(2027, 4, 10)]


@pytest.mark.anyio
async def test_the_window_days_come_from_the_stored_games_feed(
    kit: CalendarKit,
) -> None:
    window = [dt.date(2026, 10, 7), dt.date(2026, 10, 8)]
    publish_feed(
        kit.path,
        "games",
        GamesFeed.model_validate(
            {
                "generated_at": NOW,
                "days": [{"date": day, "games": []} for day in window],
            }
        ),
    )

    await kit.serve(2027)

    stored = kit.stored_calendar(2027)
    assert stored is not None
    assert stored.window_days == window


@pytest.mark.anyio
async def test_the_window_days_are_empty_without_a_stored_games_feed(
    kit: CalendarKit,
) -> None:
    await kit.serve(2027)

    stored = kit.stored_calendar(2027)
    assert stored is not None
    assert stored.window_days == []


@pytest.mark.anyio
async def test_the_current_season_is_fresh_before_24_hours_and_stale_at_24_hours(
    kit: CalendarKit,
) -> None:
    await kit.serve(2027)
    await kit.serve(2027, NOW + CURRENT_FRESH_FOR - SECOND)
    assert kit.calls == [2027]
    await kit.serve(2027, NOW + CURRENT_FRESH_FOR)

    assert kit.calls == [2027, 2027]


@pytest.mark.anyio
async def test_a_past_season_built_after_its_last_day_is_never_rebuilt(
    kit: CalendarKit,
) -> None:
    kit.moments = [at(2020, 3, 10), at(2020, 8, 1)]

    await kit.serve(2020)
    await kit.serve(2020, NOW + 10 * YEAR)

    assert kit.calls == [2020]


@pytest.mark.anyio
async def test_a_calendar_built_while_its_season_was_current_is_rebuilt_after_the_change(
    kit: CalendarKit,
) -> None:
    await kit.serve(2027)
    kit.stars.season = 2028

    await kit.serve(2027, NOW + CURRENT_FRESH_FOR)

    assert kit.calls == [2027, 2027]


@pytest.mark.anyio
async def test_a_failed_read_with_nothing_stored_answers_unavailable(
    kit: CalendarKit,
) -> None:
    kit.failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve(2027)

    assert kit.stored_calendar(2027) is None


@pytest.mark.anyio
async def test_a_failed_rebuild_keeps_and_serves_the_stored_feed(
    kit: CalendarKit,
) -> None:
    first = await kit.serve(2027)
    kit.failing = True

    body = await kit.serve(2027, NOW + CURRENT_FRESH_FOR)

    assert body == first
    assert len(kit.calls) == 2


@pytest.mark.anyio
async def test_the_cleanup_keeps_every_calendar(kit: CalendarKit) -> None:
    assert kit.calendars.keep("1999") is True
    assert kit.calendars.keep("2027") is True


@pytest.mark.anyio
async def test_a_kept_past_calendar_is_served_with_the_newer_season_list(
    kit: CalendarKit,
) -> None:
    kit.moments = [at(2020, 3, 10), at(2020, 8, 1)]
    await kit.serve(2020)
    kit.stars.season = 2028

    body = await kit.serve(2020, NOW + 10 * YEAR)

    served = CalendarFeed.model_validate_json(body)
    assert served.seasons[0].season == 2028
    stored = kit.stored_calendar(2020)
    assert stored is not None
    assert stored.seasons[0].season == 2027
    assert kit.calls == [2020]


def test_feed_id_resolves_current_and_leaves_an_end_year_alone(
    kit: CalendarKit,
) -> None:
    assert kit.calendars.feed_id("current") == "2027"
    assert kit.calendars.feed_id("1999") == "1999"
    kit.stars.season = None
    assert kit.calendars.feed_id("current") is None
    assert kit.calendars.feed_id("1999") == "1999"
