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
# - Every kind serves the stored feed through its model, not the stored bytes, when the serve-time additions are invalid; with no write and no build
# - With an identities provider a served feed carries the identity on every league side, nested and in lists, after the kind's serve_with additions, a served feed whose root is a league team object gets its logo, the stored file stays without it, and additions that make it invalid serve the stored feed through its model (ADR 0068, ADR 0073)
# - With an identities provider a stored player feed from before the season logos is served with them, valid, with no build and no source read, and the stored file stays without them (ADR 0070)
# - With no provider and no serve_with the body is the stored one byte for byte
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
# - A build whose kind depends on a missing feed builds that feed first and then itself
# - A fresh dependency is not rebuilt and a stale one is rebuilt before the build
# - A dependency build already in flight is joined: one build of it in total
# - Five dependent builds of five missing dependencies finish while at most 4 builds run at once
# - A build whose kind sets prepare builds every feed the hook ensures, in order, before itself
# - A feed the hook ensures that is fresh is not rebuilt
# - An exception raised by the hook is recorded as a failed build of the feed and never raised
# - Five builds whose hook waits on a gated feed finish while at most 4 builds run at once
# - A dependency inside its 10-minute backoff is not rebuilt and the dependent build still runs
# - A dependency id its kind does not know is skipped with no build
# - An exception raised while ensuring the dependency is recorded as a failed build of the dependent feed and never raised
# - after_publish is called once with the id and the feed after a stored build, and not when the build fails (ADR 0066)
# - A build that raises UnknownFeedError after its check learns the id answers unknown and records no failure, and a later request answers unknown with no build
# - status gives the kind's answer for an id with no build and None for a kind never registered
# - refresh starts one build without waiting, joins one in flight and leaves no task referenced
# - A build error that carries a non-empty string reason is recorded with it, in the build step and in the dependency step; one with an empty or non-string reason, or none, is recorded by its type
# - warm starts one build for a missing or stale feed without waiting, and none for a fresh feed, one in flight, an unknown id or a failure inside the 10-minute window (ADR 0055)
# - At most 16 builds are started: a new missing id answers unavailable, warm and refresh start nothing, a stale feed is served as stored and a dependency is used as stored (ADR 0062)
# - A build past its timeout is recorded as "build timed out", ends its task and keeps the stored feed (ADR 0062)
# - Serving a stored feed, or a feed after its build, sets its last served time to the clock, and an unavailable or unknown answer does not (ADR 0063)
# - prune_unserved deletes the file and row of a feed not served in 91 days and keeps one served 89 days ago, and a stored file with no row
# - prune_unserved skips an id with a build in flight and the kinds not given, and a pruned feed is built again on its next request
# - with_build_version stamps the current rules version of the kept season feeds, and is_current_build is true only for that version (ADR 0053)
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
from pydantic import BaseModel, HttpUrl

from app.feeds.games import FeedModel, GameTeam
from app.feeds.opponent import TeamColors, TeamLogo
from app.feeds.player import PlayerFeed
from app.jobs.on_demand import (
    BUILD_TIMEOUT_SECONDS,
    MAX_BUILDS,
    MAX_QUEUED_BUILDS,
    MISSING_WAIT_SECONDS,
    RETRY_AFTER,
    SEASON_BUILD_VERSION,
    Ensure,
    FeedCache,
    FeedKind,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
    is_current_build,
    with_build_version,
)
from app.jobs.playoffs_feed import PlayoffsBuildError
from app.sources.http import SourceError
from app.storage.feeds import publish_by_id, published_ids, read_by_id
from app.storage.state import StateStore, TeamIdentity
from tests.feeds.test_player import valid_player

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

    def kind(
        self,
        serve_with: object = None,
        depends_on: object = None,
        after_publish: object = None,
        prepare: object = None,
    ) -> FeedKind[FakeFeed]:
        return FeedKind(
            self.name,
            FakeFeed,
            check=self.check,
            build=self.build,
            is_fresh=lambda feed, built_at, now: now - built_at < HOUR,
            keep=self.keep,
            serve_with=serve_with,  # type: ignore[arg-type]
            depends_on=depends_on,  # type: ignore[arg-type]
            after_publish=after_publish,  # type: ignore[arg-type]
            prepare=prepare,  # type: ignore[arg-type]
        )


class Setup:
    def __init__(
        self,
        path: Path,
        fake: Fake,
        *,
        wait: float = 5.0,
        build_timeout: float = BUILD_TIMEOUT_SECONDS,
    ) -> None:
        self.path = path
        self.fake = fake
        self.now = [T]
        self.store = StateStore(path)
        self.store.migrate()
        self.cache = FeedCache(
            path,
            self.store,
            clock=lambda: self.now[0],
            wait=wait,
            build_timeout=build_timeout,
        )
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
async def test_a_default_kind_serves_the_stored_model_not_the_stored_bytes_when_the_additions_are_invalid(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    setup = Setup(tmp_path, Fake("extras"))
    fake = Fake()
    setup.cache = FeedCache(tmp_path, setup.store, clock=lambda: T)
    setup.cache.register(
        fake.kind(lambda feed_id, feed: feed.model_copy(update={"version": "x"}))
    )
    await setup.cache.serve("players", "p1")
    stored = b'{"id": "p1", "version": 1}'
    (tmp_path / "feeds" / "players" / "p1.json").write_bytes(stored)
    builds = fake.builds

    with caplog.at_level(logging.ERROR):
        body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    assert "serve-time additions are invalid" in caplog.text
    assert fake.builds == builds
    assert read_by_id(tmp_path, "players", "p1") == stored


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
    with pytest.raises(ValueError, match="safe id"):
        setup.cache.register(Fake("days\n").kind())


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
async def test_warm_starts_one_build_for_a_missing_feed_without_waiting(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.gate = asyncio.Event()
    setup = Setup(tmp_path, fake)

    setup.cache.warm("players", "p1")
    setup.cache.warm("players", "p1")
    for _ in range(3):
        await asyncio.sleep(0)

    assert fake.builds == 1
    assert setup.stored() is None
    fake.gate.set()
    await setup.settle()
    assert setup.stored() == body_of(1)


@pytest.mark.anyio
async def test_warm_starts_no_build_for_a_fresh_feed(tmp_path: Path) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "p1")
    setup.now[0] = T + dt.timedelta(minutes=5)

    setup.cache.warm("players", "p1")
    await setup.settle()

    assert fake.builds == 1


@pytest.mark.anyio
async def test_warm_starts_one_build_for_a_stale_feed_and_keeps_serving_the_stored_one(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "p1")
    setup.now[0] = T + 2 * HOUR
    fake.version = 2

    setup.cache.warm("players", "p1")
    assert setup.stored() == body_of(1)
    await setup.settle()

    assert fake.builds == 2
    assert setup.stored() == body_of(2)


@pytest.mark.anyio
async def test_warm_starts_no_build_inside_the_retry_window_of_a_failure_and_one_after(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.fail = SourceError("src", "down")
    setup = Setup(tmp_path, fake)
    setup.cache.warm("players", "p1")
    await setup.settle()
    assert fake.builds == 1

    setup.now[0] = T + RETRY_AFTER - dt.timedelta(seconds=1)
    setup.cache.warm("players", "p1")
    await setup.settle()
    assert fake.builds == 1

    setup.now[0] = T + RETRY_AFTER
    fake.fail = None
    setup.cache.warm("players", "p1")
    await setup.settle()
    assert fake.builds == 2
    assert setup.stored() == body_of(1)


@pytest.mark.anyio
async def test_warm_starts_nothing_for_an_id_its_kind_does_not_know(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.status = IdStatus.UNKNOWN
    setup = Setup(tmp_path, fake)

    setup.cache.warm("players", "p1")
    await setup.settle()

    assert fake.builds == 0


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


class Dependent:
    """A dependent kind (players) over a dependency kind (teams) in one cache."""

    def __init__(
        self, path: Path, *, wait: float = 5.0, pair: object = ("teams", "t1")
    ) -> None:
        self.teams = Fake("teams")
        self.players = Fake("players")
        self.order: list[str] = []
        self.setup = Setup(path, self.teams, wait=wait)
        self.pairs: dict[str, tuple[str, str] | None] = {}
        self.pair = pair
        self.setup.cache.register(
            self.players.kind(depends_on=lambda feed_id: self.depends(feed_id))
        )
        for fake in (self.teams, self.players):
            self._record(fake)

    def depends(self, feed_id: str) -> tuple[str, str] | None:
        if isinstance(self.pair, Exception):
            raise self.pair
        if feed_id in self.pairs:
            return self.pairs[feed_id]
        return self.pair  # type: ignore[return-value]

    def _record(self, fake: Fake) -> None:
        build = fake.build

        async def recorded(feed_id: str) -> FakeFeed:
            self.order.append(f"{fake.name}:{feed_id}")
            return await build(feed_id)

        fake.build = recorded  # type: ignore[method-assign]
        self.setup.cache._kinds[fake.name].build = recorded


@pytest.mark.anyio
async def test_a_dependent_build_builds_its_missing_dependency_first(
    tmp_path: Path,
) -> None:
    dep = Dependent(tmp_path)

    body = await dep.setup.cache.serve("players", "p1")

    assert dep.order == ["teams:t1", "players:p1"]
    assert body == body_of(1)
    assert read_by_id(tmp_path, "teams", "t1") == body_of(1, "t1")


@pytest.mark.anyio
async def test_a_fresh_dependency_is_not_rebuilt_and_a_stale_one_is(
    tmp_path: Path,
) -> None:
    dep = Dependent(tmp_path)
    await dep.setup.cache.serve("teams", "t1")
    dep.order.clear()

    await dep.setup.cache.serve("players", "p1")
    assert dep.order == ["players:p1"]

    dep.setup.now[0] = T + 2 * HOUR
    dep.order.clear()
    dep.players.version = 2
    await dep.setup.cache.serve("players", "p1")
    await dep.setup.settle()

    assert dep.order == ["teams:t1", "players:p1"]
    build = dep.setup.store.feed_build("teams", "t1")
    assert build is not None and build.last_build == T + 2 * HOUR


@pytest.mark.anyio
async def test_a_dependency_build_in_flight_is_joined(tmp_path: Path) -> None:
    dep = Dependent(tmp_path)
    dep.teams.gate = asyncio.Event()
    first = asyncio.create_task(dep.setup.cache.serve("teams", "t1"))
    for _ in range(5):
        await asyncio.sleep(0)
    second = asyncio.create_task(dep.setup.cache.serve("players", "p1"))
    for _ in range(5):
        await asyncio.sleep(0)

    assert dep.players.builds == 0
    dep.teams.gate.set()
    await asyncio.gather(first, second)

    assert dep.teams.builds == 1
    assert dep.players.builds == 1


@pytest.mark.anyio
async def test_dependent_builds_of_missing_dependencies_never_deadlock_under_the_limit(
    tmp_path: Path,
) -> None:
    dep = Dependent(tmp_path)
    dep.pairs = {f"p{n}": ("teams", f"t{n}") for n in range(5)}
    dep.teams.gate = asyncio.Event()
    tasks = [
        asyncio.create_task(dep.setup.cache.serve("players", f"p{n}")) for n in range(5)
    ]
    for _ in range(20):
        await asyncio.sleep(0)

    dep.teams.gate.set()
    bodies = await asyncio.wait_for(asyncio.gather(*tasks), 5)

    assert bodies == [body_of(1, f"p{n}") for n in range(5)]
    assert dep.teams.builds == 5
    assert dep.teams.peak <= MAX_BUILDS
    assert dep.players.peak <= MAX_BUILDS


@pytest.mark.anyio
async def test_a_dependency_inside_its_backoff_is_not_rebuilt_and_the_dependent_build_runs(
    tmp_path: Path,
) -> None:
    dep = Dependent(tmp_path)
    dep.setup.store.record_build_failure("teams", "t1", T, "down")
    dep.setup.now[0] = T + RETRY_AFTER - dt.timedelta(seconds=1)

    body = await dep.setup.cache.serve("players", "p1")

    assert dep.teams.builds == 0
    assert dep.order == ["players:p1"]
    assert body == body_of(1)


@pytest.mark.anyio
async def test_a_dependency_id_its_kind_does_not_know_is_skipped_with_no_build(
    tmp_path: Path,
) -> None:
    dep = Dependent(tmp_path)
    dep.teams.status = IdStatus.UNKNOWN

    await dep.setup.cache.serve("players", "p1")

    assert dep.teams.builds == 0
    assert dep.players.builds == 1


@pytest.mark.anyio
async def test_an_error_ensuring_the_dependency_is_recorded_as_a_failed_build_and_never_raised(
    tmp_path: Path,
) -> None:
    dep = Dependent(tmp_path, pair=RuntimeError("boom"))

    with pytest.raises(FeedUnavailableError):
        await dep.setup.cache.serve("players", "p1")

    assert dep.players.builds == 0
    state = dep.setup.store.feed_build("players", "p1")
    assert state is not None
    assert state.last_failure_reason == "unexpected error: RuntimeError"
    assert dep.setup.stored("p1") is None


class Prepared:
    """A kind (players) whose prepare hook ensures feeds of another kind (teams)."""

    def __init__(self, path: Path, ids: dict[str, list[str]] | None = None) -> None:
        self.teams = Fake("teams")
        self.players = Fake("players")
        self.order: list[str] = []
        self.ids = ids or {}
        self.error: Exception | None = None
        self.setup = Setup(path, self.teams)
        self.setup.cache.register(self.players.kind(prepare=self.prepare))
        for fake in (self.teams, self.players):
            self._record(fake)

    async def prepare(self, feed_id: str, ensure: Ensure) -> None:
        if self.error is not None:
            raise self.error
        for team in self.ids.get(feed_id, ["t1", "t2"]):
            await ensure("teams", team)

    def _record(self, fake: Fake) -> None:
        build = fake.build

        async def recorded(feed_id: str) -> FakeFeed:
            self.order.append(f"{fake.name}:{feed_id}")
            return await build(feed_id)

        fake.build = recorded  # type: ignore[method-assign]
        self.setup.cache._kinds[fake.name].build = recorded


@pytest.mark.anyio
async def test_a_kind_with_prepare_builds_every_feed_it_ensures_before_itself(
    tmp_path: Path,
) -> None:
    prep = Prepared(tmp_path)

    body = await prep.setup.cache.serve("players", "p1")

    assert prep.order == ["teams:t1", "teams:t2", "players:p1"]
    assert body == body_of(1)
    assert read_by_id(tmp_path, "teams", "t2") == body_of(1, "t2")


@pytest.mark.anyio
async def test_prepare_ensuring_a_fresh_feed_rebuilds_nothing(tmp_path: Path) -> None:
    prep = Prepared(tmp_path)
    await prep.setup.cache.serve("teams", "t1")
    await prep.setup.cache.serve("teams", "t2")
    prep.order.clear()

    await prep.setup.cache.serve("players", "p1")

    assert prep.order == ["players:p1"]


@pytest.mark.anyio
async def test_an_error_in_prepare_is_recorded_as_a_failed_build_and_never_raised(
    tmp_path: Path,
) -> None:
    prep = Prepared(tmp_path)
    prep.error = RuntimeError("boom")

    with pytest.raises(FeedUnavailableError):
        await prep.setup.cache.serve("players", "p1")

    assert prep.players.builds == 0
    state = prep.setup.store.feed_build("players", "p1")
    assert state is not None
    assert state.last_failure_reason == "unexpected error: RuntimeError"
    assert prep.setup.stored("p1") is None


@pytest.mark.anyio
async def test_prepare_runs_before_the_build_takes_a_slot(tmp_path: Path) -> None:
    prep = Prepared(tmp_path, {f"p{n}": [f"t{n}"] for n in range(5)})
    prep.teams.gate = asyncio.Event()
    tasks = [
        asyncio.create_task(prep.setup.cache.serve("players", f"p{n}"))
        for n in range(5)
    ]
    for _ in range(20):
        await asyncio.sleep(0)

    prep.teams.gate.set()
    bodies = await asyncio.wait_for(asyncio.gather(*tasks), 5)

    assert bodies == [body_of(1, f"p{n}") for n in range(5)]
    assert prep.teams.builds == 5
    assert prep.teams.peak <= MAX_BUILDS
    assert prep.players.peak <= MAX_BUILDS


@pytest.mark.anyio
async def test_status_gives_the_kinds_answer_with_no_build_and_none_for_an_unregistered_kind(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)

    known = setup.cache.status("players", "p1")
    fake.status = IdStatus.UNKNOWN
    unknown = setup.cache.status("players", "p1")
    missing = setup.cache.status("nobody", "p1")

    assert (known, unknown, missing) == (IdStatus.KNOWN, IdStatus.UNKNOWN, None)
    assert fake.builds == 0
    assert setup.cache.in_flight == {}
    assert setup.store.feed_build("players", "p1") is None


class LearnsUnknown(Fake):
    """A kind whose build finds out that the id is unknown."""

    async def build(self, feed_id: str) -> FakeFeed:
        self.builds += 1
        self.status = IdStatus.UNKNOWN
        raise UnknownFeedError(feed_id)


@pytest.mark.anyio
async def test_a_build_that_learns_the_id_is_unknown_answers_unknown_and_records_no_failure(
    tmp_path: Path,
) -> None:
    fake = LearnsUnknown()
    setup = Setup(tmp_path, fake)

    with pytest.raises(UnknownFeedError):
        await setup.cache.serve("players", "p1")

    assert fake.builds == 1
    assert setup.store.feed_build("players", "p1") is None
    assert setup.stored() is None

    with pytest.raises(UnknownFeedError):
        await setup.cache.serve("players", "p1")

    assert fake.builds == 1


@pytest.mark.anyio
async def test_after_publish_is_called_once_with_the_id_and_feed_after_a_publish(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    setup.cache = FeedCache(tmp_path, setup.store, clock=lambda: setup.now[0])
    published: list[tuple[str, FakeFeed, bytes | None]] = []

    def after_publish(feed_id: str, feed: FakeFeed) -> None:
        # The feed is already stored when the hook runs.
        published.append((feed_id, feed, setup.stored(feed_id)))

    setup.cache.register(fake.kind(after_publish=after_publish))

    await setup.cache.serve("players", "p1")
    await setup.settle()
    await setup.cache.serve("players", "p1")

    assert len(published) == 1
    feed_id, feed, stored = published[0]
    assert (feed_id, feed) == ("p1", FakeFeed(id="p1", version=1))
    assert stored == body_of(1)


@pytest.mark.anyio
async def test_after_publish_is_not_called_when_the_build_fails(
    tmp_path: Path,
) -> None:
    fake = Fake()
    fake.fail = RuntimeError("down")
    setup = Setup(tmp_path, fake)
    setup.cache = FeedCache(tmp_path, setup.store, clock=lambda: setup.now[0])
    published: list[str] = []
    setup.cache.register(
        fake.kind(after_publish=lambda feed_id, feed: published.append(feed_id))
    )

    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")
    await setup.settle()

    assert published == []


class Versioned(BaseModel):
    build_version: int | None = None


def test_with_build_version_stamps_the_current_version_and_is_current_build_accepts_only_it() -> (
    None
):
    unstamped = Versioned()

    stamped = with_build_version(unstamped)

    assert unstamped.build_version is None
    assert stamped.build_version == SEASON_BUILD_VERSION
    assert is_current_build(stamped) is True
    assert is_current_build(unstamped) is False
    assert is_current_build(Versioned(build_version=SEASON_BUILD_VERSION + 1)) is False


class EmptyReasonError(Exception):
    reason = ""


class NumberReasonError(Exception):
    reason = 3


@pytest.mark.anyio
async def test_records_a_build_error_by_its_reason(tmp_path: Path) -> None:
    fake = Fake()
    fake.fail = PlayoffsBuildError("the 2005 postseason is not complete")
    setup = Setup(tmp_path, fake)

    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")

    failed = setup.store.feed_build("players", "p1")
    assert failed is not None
    assert failed.last_failure_reason == "the 2005 postseason is not complete"


@pytest.mark.anyio
@pytest.mark.parametrize("error", [EmptyReasonError("x"), NumberReasonError("x")])
async def test_records_an_error_with_an_empty_or_non_string_reason_by_its_type(
    tmp_path: Path, error: Exception
) -> None:
    fake = Fake()
    fake.fail = error
    setup = Setup(tmp_path, fake)

    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")

    failed = setup.store.feed_build("players", "p1")
    assert failed is not None
    assert failed.last_failure_reason == f"unexpected error: {type(error).__name__}"


@pytest.mark.anyio
async def test_records_a_dependency_error_by_its_reason(tmp_path: Path) -> None:
    dep = Dependent(tmp_path, pair=PlayoffsBuildError("no standings"))

    with pytest.raises(FeedUnavailableError):
        await dep.setup.cache.serve("players", "p1")

    state = dep.setup.store.feed_build("players", "p1")
    assert state is not None
    assert state.last_failure_reason == "no standings"


def test_queues_at_most_16_builds_and_times_a_build_out_after_60_seconds() -> None:
    assert MAX_QUEUED_BUILDS == 16
    assert BUILD_TIMEOUT_SECONDS == 60


async def fill(setup: Setup, count: int = MAX_QUEUED_BUILDS) -> None:
    setup.fake.gate = asyncio.Event()
    for n in range(count):
        setup.cache.refresh("players", f"p{n}")
    await asyncio.sleep(0)


@pytest.mark.anyio
async def test_a_request_for_a_new_id_with_16_builds_started_answers_unavailable_and_starts_nothing(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    await fill(setup)

    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p16")

    assert ("players", "p16") not in setup.cache.in_flight
    assert len(setup.cache.in_flight) == MAX_QUEUED_BUILDS
    assert setup.store.feed_build("players", "p16") is None
    assert setup.fake.gate is not None
    setup.fake.gate.set()
    await setup.settle()
    assert setup.cache.in_flight == {}
    assert setup.fake.builds == MAX_QUEUED_BUILDS


@pytest.mark.anyio
async def test_warm_and_refresh_start_nothing_with_16_builds_started(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    await fill(setup)

    setup.cache.warm("players", "p16")
    setup.cache.refresh("players", "p17")

    assert len(setup.cache.in_flight) == MAX_QUEUED_BUILDS
    assert ("players", "p16") not in setup.cache.in_flight
    assert ("players", "p17") not in setup.cache.in_flight
    assert setup.fake.gate is not None
    setup.fake.gate.set()
    await setup.settle()
    assert setup.fake.builds == MAX_QUEUED_BUILDS


@pytest.mark.anyio
async def test_a_stale_feed_with_16_builds_started_is_served_as_stored_with_no_build(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    await setup.cache.serve("players", "p0")
    setup.now[0] = T + 2 * HOUR
    fake.gate = asyncio.Event()
    for n in range(1, MAX_QUEUED_BUILDS + 1):
        setup.cache.refresh("players", f"p{n}")
    await asyncio.sleep(0)

    body = await setup.cache.serve("players", "p0")

    assert body == body_of(1, "p0")
    assert ("players", "p0") not in setup.cache.in_flight
    assert len(setup.cache.in_flight) == MAX_QUEUED_BUILDS
    fake.gate.set()
    await setup.settle()


@pytest.mark.anyio
async def test_a_dependency_with_16_builds_started_is_used_as_stored(
    tmp_path: Path,
) -> None:
    dep = Dependent(tmp_path)
    dep.pairs = {"p1": ("teams", "tdep")}
    dep.teams.gate = asyncio.Event()
    for n in range(MAX_QUEUED_BUILDS - 1):
        dep.setup.cache.refresh("teams", f"t{n}")
    await asyncio.sleep(0)

    task = asyncio.create_task(dep.setup.cache.serve("players", "p1"))
    for _ in range(20):
        await asyncio.sleep(0)

    assert ("teams", "tdep") not in dep.setup.cache.in_flight
    dep.teams.gate.set()
    body = await asyncio.wait_for(task, 5)

    assert body == body_of(1, "p1")
    assert dep.teams.builds == MAX_QUEUED_BUILDS - 1
    assert dep.players.builds == 1


@pytest.mark.anyio
async def test_a_build_past_its_timeout_is_recorded_as_build_timed_out_and_its_task_ends(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake, build_timeout=0.01)
    await setup.cache.serve("players", "p0")
    fake.gate = asyncio.Event()

    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")
    await setup.settle()

    failure = setup.store.feed_build("players", "p1")
    assert failure is not None
    assert failure.last_failure_reason == "build timed out"
    assert setup.cache.in_flight == {}
    assert fake.running == 0
    assert setup.stored("p0") == body_of(1, "p0")


DAY = dt.timedelta(days=1)


@pytest.mark.anyio
async def test_serving_a_stored_feed_updates_its_last_served_to_the_clock(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    publish_by_id(tmp_path, "players", FakeFeed, "p1", FakeFeed(id="p1", version=7))
    setup.store.record_build("players", "p1", T)
    assert setup.store.last_served("players", "p1") is None
    setup.now[0] = T + HOUR / 2

    await setup.cache.serve("players", "p1")

    assert setup.store.last_served("players", "p1") == T + HOUR / 2


@pytest.mark.anyio
async def test_serving_a_feed_after_its_build_updates_its_last_served_to_the_clock(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    setup.now[0] = T + DAY

    await setup.cache.serve("players", "p1")

    assert setup.store.last_served("players", "p1") == T + DAY


@pytest.mark.anyio
async def test_an_unavailable_or_unknown_answer_does_not_update_last_served(
    tmp_path: Path,
) -> None:
    fake = Fake()
    setup = Setup(tmp_path, fake)
    setup.store.record_build("players", "p1", T)
    setup.now[0] = T + DAY

    fake.status = IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await setup.cache.serve("players", "p1")
    fake.status = IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")
    fake.status = IdStatus.KNOWN
    fake.fail = SourceError("scoreboard", "request failed")
    with pytest.raises(FeedUnavailableError):
        await setup.cache.serve("players", "p1")

    assert setup.store.last_served("players", "p1") is None


@pytest.mark.anyio
async def test_prune_unserved_deletes_the_file_and_row_of_a_feed_not_served_in_91_days_and_keeps_one_served_89_days_ago(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    for feed_id, age in [("old", 91), ("new", 89), ("built", 91)]:
        publish_by_id(
            tmp_path, "players", FakeFeed, feed_id, FakeFeed(id=feed_id, version=1)
        )
        setup.store.record_build("players", feed_id, T - 200 * DAY)
        if feed_id != "built":
            setup.store.touch_feed_build("players", feed_id, T - age * DAY)
    setup.store.record_build("players", "built", T - 91 * DAY)

    with respx.mock:
        setup.cache.prune_unserved(["players"], T)

    assert published_ids(tmp_path, "players") == {"new"}
    assert setup.store.feed_build_ids("players") == {"new"}
    assert setup.fake.builds == 0


@pytest.mark.anyio
async def test_prune_unserved_deletes_a_stored_file_with_no_build_row(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    publish_by_id(tmp_path, "players", FakeFeed, "p1", FakeFeed(id="p1", version=1))

    setup.cache.prune_unserved(["players"], T)

    assert published_ids(tmp_path, "players") == set()


@pytest.mark.anyio
async def test_prune_unserved_skips_an_id_with_a_build_in_flight_and_kinds_not_given(
    tmp_path: Path,
) -> None:
    fake = Fake()
    other = Fake("teams")
    setup = Setup(tmp_path, fake)
    setup.cache.register(other.kind())
    for kind in ("players", "teams"):
        for feed_id in ("p1", "p2"):
            publish_by_id(
                tmp_path, kind, FakeFeed, feed_id, FakeFeed(id=feed_id, version=1)
            )
            setup.store.record_build(kind, feed_id, T - 100 * DAY)
    fake.gate = asyncio.Event()
    setup.cache.refresh("players", "p1")
    await asyncio.sleep(0)

    setup.cache.prune_unserved(["players"], T)

    assert published_ids(tmp_path, "players") == {"p1"}
    assert setup.store.feed_build_ids("players") == {"p1"}
    assert published_ids(tmp_path, "teams") == {"p1", "p2"}
    assert setup.store.feed_build_ids("teams") == {"p1", "p2"}
    fake.gate.set()
    await setup.settle()


@pytest.mark.anyio
async def test_a_pruned_feed_is_built_again_on_its_next_request(
    tmp_path: Path,
) -> None:
    setup = Setup(tmp_path, Fake())
    await setup.cache.serve("players", "p1")
    setup.now[0] = T + 91 * DAY

    setup.cache.prune_unserved(["players"], setup.now[0])
    assert setup.stored() is None
    assert setup.store.feed_build("players", "p1") is None
    body = await setup.cache.serve("players", "p1")

    assert body == body_of(1)
    assert setup.fake.builds == 2


class Sided(FeedModel):
    """A feed with a league team object at its root, a nested side and a list of sides."""

    id: str
    code: str
    logo: TeamLogo | None = None
    next: GameTeam
    sides: list[GameTeam]
    extra: str | None = None


OKC = TeamIdentity(
    code="OKC",
    logo=TeamLogo(light=HttpUrl("https://example.com/okc.svg"), dark=None),
    colors=TeamColors(primary="#007AC1", secondary=None),
)


def sided_kind(serve_with: object = None) -> FeedKind[Sided]:
    async def build(feed_id: str) -> Sided:
        side = GameTeam(code="OKC", name="Thunder", city="Oklahoma City")
        return Sided(id=feed_id, code="OKC", next=side, sides=[side, side])

    return FeedKind(
        "sided",
        Sided,
        check=lambda feed_id: IdStatus.KNOWN,
        build=build,
        is_fresh=lambda feed, built_at, now: now - built_at < HOUR,
        keep=lambda feed_id: True,
        serve_with=serve_with,  # type: ignore[arg-type]
    )


@pytest.mark.anyio
async def test_an_identities_provider_stamps_every_side_after_the_additions(
    tmp_path: Path,
) -> None:
    store = StateStore(tmp_path)
    store.migrate()
    cache = FeedCache(tmp_path, store, clock=lambda: T, identities=lambda: {"OKC": OKC})
    cache.register(
        sided_kind(lambda feed_id, feed: feed.model_copy(update={"extra": "hi"}))
    )

    served = Sided.model_validate_json(await cache.serve("sided", "s1"))

    assert served.extra == "hi"
    assert served.logo == OKC.logo
    assert served.next.logo == OKC.logo
    assert served.next.colors == OKC.colors
    assert [side.logo for side in served.sides] == [OKC.logo, OKC.logo]
    stored = Sided.model_validate_json(read_by_id(tmp_path, "sided", "s1") or b"")
    assert stored.logo is None
    assert stored.next.logo is None and stored.extra is None


@pytest.mark.anyio
async def test_an_identities_provider_adds_the_season_logos_to_a_stored_player_feed_from_before(
    tmp_path: Path,
) -> None:
    store = StateStore(tmp_path)
    store.migrate()
    payload = valid_player()
    rows = payload["seasons"]["regular"]["perGame"]
    rows[0]["teams"], rows[0]["seasonCodes"] = ["OKC"], ["OKC"]
    stored_body = PlayerFeed.model_validate(payload).model_dump_json(by_alias=True)
    feeds_dir = tmp_path / "feeds" / "players"
    feeds_dir.mkdir(parents=True)
    (feeds_dir / "p1.json").write_bytes(stored_body.encode())
    store.record_build("players", "p1", T)
    builds: list[str] = []

    async def build(feed_id: str) -> PlayerFeed:
        builds.append(feed_id)
        raise AssertionError("a fresh feed is never built")

    cache = FeedCache(tmp_path, store, clock=lambda: T, identities=lambda: {"OKC": OKC})
    cache.register(
        FeedKind(
            "players",
            PlayerFeed,
            check=lambda feed_id: IdStatus.KNOWN,
            build=build,
            is_fresh=lambda feed, built_at, now: now - built_at < HOUR,
            keep=lambda feed_id: True,
        )
    )

    with respx.mock:
        body = await cache.serve("players", "p1")

    served = PlayerFeed.model_validate_json(body)
    per_game = served.seasons.regular.per_game
    assert per_game[0].logos == [OKC.logo]
    assert per_game[1].logos == [None]
    assert builds == []
    assert read_by_id(tmp_path, "players", "p1") == stored_body.encode()


@pytest.mark.anyio
async def test_with_no_provider_and_no_serve_with_the_body_is_the_stored_one(
    tmp_path: Path,
) -> None:
    store = StateStore(tmp_path)
    store.migrate()
    cache = FeedCache(tmp_path, store, clock=lambda: T)
    cache.register(sided_kind())

    body = await cache.serve("sided", "s1")

    assert body == read_by_id(tmp_path, "sided", "s1")


@pytest.mark.anyio
async def test_additions_that_make_a_stamped_feed_invalid_serve_the_stored_body(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = StateStore(tmp_path)
    store.migrate()
    cache = FeedCache(tmp_path, store, clock=lambda: T, identities=lambda: {"OKC": OKC})
    cache.register(
        sided_kind(lambda feed_id, feed: feed.model_copy(update={"code": 5}))
    )

    with caplog.at_level(logging.ERROR):
        body = await cache.serve("sided", "s1")

    assert body == read_by_id(tmp_path, "sided", "s1")
    assert "serve-time additions are invalid" in caplog.text
