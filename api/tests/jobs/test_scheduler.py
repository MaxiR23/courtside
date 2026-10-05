# api/tests/jobs/test_scheduler.py
#
# Tests for the in-process scheduler.
#
# Tested:
# - Runs each job at once with the time of the clock
# - Runs the jobs again after each tick of thirty seconds
# - Records an unexpected error and keeps running
# - Stops the loop on stop
# - Does nothing when stopped before it started, and when started twice
#
# What is covered:
# - Happy path, edge cases (stop before start, start twice), error case
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_scheduler.py
#
# SEE: api/app/jobs/scheduler.py

import asyncio
import datetime as dt
from pathlib import Path

import pytest

from app.jobs.scheduler import TICK_SECONDS, Scheduler
from app.storage.state import StateStore

NOW = dt.datetime(2026, 10, 5, 12, 0, tzinfo=dt.UTC)


class FakeJob:
    name = "fake"

    def __init__(self, error: Exception | None = None) -> None:
        self.runs: list[dt.datetime] = []
        self.error = error

    async def run(self, now: dt.datetime) -> None:
        self.runs.append(now)
        if self.error is not None:
            raise self.error


class Ticks:
    """A fake sleep that records the seconds and signals after a number of calls."""

    def __init__(self, stop_after: int) -> None:
        self.seconds: list[float] = []
        self.reached = asyncio.Event()
        self._stop_after = stop_after

    async def __call__(self, seconds: float) -> None:
        self.seconds.append(seconds)
        if len(self.seconds) >= self._stop_after:
            self.reached.set()
            await asyncio.Event().wait()


def make(tmp_path: Path, job: FakeJob, ticks: Ticks) -> tuple[Scheduler, StateStore]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = StateStore(tmp_path)
    store.create_tables()
    return Scheduler([job], store, clock=lambda: NOW, sleep=ticks), store


@pytest.mark.anyio
async def test_runs_each_job_at_once_with_the_time_of_the_clock(
    tmp_path: Path,
) -> None:
    job, ticks = FakeJob(), Ticks(1)
    scheduler, _ = make(tmp_path, job, ticks)

    scheduler.start()
    await ticks.reached.wait()
    await scheduler.stop()

    assert job.runs == [NOW]


@pytest.mark.anyio
async def test_runs_the_jobs_again_after_each_tick_of_thirty_seconds(
    tmp_path: Path,
) -> None:
    job, ticks = FakeJob(), Ticks(2)

    scheduler, _ = make(tmp_path, job, ticks)
    scheduler.start()
    await ticks.reached.wait()
    await scheduler.stop()

    assert ticks.seconds == [TICK_SECONDS, TICK_SECONDS]
    assert len(job.runs) == 2


@pytest.mark.anyio
async def test_records_an_unexpected_error_and_keeps_running(tmp_path: Path) -> None:
    job, ticks = FakeJob(RuntimeError("secret detail")), Ticks(2)
    scheduler, store = make(tmp_path, job, ticks)

    scheduler.start()
    await ticks.reached.wait()
    await scheduler.stop()

    assert len(job.runs) == 2
    state = store.job_states()[0]
    assert state.last_failure_reason == "unexpected error: RuntimeError"


@pytest.mark.anyio
async def test_stops_the_loop_on_stop(tmp_path: Path) -> None:
    job, ticks = FakeJob(), Ticks(1)
    scheduler, _ = make(tmp_path, job, ticks)

    scheduler.start()
    scheduler.start()
    assert scheduler.running
    await ticks.reached.wait()
    await scheduler.stop()

    assert not scheduler.running
    assert len(job.runs) == 1


@pytest.mark.anyio
async def test_stop_before_start_does_nothing(tmp_path: Path) -> None:
    scheduler, _ = make(tmp_path, FakeJob(), Ticks(1))

    await scheduler.stop()

    assert not scheduler.running
