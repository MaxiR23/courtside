# api/app/jobs/on_demand.py
#
# On-demand feed cache: builds a feed when it is requested, serves the stored feed when it is fresh,
# and rebuilds a stale one in the background. The clock and the wait are injected so tests run without real time.
# It must only be used from async code in the event loop. A kind may depend on another feed: that feed is
# built first when missing or stale, before the build takes one of the build slots. A build may find that
# its id is unknown: it raises UnknownFeedError after the kind's check learns it, and the request answers unknown.
#
# A failed build or dependency is recorded with the error's own reason when it carries a non-empty one,
# else with its type.
#
# At most MAX_QUEUED_BUILDS builds are started at once, and a build is stopped after BUILD_TIMEOUT_SECONDS
# and recorded as "build timed out" (ADR 0062).
#
# A kind may set after_publish: it is called with the id and the feed once a build
# has been stored (ADR 0066).
#
# A served feed carries the team identities (logo and colors) on every league team
# object in it, put there when it is served and never stored, so a kept feed picks up
# a new logo with no rebuild (ADR 0068).
#
# When the serve-time additions of any kind are invalid, the feed is served as its model reads the
# stored file, never as the stored bytes, so a retired field is never served (ADR 0073).
#
# prune_unserved deletes the stored file and build row of the ids of the given kinds not served in
# KEPT_RETENTION; they are built again on their next request (ADR 0063).
#
# SEE: docs/source-rules.md, docs/adr/0020-source-rules.md, docs/adr/0062-bounded-upstream-reads-and-on-demand-builds.md,
# docs/adr/0063-bounded-state-and-kept-feeds.md,
# docs/adr/0073-no-champion-record-or-point-differential-in-the-playoffs-feed.md

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Iterable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from app.jobs.scheduler import utc_now
from app.jobs.team_identity import with_identities
from app.sources.http import SourceError
from app.storage.feeds import (
    GAME_ID,
    delete_by_id,
    publish_by_id,
    published_ids,
    read_by_id,
)
from app.storage.state import StateStore, TeamIdentity

logger = logging.getLogger(__name__)

MISSING_WAIT_SECONDS = 20.0
MAX_BUILDS = 4
MAX_QUEUED_BUILDS = 16
BUILD_TIMEOUT_SECONDS = 60.0
BUILD_TIMED_OUT = "build timed out"
RETRY_AFTER = dt.timedelta(minutes=10)

# The rules version of the kept season feeds (ADR 0053). Bump it in any change to
# the rules a past season is built by: a stored feed of another or no version is
# then stale, rebuilt on its next request, and served as stored until then. The
# franchise names, the past calendars and the stored past game players carry it too
# (ADR 0055).
# A kind may carry its own version on top of it (ADR 0061).
SEASON_BUILD_VERSION = 3

# How long a kept feed may go unserved before the daily cleanup deletes it (ADR 0063).
KEPT_RETENTION = dt.timedelta(days=90)


def failure_reason(error: Exception) -> str:
    """The reason a failed build is recorded with: the error's own non-empty
    string reason, else its type."""
    reason = getattr(error, "reason", None)
    if isinstance(reason, str) and reason:
        return reason
    return f"unexpected error: {type(error).__name__}"


def with_build_version[M: BaseModel](feed: M, version: int = SEASON_BUILD_VERSION) -> M:
    """The season feed stamped with the current rules version."""
    return feed.model_copy(update={"build_version": version})


def is_current_build(feed: BaseModel, version: int = SEASON_BUILD_VERSION) -> bool:
    """Whether a kept season feed was built by the current rules."""
    return getattr(feed, "build_version", None) == version


class IdStatus(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    NOT_READY = "not-ready"


class UnknownFeedError(Exception):
    """The id is not one of its kind's ids (rule I)."""


class FeedUnavailableError(Exception):
    """The feed cannot be served now: not ready, build failed, or past the wait."""


class FeedKind[M: BaseModel]:
    def __init__(
        self,
        name: str,
        model: type[M],
        *,
        check: Callable[[str], IdStatus],
        build: Callable[[str], Awaitable[M]],
        is_fresh: Callable[[M, dt.datetime, dt.datetime], bool],
        keep: Callable[[str], bool],
        serve_with: Callable[[str, M], M] | None = None,
        wait_when_stale: Callable[[str], bool] | None = None,
        depends_on: Callable[[str], tuple[str, str] | None] | None = None,
        after_publish: Callable[[str, M], None] | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.check = check
        self.build = build
        self.is_fresh = is_fresh
        self.keep = keep
        self.serve_with = serve_with
        self.wait_when_stale = wait_when_stale
        self.depends_on = depends_on
        self.after_publish = after_publish


class FeedCache:
    def __init__(
        self,
        data_dir: Path,
        store: StateStore,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
        wait: float = MISSING_WAIT_SECONDS,
        build_timeout: float = BUILD_TIMEOUT_SECONDS,
        identities: Callable[[], Mapping[str, TeamIdentity]] | None = None,
    ) -> None:
        self._identities = identities
        self._data_dir = data_dir
        self._store = store
        self._clock = clock
        self._wait = wait
        self._build_timeout = build_timeout
        self.in_flight: dict[tuple[str, str], asyncio.Task[bool]] = {}
        self._builds = asyncio.Semaphore(MAX_BUILDS)
        self._kinds: dict[str, FeedKind[Any]] = {}

    def register(self, kind: FeedKind[Any]) -> None:
        if not GAME_ID.fullmatch(kind.name):
            raise ValueError(f"feed kind name is not a safe id: {kind.name!r}")
        if kind.name in self._kinds:
            raise ValueError(f"feed kind already registered: {kind.name}")
        self._kinds[kind.name] = kind

    def status(self, kind: str, feed_id: str) -> IdStatus | None:
        """The kind's status of an id, or None when no such kind is registered.
        Builds nothing and reads no source."""
        feed_kind = self._kinds.get(kind)
        return None if feed_kind is None else feed_kind.check(feed_id)

    def _full(self) -> bool:
        return len(self.in_flight) >= MAX_QUEUED_BUILDS

    @property
    def wait(self) -> float:
        """The configured wait of a request, in seconds."""
        return self._wait

    async def serve(
        self, kind: str, feed_id: str, *, wait: float | None = None
    ) -> bytes:
        budget = self._wait if wait is None else wait
        feed_kind = self._kinds[kind]
        status = feed_kind.check(feed_id)
        if status is IdStatus.UNKNOWN:
            raise UnknownFeedError(f"{kind} {feed_id}")
        if status is IdStatus.NOT_READY:
            raise FeedUnavailableError(f"{kind} {feed_id} is not ready")

        now = self._clock()
        body = read_by_id(self._data_dir, kind, feed_id)
        state = self._store.feed_build(kind, feed_id)
        feed: BaseModel | None = None
        if body is not None:
            try:
                feed = feed_kind.model.model_validate_json(body)
            except ValidationError:
                logger.error("feed %s %s stored file is invalid", kind, feed_id)
                body = None
        last_build = state.last_build if state else None
        last_failure = state.last_failure if state else None
        retrying = last_failure is not None and now - last_failure < RETRY_AFTER
        key = (kind, feed_id)

        if body is not None and feed is not None:
            fresh = last_build is not None and feed_kind.is_fresh(feed, last_build, now)
            current = self.in_flight.get(key)
            if not fresh and current is None and not retrying and not self._full():
                current = self._start(feed_kind, feed_id)
            if (
                not fresh
                and current is not None
                and feed_kind.wait_when_stale is not None
                and feed_kind.wait_when_stale(feed_id)
            ):
                try:
                    ok = await asyncio.wait_for(asyncio.shield(current), budget)
                except TimeoutError:
                    ok = False
                if ok:
                    rebuilt = read_by_id(self._data_dir, kind, feed_id)
                    if rebuilt is not None:
                        try:
                            feed = feed_kind.model.model_validate_json(rebuilt)
                        except ValidationError:
                            pass
                        else:
                            body = rebuilt
            self._store.touch_feed_build(kind, feed_id, self._clock())
            return self._respond(feed_kind, feed_id, feed, body)

        task = self.in_flight.get(key)
        if task is None:
            if retrying:
                raise FeedUnavailableError(f"{kind} {feed_id} failed recently")
            if self._full():
                raise FeedUnavailableError(f"{kind} {feed_id}: too many builds")
            task = self._start(feed_kind, feed_id)
        try:
            ok = await asyncio.wait_for(asyncio.shield(task), budget)
        except TimeoutError:
            raise FeedUnavailableError(f"{kind} {feed_id} is still building") from None
        if not ok:
            if feed_kind.check(feed_id) is IdStatus.UNKNOWN:
                raise UnknownFeedError(f"{kind} {feed_id}")
            raise FeedUnavailableError(f"{kind} {feed_id} build failed")
        body = read_by_id(self._data_dir, kind, feed_id)
        if body is None:
            raise FeedUnavailableError(f"{kind} {feed_id} was not stored")
        try:
            feed = feed_kind.model.model_validate_json(body)
        except ValidationError:
            raise FeedUnavailableError(
                f"{kind} {feed_id} stored file is invalid"
            ) from None
        self._store.touch_feed_build(kind, feed_id, self._clock())
        return self._respond(feed_kind, feed_id, feed, body)

    def refresh(self, kind: str, feed_id: str) -> None:
        """Starts a build of the feed unless one is in flight or MAX_QUEUED_BUILDS
        builds are already in flight; never waits."""
        if (kind, feed_id) not in self.in_flight and not self._full():
            self._start(self._kinds[kind], feed_id)

    def warm(self, kind: str, feed_id: str) -> None:
        """Starts a build of the feed when it is stored with no fresh copy, or
        missing, unless one is in flight, MAX_QUEUED_BUILDS builds are already in flight or
        the last failure is inside the retry window; never waits."""
        feed_kind = self._kinds[kind]
        if feed_kind.check(feed_id) is not IdStatus.KNOWN:
            return
        if (kind, feed_id) in self.in_flight:
            return
        now = self._clock()
        state = self._store.feed_build(kind, feed_id)
        feed = self._stored_model(feed_kind, feed_id)
        last_build = state.last_build if state else None
        if (
            feed is not None
            and last_build is not None
            and feed_kind.is_fresh(feed, last_build, now)
        ):
            return
        if (
            state is not None
            and state.last_failure is not None
            and now - state.last_failure < RETRY_AFTER
        ):
            return
        if self._full():
            return
        self._start(feed_kind, feed_id)

    def _respond(
        self, kind: FeedKind[Any], feed_id: str, feed: BaseModel, body: bytes
    ) -> bytes:
        if kind.serve_with is None and self._identities is None:
            return body
        try:
            added = feed if kind.serve_with is None else kind.serve_with(feed_id, feed)
            if self._identities is not None:
                added = with_identities(added, self._identities())
            served = kind.model.model_validate(added.model_dump(mode="json"))
        except ValidationError:
            logger.error(
                "feed %s %s serve-time additions are invalid", kind.name, feed_id
            )
            return bytes(feed.model_dump_json().encode("utf-8"))
        return bytes(served.model_dump_json().encode("utf-8"))

    def _start(self, kind: FeedKind[Any], feed_id: str) -> asyncio.Task[bool]:
        key = (kind.name, feed_id)
        task = asyncio.create_task(self._build(kind, feed_id))
        self.in_flight[key] = task

        def done(finished: asyncio.Task[bool]) -> None:
            if self.in_flight.get(key) is finished:
                del self.in_flight[key]
            if not finished.cancelled():
                finished.exception()  # consume it: callers that left never retrieve it

        task.add_done_callback(done)
        return task

    def _stored_model(self, kind: FeedKind[Any], feed_id: str) -> BaseModel | None:
        body = read_by_id(self._data_dir, kind.name, feed_id)
        if body is None:
            return None
        try:
            return kind.model.model_validate_json(body)  # type: ignore[no-any-return]
        except ValidationError:
            return None

    async def _ensure(self, kind_name: str, feed_id: str) -> None:
        """Makes the feed fresh before a build that reads it; a failure, or too many
        builds in flight, leaves it as stored."""
        kind = self._kinds[kind_name]
        if kind.check(feed_id) is not IdStatus.KNOWN:
            return
        task = self.in_flight.get((kind_name, feed_id))
        if task is None:
            now = self._clock()
            state = self._store.feed_build(kind_name, feed_id)
            feed = self._stored_model(kind, feed_id)
            last_build = state.last_build if state else None
            if (
                feed is not None
                and last_build is not None
                and kind.is_fresh(feed, last_build, now)
            ):
                return
            if (
                state is not None
                and state.last_failure is not None
                and now - state.last_failure < RETRY_AFTER
            ):
                return
            if self._full():
                return
            task = self._start(kind, feed_id)
        await asyncio.shield(task)

    async def _build(self, kind: FeedKind[Any], feed_id: str) -> bool:
        if kind.depends_on is not None:
            try:
                pair = kind.depends_on(feed_id)
                if pair is not None:
                    await self._ensure(*pair)
            except Exception as error:  # noqa: BLE001 - a failed build must never escape
                self._store.record_build_failure(
                    kind.name,
                    feed_id,
                    self._clock(),
                    failure_reason(error),
                )
                return False
        async with self._builds:
            started = self._clock()
            reason: str
            try:
                feed = await asyncio.wait_for(kind.build(feed_id), self._build_timeout)
            except UnknownFeedError:
                return False
            except TimeoutError:
                reason = BUILD_TIMED_OUT
            except SourceError as error:
                reason = error.reason
            except Exception as error:  # noqa: BLE001 - a failed build must never escape
                reason = failure_reason(error)
            else:
                if publish_by_id(self._data_dir, kind.name, kind.model, feed_id, feed):
                    self._store.record_build(kind.name, feed_id, started)
                    if kind.after_publish is not None:
                        kind.after_publish(feed_id, feed)
                    return True
                reason = "feed not written"
            self._store.record_build_failure(kind.name, feed_id, self._clock(), reason)
            return False

    def cleanup(self) -> None:
        for kind in self._kinds.values():
            ids = published_ids(self._data_dir, kind.name) | self._store.feed_build_ids(
                kind.name
            )
            for feed_id in sorted(ids):
                if not kind.keep(feed_id):
                    delete_by_id(self._data_dir, kind.name, feed_id)
                    self._store.delete_feed_build(kind.name, feed_id)

    def prune_unserved(self, kinds: Iterable[str], now: dt.datetime) -> None:
        """Deletes the stored file and build row of every id of the given kinds
        not served in KEPT_RETENTION, or stored with no build row; an id with a
        build in flight is skipped. Builds nothing and reads no source."""
        for name in kinds:
            kind = self._kinds[name]
            stored = published_ids(self._data_dir, kind.name)
            rows = self._store.feed_build_ids(kind.name)
            ids = self._store.stale_feed_build_ids(kind.name, now - KEPT_RETENTION) | (
                stored - rows
            )
            for feed_id in sorted(ids):
                if (kind.name, feed_id) in self.in_flight:
                    continue
                delete_by_id(self._data_dir, kind.name, feed_id)
                self._store.delete_feed_build(kind.name, feed_id)
