# api/app/jobs/scheduler.py
#
# In-process scheduler: one asyncio task that runs every job on a fixed tick.
# The clock and the sleep are injected so tests run without real time.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md

import asyncio
import contextlib
import datetime as dt
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

from app.storage.state import StateStore

TICK_SECONDS = 30.0


class Job(Protocol):
    name: str

    async def run(self, now: dt.datetime) -> None: ...


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Scheduler:
    def __init__(
        self,
        jobs: Sequence[Job],
        store: StateStore,
        *,
        clock: Callable[[], dt.datetime] = utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        interval: float = TICK_SECONDS,
    ) -> None:
        self._jobs = jobs
        self._store = store
        self._clock = clock
        self._sleep = sleep
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        self._task = None

    async def _loop(self) -> None:
        while True:
            for job in self._jobs:
                await self._run(job)
            await self._sleep(self._interval)

    async def _run(self, job: Job) -> None:
        now = self._clock()
        try:
            await job.run(now)
        except Exception as error:  # noqa: BLE001 - a job must never stop the loop
            self._store.record_failure(
                job.name, now, f"unexpected error: {type(error).__name__}"
            )
