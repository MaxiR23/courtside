# api/tests/jobs/test_all_star_discovery.py
#
# Tests for the All-Star discovery job.
#
# Tested:
# - scan_days gives February 1 to March 7 of the season's end year, 36 days in a leap year and 35 otherwise
# - Found: stores the date and the game ids of the first day with All-Star games and reads no later day
# - Not found: reads every day, stores nothing and scans again at the next daily run
# - The previous edition is scanned once and kept: the second daily run reads no day of it
# - A stored current season is never scanned again
# - The season unknown: no read and no job state recorded
# - A failed day read records the failure, stores nothing for that season and is retried no sooner than 5 minutes later
# - A season change makes the run due at once
# - Nothing is read between the daily runs
# - ready() and last_run() are set only after a completed run
#
# What is covered:
# - Pure logic: happy path and edge cases of the scan window
# - Job: a successful run stores the edition, a failed run keeps the stored state
#
# The scoreboard reader is a fake passed to the job and times are passed to run(),
# so no test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_all_star_discovery.py
#
# SEE: api/app/jobs/all_star_discovery.py

import datetime as dt
from pathlib import Path
from typing import cast

import pytest

from app.feeds.games import GameStatus
from app.jobs.all_star_discovery import JOB, RETRY, AllStarDiscovery, scan_days
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources.all_star_scoreboard import AllStarScoreboardGame
from app.sources.http import SourceClient, SourceError, create_client
from app.storage.state import StateStore

MORNING = dt.datetime(2026, 10, 14, 11, 0, tzinfo=dt.UTC)
DAY = dt.timedelta(days=1)


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027

    def current_season(self) -> int | None:
        return self.season


def all_star_game(game_id: str) -> AllStarScoreboardGame:
    return AllStarScoreboardGame(
        id=game_id,
        start_time=dt.datetime(2027, 2, 15, 1, 0, tzinfo=dt.UTC),
        status=GameStatus.SCHEDULED,
        status_text=None,
        period=None,
        clock=None,
        score=None,
        note=None,
        venue=None,
        away=None,
        home=None,
    )


class Kit:
    def __init__(self, path: Path) -> None:
        self.store = StateStore(path)
        self.store.migrate()
        self.clock = [MORNING]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.stars = FakeStars()
        self.days: dict[dt.date, list[str]] = {}
        self.read: list[dt.date] = []
        self.failing: set[dt.date] = set()
        self.job = AllStarDiscovery(
            self.settings,
            self.store,
            self.client,
            cast(StarsJob, self.stars),
            fetch_all_star_games=self.fetch,
        )

    async def fetch(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[AllStarScoreboardGame]:
        self.read.append(day)
        if day in self.failing:
            raise SourceError("test", f"{day} is down")
        return [all_star_game(g) for g in self.days.get(day, [])]

    def reads_of(self, year: int) -> list[dt.date]:
        return [day for day in self.read if day.year == year]


@pytest.fixture
def kit(tmp_path: Path) -> Kit:
    return Kit(tmp_path)


def test_scan_days_runs_from_february_1_to_march_7() -> None:
    days = scan_days(2027)

    assert days[0] == dt.date(2027, 2, 1)
    assert days[-1] == dt.date(2027, 3, 7)
    assert len(days) == 35


def test_scan_days_has_36_days_in_a_leap_year() -> None:
    days = scan_days(2028)

    assert len(days) == 36
    assert dt.date(2028, 2, 29) in days


@pytest.mark.anyio
async def test_stores_the_first_day_with_all_star_games_and_reads_no_later_day(
    kit: Kit,
) -> None:
    kit.days = {dt.date(2027, 2, 14): ["9001", "9002"], dt.date(2027, 2, 20): ["x"]}

    await kit.job.run(MORNING)

    found = kit.store.all_star_edition(2027)
    assert found is not None
    assert found.game_date == dt.date(2027, 2, 14)
    assert found.game_ids == ["9001", "9002"]
    assert kit.reads_of(2027) == scan_days(2027)[:14]
    assert kit.job.edition(2027) == found


@pytest.mark.anyio
async def test_reads_every_day_and_stores_nothing_when_a_season_has_no_all_star_game(
    kit: Kit,
) -> None:
    await kit.job.run(MORNING)

    assert kit.reads_of(2027) == scan_days(2027)
    assert kit.store.all_star_edition(2027) is None
    assert kit.job.ready()


@pytest.mark.anyio
async def test_scans_a_season_with_no_game_again_at_the_next_daily_run(
    kit: Kit,
) -> None:
    await kit.job.run(MORNING)
    kit.read.clear()
    kit.days = {dt.date(2027, 2, 14): ["9001"]}

    await kit.job.run(MORNING + DAY)

    assert kit.reads_of(2027) == scan_days(2027)[:14]
    assert kit.store.all_star_edition(2027) is not None


@pytest.mark.anyio
async def test_scans_the_previous_season_once_and_keeps_it(kit: Kit) -> None:
    kit.days = {
        dt.date(2027, 2, 14): ["9001"],
        dt.date(2026, 2, 15): ["8001"],
    }

    await kit.job.run(MORNING)
    kit.read.clear()
    await kit.job.run(MORNING + DAY)

    previous = kit.store.all_star_edition(2026)
    assert previous is not None and previous.game_date == dt.date(2026, 2, 15)
    assert kit.read == []


@pytest.mark.anyio
async def test_never_scans_a_stored_current_season_again(kit: Kit) -> None:
    kit.store.set_all_star_edition(2027, dt.date(2027, 2, 14), ["9001"])

    await kit.job.run(MORNING)

    assert kit.reads_of(2027) == []
    assert kit.reads_of(2026) == scan_days(2026)


@pytest.mark.anyio
async def test_does_nothing_and_records_nothing_while_the_season_is_unknown(
    kit: Kit,
) -> None:
    kit.stars.season = None

    await kit.job.run(MORNING)

    assert kit.read == []
    assert kit.store.job_states() == []
    assert not kit.job.ready()
    assert kit.job.last_run() is None


@pytest.mark.anyio
async def test_a_failed_day_read_records_the_failure_and_stores_nothing(
    kit: Kit,
) -> None:
    kit.failing = {dt.date(2027, 2, 3)}

    await kit.job.run(MORNING)

    states = {state.name: state for state in kit.store.job_states()}
    assert states[JOB].last_failure == MORNING
    assert states[JOB].last_failure_reason is not None
    assert states[JOB].last_success is None
    assert kit.store.all_star_edition(2027) is None
    assert not kit.job.ready()
    assert kit.job.last_run() is None


@pytest.mark.anyio
async def test_retries_a_failed_run_no_sooner_than_five_minutes_later(
    kit: Kit,
) -> None:
    kit.failing = {dt.date(2027, 2, 3)}
    await kit.job.run(MORNING)
    kit.read.clear()

    await kit.job.run(MORNING + RETRY - dt.timedelta(seconds=1))
    assert kit.read == []

    kit.failing = set()
    kit.days = {dt.date(2027, 2, 14): ["9001"]}
    await kit.job.run(MORNING + RETRY)

    assert kit.store.all_star_edition(2027) is not None
    assert kit.job.ready()


@pytest.mark.anyio
async def test_a_failure_keeps_a_stored_edition(kit: Kit) -> None:
    kit.store.set_all_star_edition(2027, dt.date(2027, 2, 14), ["9001"])
    kit.failing = {dt.date(2026, 2, 1)}

    await kit.job.run(MORNING)

    assert kit.store.all_star_edition(2027) is not None


@pytest.mark.anyio
async def test_a_season_change_makes_the_run_due_at_once(kit: Kit) -> None:
    await kit.job.run(MORNING)
    kit.read.clear()

    await kit.job.run(MORNING + dt.timedelta(minutes=1))
    assert kit.read == []

    kit.stars.season = 2028
    await kit.job.run(MORNING + dt.timedelta(minutes=2))

    assert kit.reads_of(2028) == scan_days(2028)


@pytest.mark.anyio
async def test_reads_nothing_between_the_daily_runs(kit: Kit) -> None:
    await kit.job.run(MORNING)
    kit.read.clear()

    await kit.job.run(MORNING + dt.timedelta(hours=5))

    assert kit.read == []


@pytest.mark.anyio
async def test_ready_and_last_run_are_set_after_a_completed_run(kit: Kit) -> None:
    assert not kit.job.ready() and kit.job.last_run() is None
    kit.clock[0] = MORNING + dt.timedelta(seconds=7)

    await kit.job.run(MORNING)

    assert kit.job.ready()
    assert kit.job.last_run() == MORNING + dt.timedelta(seconds=7)
    states = {state.name: state for state in kit.store.job_states()}
    assert states[JOB].last_success == MORNING
