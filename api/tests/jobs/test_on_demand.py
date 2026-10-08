# api/tests/jobs/test_on_demand.py
#
# Tests for the on-demand feed cache.
#
# Tested:
# - Builds nothing without a request
# - Answers unknown for an unknown id with no build and no source request
# - Answers unavailable for a not-ready id with no build
# - Serves a fresh stored feed from storage with no build, byte for byte
# - Serves a stale feed at once and rebuilds it once in the background
# - Builds a missing feed and serves it within the wait
# - Answers unavailable past the wait while the shielded build still finishes and is stored
# - Waits 20 seconds by default, runs at most 4 builds and retries a failed build after 10 minutes
# - Concurrent requests for one missing feed share one build
# - Runs at most 4 builds at once
# - Leaves no task referenced after a build completes, fails or outlives its wait
# - A failed rebuild keeps the stored feed and is listed as a failed build
# - Does not rebuild a failed feed for 10 minutes and rebuilds it after
# - A missing feed whose build failed within 10 minutes answers unavailable with no new build
# - Records an unexpected build error by its type and an invalid built feed as not written
# - Serve-time additions are in the response and not in the stored file
# - Serves the stored feed without additions when the additions make it invalid
# - Keeps stored feeds and build times across a restart with no build on startup
# - Serves a stored feed with no build time as stale and rebuilds it
# - Treats a stored file that fails validation as missing and builds it
# - The cleanup deletes only invalid ids, with no build, check or source request
# - Rejects a second kind with the same name and a kind name that is not a safe id
# - A stale feed whose kind waits when stale is rebuilt while the request waits and the new body is served
# - Concurrent waiting requests share one rebuild
# - A waiting request is served the stored body when the rebuild fails or outlives the wait, and the shielded build still finishes
# - A stale feed whose wait_when_stale is false is served at once
# - Within 10 minutes of a failure a waiting kind serves the stored feed with no build
# - serve with a wait override of 0 serves a stale waiting feed's stored body at once with the rebuild in flight
# - serve with a wait override of 0 answers unavailable at once for a missing feed, and the wait property reports the configured wait
# - refresh starts one build without waiting, joins one in flight and leaves no task referenced
#
# What is covered:
# - Happy path (fresh, missing built), edge cases (stale, concurrent, semaphore, restart, no build time, invalid stored file), error cases (failed build, timeout, unknown and not ready)
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_on_demand.py
#
# SEE: api/app/jobs/on_demand.py

import asyncio
import datetime as dt
import logging
from pathlib import Path

import pytest
import respx

from app.feeds.games import FeedModel
from app.jobs.on_demand import (
    MAX_BUILDS,
    MISSING_WAIT_SECONDS,
    RETRY_AFTER,
    FeedCache,
    FeedKind,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.sources.http import SourceError
from app.storage.feeds import publish_by_id, published_ids, read_by_id
from app.storage.state import StateStore

T = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
HOUR = dt.timedelta(hours=1)


class FakeFeed(FeedModel):
    id: str
    version: int
    extra: str | None = None


class Fake:
    """A feed kind whose build, check and keep calls are counted."""

    def __init__(self, name: str = "players") -> None:
        self.name = name
        self.version = 1
        self.builds = 0
        self.checks = 0
        self.keeps = 0
        self.running = 0
        self.peak = 0
        self.gate: asyncio.Event | None = None
        self.fail: Exception | None = None
        self.invalid = False
        self.status = IdStatus.KNOWN
        self.keep_ids: set[str] | None = None

    async def build(self, feed_id: str) -> FakeFeed:
        self.builds += 1
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            if self.gate is not None:
                await self.gate.wait()
            if self.fail is not None:
                raise self.fail
            if self.invalid:
                return FakeFeed.model_construct(id=feed_id, version="x")
            return FakeFeed(id=feed_id, version=self.version)
        finally:
            self.running -= 1

    def check(self, feed_id: str) -> IdStatus:
        self.checks += 1
        return self.status

    def keep(self, feed_id: str) -> bool:
        self.keeps += 1
        return self.keep_ids is None or feed_id in self.keep_ids

    def kind(self, serve_with: object = None) -> FeedKind[FakeFeed]:
        return FeedKind(
            self.name,
            FakeFeed,
            check=self.check,
            build=self.build,
            is_fresh=lambda feed, built_at, now: now - built_at < HOUR,
            keep=self.keep,
            serve_with=serve_with,  # type: ignore[arg-type]
        )


class Setup:
    def __init__(self, path: Path, fake: Fake, *, wait: float = 5.0) -> None:
        self.path = path
        self.fake = fake
        self.now = [T]
        self.store = StateStore(path)
        self.store.migrate()
        self.cache = FeedCache(path, self.store, clock=lambda: self.now[0], wait=wait)
        self.cache.register(fake.kind())

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    def stored(self, feed_id: str = "p1") -> bytes | None:
        return read_by_id(self.path, "players", feed_id)


def body_of(version: int, feed_id: str = "p1", extra: str | None = None) -> bytes:
    return (
        FakeFeed(id=feed_id, version=version, extra=extra)
        .model_dump_json()
        .encode("utf-8")
    )


@pytest.mark.anyio
async def test_builds_nothing_without_a_request(tmp_path: Path) -> None:
    setup = Setup(tmp_path, Fake())

    await asyncio.sleep(0)

    assert setup.fake.builds == 0
    assert not (tmp_path / "feeds").exists()
    assert setup.store.feed_build_ids("players") == set()
    assert setup.cache.in_flight == {}


@pytest.mark.anyio
async def test_answers_unknown_for_an_unknown_id_with_no_build_and_no_source_request(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.status = IdStatus.UNKNOWN
    setup = Setup(tmp_path, fake)

    with respx.mock, pytest.raises(UnknownFeedError):
        await setup.cache.serve("players", "nobody")

    assert fake.builds == 0
    assert setup.store.feed_build("players", "nobody") is None
    assert setup.stored("nobody") is None


@pytest.mark.anyio
async def test_answers_unavailable_for_a_not_ready_id_with_no_build(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.status = IdStatus.NOT_READY
    setup = Setup(tmp_path, fake)

    with respx.mock, pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")

    assert fake.builds == 0
    assert setup.store.feed_build("players", "p1") is None


@pytest.mark.anyio
async def test_serves_a_fresh_stored_feed_from_storage_with_no_build(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    publish_by_id(tmp_path, "players", FakeFeed, "p1", FakeFeed(id="p1", version=7))
    setup.store.record_build("players", "p1", T)
    setup.now[0] = T + HOUR / 2

    with respx.mock:
        body = await setup.cache.serve("players", "p1")

    assert body == body_of(7)
    assert body == setup.stored()
    assert setup.fake.builds == 0
    assert setup.cache.in_flight == {}


@pytest.mark.anyio
async def test_serves_a_stale_feed_at_once_and_rebuilds_it_once_in_the_background(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "p1")
    assert fake.builds == 1
    setup.now[0] = T + 2 * HOUR
    fake.version = 2
    fake.gate = asyncio.Event()

    first = await setup.cache.serve("players", "p1")
    await asyncio.sleep(0)
    second = await setup.cache.serve("players", "p1")

    assert first == second == body_of(1)
    assert fake.builds == 2
    assert fake.running == 1
    fake.gate.set()
    await setup.settle()
    assert await setup.cache.serve("players", "p1") == body_of(2)
    build = setup.store.feed_build("players", "p1")
    assert build is not None
    assert build.last_build == T + 2 * HOUR
    assert fake.builds == 2
    assert setup.cache.in_flight == {}


@pytest.mark.anyio
async def test_builds_a_missing_feed_and_serves_it_within_the_wait(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())

    body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    assert setup.stored() == body
    build = setup.store.feed_build("players", "p1")
    assert build is not None
    assert build.last_build == T
    assert setup.fake.builds == 1


@pytest.mark.anyio
async def test_answers_unavailable_past_the_wait_while_the_shielded_build_finishes(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.gate = asyncio.Event()
    setup = Setup(tmp_path, fake, wait=0)

    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")

    task = setup.cache.in_flight[("players", "p1")]
    assert not task.cancelled()
    fake.gate.set()
    await task
    await asyncio.sleep(0)
    assert setup.stored() == body_of(1)
    build = setup.store.feed_build("players", "p1")
    assert build is not None
    assert build.last_build == T
    assert await setup.cache.serve("players", "p1") == body_of(1)
    assert fake.builds == 1
    assert setup.cache.in_flight == {}


def test_waits_20_seconds_runs_at_most_4_builds_and_retries_after_10_minutes() -> None:
    assert MISSING_WAIT_SECONDS == 20
    assert MAX_BUILDS == 4
    assert RETRY_AFTER == dt.timedelta(minutes=10)


@pytest.mark.anyio
async def test_concurrent_requests_for_one_missing_feed_share_one_build(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())

    bodies = await asyncio.gather(
        *(setup.cache.serve("players", "p1") for _ in range(5))
    )

    assert setup.fake.builds == 1
    assert len(set(bodies)) == 1
    assert bodies[0] == body_of(1)
    assert setup.cache.in_flight == {}


@pytest.mark.anyio
async def test_runs_at_most_4_builds_at_once(tmp_path: Path) -> None:
    fake = Fake()
    fake.gate = asyncio.Event()
    setup = Setup(tmp_path, fake)
    ids = [f"p{n}" for n in range(6)]
    tasks = [asyncio.create_task(setup.cache.serve("players", i)) for i in ids]

    for _ in range(10):
        await asyncio.sleep(0)

    assert fake.peak == 4
    assert fake.builds == 4
    fake.gate.set()
    bodies = await asyncio.gather(*tasks)
    assert bodies == [body_of(1, i) for i in ids]
    assert fake.peak == 4
    assert fake.builds == 6
    assert setup.cache.in_flight == {}


@pytest.mark.anyio
async def test_leaves_no_task_referenced_after_a_build_completes_fails_or_outlives_its_wait(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "done")
    assert setup.cache.in_flight == {}

    fake.fail = SourceError("src", "down")
    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "failed")
    await asyncio.sleep(0)
    assert setup.cache.in_flight == {}

    fake.fail = None
    fake.gate = asyncio.Event()
    (tmp_path / "slow").mkdir()
    slow = Setup(tmp_path / "slow", fake, wait=0)
    with pytest.raises(FeedUnavailableError):
        await slow.cache.serve("players", "late")
    fake.gate.set()
    await slow.settle()
    assert slow.cache.in_flight == {}


@pytest.mark.anyio
async def test_a_failed_rebuild_keeps_the_stored_feed_and_is_listed_as_failed(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "p1")
    before = setup.stored()
    setup.now[0] = T + 2 * HOUR
    fake.fail = SourceError("src", "source down")

    served = await setup.cache.serve("players", "p1")
    await setup.settle()

    assert served == before
    assert setup.stored() == before
    failed = setup.store.failed_feed_builds()
    assert [(f.kind, f.feed_id, f.last_failure_reason) for f in failed] == [
        ("players", "p1", "source down")
    ]
    assert failed[0].last_failure == T + 2 * HOUR
    assert failed[0].last_build == T


@pytest.mark.anyio
async def test_does_not_rebuild_a_failed_feed_for_10_minutes_and_rebuilds_it_after(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "p1")
    failure_at = T + 2 * HOUR
    setup.now[0] = failure_at
    fake.fail = SourceError("src", "down")
    await setup.cache.serve("players", "p1")
    await setup.settle()
    assert fake.builds == 2

    setup.now[0] = failure_at + RETRY_AFTER - dt.timedelta(seconds=1)
    served = await setup.cache.serve("players", "p1")
    await setup.settle()
    assert served == body_of(1)
    assert fake.builds == 2

    fake.fail = None
    fake.version = 3
    setup.now[0] = failure_at + RETRY_AFTER
    await setup.cache.serve("players", "p1")
    await setup.settle()
    assert fake.builds == 3
    assert setup.stored() == body_of(3)


@pytest.mark.anyio
async def test_a_missing_feed_whose_build_failed_within_10_minutes_answers_unavailable_with_no_new_build(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.fail = SourceError("src", "down")
    setup = Setup(tmp_path, fake)
    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")
    assert fake.builds == 1

    setup.now[0] = T + RETRY_AFTER - dt.timedelta(seconds=1)
    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")
    assert fake.builds == 1

    fake.fail = None
    setup.now[0] = T + RETRY_AFTER
    assert await setup.cache.serve("players", "p1") == body_of(1)
    assert fake.builds == 2


@pytest.mark.anyio
async def test_records_an_unexpected_build_error_by_its_type_and_an_invalid_built_feed_as_not_written(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "p1")
    before = setup.stored()
    setup.now[0] = T + 2 * HOUR
    fake.fail = RuntimeError("boom")
    assert await setup.cache.serve("players", "p1") == before
    await setup.settle()
    failed = setup.store.feed_build("players", "p1")
    assert failed is not None
    assert failed.last_failure_reason == "unexpected error: RuntimeError"

    fake.fail = None
    fake.invalid = True
    setup.now[0] = T + 4 * HOUR
    assert await setup.cache.serve("players", "p1") == before
    await setup.settle()
    failed = setup.store.feed_build("players", "p1")
    assert failed is not None
    assert failed.last_failure_reason == "feed not written"
    assert setup.stored() == before


@pytest.mark.anyio
async def test_serve_time_additions_are_in_the_response_and_not_in_the_stored_file(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake("extras"))
    fake = Fake()
    setup.cache = FeedCache(tmp_path, setup.store, clock=lambda: T)
    setup.cache.register(
        fake.kind(lambda feed_id, feed: feed.model_copy(update={"extra": "hi"}))
    )
    stored_body = body_of(1)

    body = await setup.cache.serve("players", "p1")

    assert body == body_of(1, extra="hi")
    assert setup.stored() == stored_body
    assert FakeFeed.model_validate_json(setup.stored() or b"").extra is None


@pytest.mark.anyio
async def test_serves_the_stored_feed_without_additions_when_they_make_it_invalid(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = Setup(tmp_path, Fake("extras"))
    fake = Fake()
    setup.cache = FeedCache(tmp_path, setup.store, clock=lambda: T)
    setup.cache.register(
        fake.kind(lambda feed_id, feed: feed.model_copy(update={"version": "x"}))
    )

    with caplog.at_level(logging.ERROR):
        body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    assert "serve-time additions are invalid" in caplog.text


@pytest.mark.anyio
async def test_keeps_stored_feeds_and_build_times_across_a_restart_with_no_build(
    tmp_path: Path,
) -> None:
    await Setup(tmp_path, Fake()).cache.serve("players", "p1")
    fake = Fake()
    restarted = Setup(tmp_path, fake)

    await asyncio.sleep(0)
    body = await restarted.cache.serve("players", "p1")

    assert fake.builds == 0
    assert body == body_of(1)
    assert restarted.cache.in_flight == {}


@pytest.mark.anyio
async def test_serves_a_stored_feed_with_no_build_time_as_stale_and_rebuilds_it(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.version = 2
    setup = Setup(tmp_path, fake)
    publish_by_id(tmp_path, "players", FakeFeed, "p1", FakeFeed(id="p1", version=1))

    served = await setup.cache.serve("players", "p1")
    await setup.settle()

    assert served == body_of(1)
    assert fake.builds == 1
    assert setup.stored() == body_of(2)


@pytest.mark.anyio
async def test_treats_a_stored_file_that_fails_validation_as_missing_and_builds_it(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = Setup(tmp_path, Fake())
    setup.store.record_build("players", "p1", T)
    (tmp_path / "feeds" / "players").mkdir(parents=True)
    (tmp_path / "feeds" / "players" / "p1.json").write_bytes(b'{"id": 1}')

    with caplog.at_level(logging.ERROR):
        body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    assert setup.fake.builds == 1
    assert "stored file is invalid" in caplog.text


@pytest.mark.anyio
async def test_the_cleanup_deletes_only_invalid_ids_with_no_build_check_or_source_request(
    tmp_path: Path,
) -> None:
    players = Fake("players")
    players.keep_ids = {"ok1", "ok2"}
    teams = Fake("teams")
    setup = Setup(tmp_path, players)
    setup.cache.register(teams.kind())
    for kind in ("players", "teams"):
        for feed_id in ("ok1", "bad1", "bad2"):
            publish_by_id(
                tmp_path, kind, FakeFeed, feed_id, FakeFeed(id=feed_id, version=1)
            )
        for feed_id in ("ok1", "bad1", "bad3", "ok2"):
            setup.store.record_build(kind, feed_id, T)

    with respx.mock:
        setup.cache.cleanup()

    assert published_ids(tmp_path, "players") == {"ok1"}
    assert setup.store.feed_build_ids("players") == {"ok1", "ok2"}
    assert published_ids(tmp_path, "teams") == {"ok1", "bad1", "bad2"}
    assert setup.store.feed_build_ids("teams") == {"ok1", "bad1", "bad3", "ok2"}
    assert (players.builds, players.checks, teams.builds, teams.checks) == (0, 0, 0, 0)


def test_rejects_a_second_kind_with_the_same_name_and_a_kind_name_that_is_not_a_safe_id(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())

    with pytest.raises(ValueError, match="already registered"):
        setup.cache.register(Fake().kind())
    with pytest.raises(ValueError, match="safe id"):
        setup.cache.register(Fake("../x").kind())


def waiting(setup: Setup, value: bool = True) -> None:
    setup.cache._kinds["players"].wait_when_stale = lambda feed_id: value


async def stale_setup(path: Path, *, wait: float = 5.0, value: bool = True) -> Setup:
    fake = Fake()
    setup = Setup(path, fake)
    await setup.cache.serve("players", "p1")
    setup.cache._wait = wait
    setup.now[0] = T + 2 * HOUR
    fake.version = 2
    waiting(setup, value)
    return setup


@pytest.mark.anyio
async def test_a_stale_feed_whose_kind_waits_is_rebuilt_while_the_request_waits(
    tmp_path: Path,
) -> None:
    setup = await stale_setup(tmp_path)

    body = await setup.cache.serve("players", "p1")

    assert body == body_of(2)
    assert setup.fake.builds == 2
    assert setup.stored() == body_of(2)


@pytest.mark.anyio
async def test_concurrent_waiting_requests_share_one_rebuild(tmp_path: Path) -> None:
    setup = await stale_setup(tmp_path)
    setup.fake.gate = asyncio.Event()

    tasks = [asyncio.create_task(setup.cache.serve("players", "p1")) for _ in range(3)]
    for _ in range(5):
        await asyncio.sleep(0)
    setup.fake.gate.set()
    bodies = await asyncio.gather(*tasks)

    assert bodies == [body_of(2)] * 3
    assert setup.fake.builds == 2


@pytest.mark.anyio
async def test_a_waiting_request_is_served_the_stored_body_when_the_rebuild_fails(
    tmp_path: Path,
) -> None:
    setup = await stale_setup(tmp_path)
    setup.fake.fail = SourceError("x", "down")

    body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    assert setup.fake.builds == 2
    assert [f.kind for f in setup.store.failed_feed_builds()] == ["players"]


@pytest.mark.anyio
async def test_a_waiting_request_is_served_the_stored_body_when_the_rebuild_outlives_the_wait(
    tmp_path: Path,
) -> None:
    setup = await stale_setup(tmp_path, wait=0)
    setup.fake.gate = asyncio.Event()

    body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    task = setup.cache.in_flight[("players", "p1")]
    assert not task.cancelled()
    setup.fake.gate.set()
    await task
    await asyncio.sleep(0)
    assert setup.stored() == body_of(2)
    assert setup.cache.in_flight == {}


@pytest.mark.anyio
async def test_a_stale_feed_whose_wait_when_stale_is_false_is_served_at_once(
    tmp_path: Path,
) -> None:
    setup = await stale_setup(tmp_path, value=False)
    setup.fake.gate = asyncio.Event()

    body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    await asyncio.sleep(0)
    assert setup.fake.builds == 2
    assert setup.fake.running == 1
    setup.fake.gate.set()
    await setup.settle()


@pytest.mark.anyio
async def test_a_waiting_kind_serves_the_stored_feed_with_no_build_within_10_minutes_of_a_failure(
    tmp_path: Path,
) -> None:
    setup = await stale_setup(tmp_path)
    setup.store.record_build_failure("players", "p1", T + 2 * HOUR, "down")
    setup.now[0] = T + 2 * HOUR + RETRY_AFTER / 2

    body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    assert setup.fake.builds == 1


@pytest.mark.anyio
async def test_refresh_starts_one_build_without_waiting_and_joins_one_in_flight(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.gate = asyncio.Event()
    setup = Setup(tmp_path, fake)

    setup.cache.refresh("players", "p1")
    setup.cache.refresh("players", "p1")
    for _ in range(3):
        await asyncio.sleep(0)

    assert fake.builds == 1
    assert list(setup.cache.in_flight) == [("players", "p1")]
    fake.gate.set()
    await setup.settle()
    assert setup.stored() == body_of(1)
    assert setup.cache.in_flight == {}


@pytest.mark.anyio
async def test_serve_with_a_wait_override_of_0_serves_the_stored_body_of_a_stale_waiting_feed_at_once(
    tmp_path: Path,
) -> None:
    setup = await stale_setup(tmp_path, wait=60.0)
    setup.fake.gate = asyncio.Event()

    async with asyncio.timeout(1):
        body = await setup.cache.serve("players", "p1", wait=0)

    assert body == body_of(1)
    assert ("players", "p1") in setup.cache.in_flight
    setup.fake.gate.set()
    await setup.settle()
    assert setup.stored() == body_of(2)


@pytest.mark.anyio
async def test_serve_with_a_wait_override_of_0_answers_unavailable_at_once_for_a_missing_feed(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.gate = asyncio.Event()
    setup = Setup(tmp_path, fake, wait=60.0)

    assert setup.cache.wait == 60.0
    async with asyncio.timeout(1):
        with pytest.raises(FeedUnavailableError):
            await setup.cache.serve("players", "p1", wait=0)

    fake.gate.set()
    await setup.settle()
    assert setup.stored() == body_of(1)
