# api/app/jobs/on_demand.py
#
# On-demand feed cache: builds a feed when it is requested, serves the stored feed when it is fresh,
# and rebuilds a stale one in the background. The clock and the wait are injected so tests run without real time.
# It must only be used from async code in the event loop.
#
# SEE: docs/source-rules.md, docs/adr/0020-source-rules.md

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from app.jobs.scheduler import utc_now
from app.sources.http import SourceError
from app.storage.feeds import (
    GAME_ID,
    delete_by_id,
    publish_by_id,
    published_ids,
    read_by_id,
)
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

MISSING_WAIT_SECONDS = 20.0
MAX_BUILDS = 4
RETRY_AFTER = dt.timedelta(minutes=10)


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
    ) -> None:
        self.name = name
        self.model = model
        self.check = check
        self.build = build
        self.is_fresh = is_fresh
        self.keep = keep
        self.serve_with = serve_with
        self.wait_when_stale = wait_when_stale


class FeedCache:
    def __init__(
        self,
        data_dir: Path,
        store: StateStore,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
        wait: float = MISSING_WAIT_SECONDS,
    ) -> None:
        self._data_dir = data_dir
        self._store = store
        self._clock = clock
        self._wait = wait
        self.in_flight: dict[tuple[str, str], asyncio.Task[bool]] = {}
        self._builds = asyncio.Semaphore(MAX_BUILDS)
        self._kinds: dict[str, FeedKind[Any]] = {}

    def register(self, kind: FeedKind[Any]) -> None:
        if not GAME_ID.match(kind.name):
            raise ValueError(f"feed kind name is not a safe id: {kind.name!r}")
        if kind.name in self._kinds:
            raise ValueError(f"feed kind already registered: {kind.name}")
        self._kinds[kind.name] = kind

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
            if not fresh and current is None and not retrying:
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
            return self._respond(feed_kind, feed_id, feed, body)

        task = self.in_flight.get(key)
        if task is None:
            if retrying:
                raise FeedUnavailableError(f"{kind} {feed_id} failed recently")
            task = self._start(feed_kind, feed_id)
        try:
            ok = await asyncio.wait_for(asyncio.shield(task), budget)
        except TimeoutError:
            raise FeedUnavailableError(f"{kind} {feed_id} is still building") from None
        if not ok:
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
        return self._respond(feed_kind, feed_id, feed, body)

    def refresh(self, kind: str, feed_id: str) -> None:
        """Starts a build of the feed unless one is in flight; never waits."""
        if (kind, feed_id) not in self.in_flight:
            self._start(self._kinds[kind], feed_id)

    def _respond(
        self, kind: FeedKind[Any], feed_id: str, feed: BaseModel, body: bytes
    ) -> bytes:
        if kind.serve_with is None:
            return body
        try:
            served = kind.model.model_validate(
                kind.serve_with(feed_id, feed).model_dump(mode="json")
            )
        except ValidationError:
            logger.error(
                "feed %s %s serve-time additions are invalid", kind.name, feed_id
            )
            return body
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

    async def _build(self, kind: FeedKind[Any], feed_id: str) -> bool:
        async with self._builds:
            started = self._clock()
            reason: str
            try:
                feed = await kind.build(feed_id)
            except SourceError as error:
                reason = error.reason
            except Exception as error:  # noqa: BLE001 - a failed build must never escape
                reason = f"unexpected error: {type(error).__name__}"
            else:
                if publish_by_id(self._data_dir, kind.name, kind.model, feed_id, feed):
                    self._store.record_build(kind.name, feed_id, started)
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
