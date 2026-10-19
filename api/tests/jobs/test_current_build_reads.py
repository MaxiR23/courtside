# api/tests/jobs/test_current_build_reads.py
#
# Tests for the source reads of the four current builds that declare a read
# budget: the playoffs, Cup, standings and search feeds (ADR 0066).
#
# Tested:
# - A complete build stores a feed, and the requests that reach the network are at most the declared budget (playoffs: the two window reads plus the day count plus the other reads)
# - Over budget (the constant cut to 3, the window reads of the playoffs to 1), the build fails, the reason "read budget of N reached" is logged and recorded, nothing is stored and no request goes past the budget
# - At most four requests are in flight in each build, and exactly four in the playoffs scoreboard days and the Cup schedules
# - The budgets are 2 + 60, 44, 32 and 33
# - The four builds count reads only (ADR 0066): a rate-limited Cup schedule read is skipped and the Cup feed is stored, with no "rate limited" reason recorded or logged; a rate-limited Cup group or conference table read fails the build as an ordinary failed read
# - The standings and search builds: a rate-limited team info leaves null colors and the build succeeds; a rate-limited standings read, and a rate-limited season type read of the playoffs, fail the build as an ordinary failed read (ADR 0066)
#
# What is covered:
# - Job minimums for the four kinds: success publishes a valid feed, failure with nothing stored is unavailable
# - The cross-cutting rules of ADR 0058 and ADR 0066, counted where a read is made: the shared client
#
# Each kit keeps its fake adapters; count_reads makes every call of one send one
# request through the client to a respx route, so the counts are the build's own
# call plan and the budget, the limit of four and the rate-limit rule are the
# real ones. The standings and search kits' own reads are silenced so that a
# call counts once. No test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_current_build_reads.py
#
# SEE: api/app/sources/http.py, api/tests/jobs/past_season_source.py,
# api/tests/jobs/test_past_page_reads.py

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
import respx

from app.feeds.standings import StandingsFeed
from app.jobs import cup_feed, playoffs_feed, search_feed, standings_feed
from app.jobs.on_demand import FeedUnavailableError
from app.jobs.playoffs_feed import postseason_days
from app.sources.http import Freshness, SourceError
from app.storage.feeds import read_by_id
from tests.jobs.past_season_source import BASE, REAL_SLEEP, ReadRecorder, count_reads
from tests.jobs.test_cup_feed import CupKit, group_pairs
from tests.jobs.test_playoffs_feed import (
    PLAY_IN_WINDOW,
    POSTSEASON_WINDOW,
    PlayoffsKit,
)
from tests.jobs.test_search_feed import SearchKit
from tests.jobs.test_standings_feed import StandingsKit

DAYS = len(postseason_days(PLAY_IN_WINDOW, POSTSEASON_WINDOW))


def silence_own_reads(kit: Any) -> Any:
    """The kit's fake adapters read a URL themselves: count_reads does it once."""

    async def read(name: str, fresh: Freshness) -> None:
        kit.calls.append(name)
        if name in kit.failing:
            raise SourceError("test", f"{name} is down")

    kit.read = read
    return kit


def make_standings(path: Path) -> StandingsKit:
    return silence_own_reads(StandingsKit(path))  # type: ignore[no-any-return]


def make_search(path: Path) -> SearchKit:
    return silence_own_reads(SearchKit(path))  # type: ignore[no-any-return]


async def nothing(kit: Any) -> None:
    return None


async def prepare_search(kit: SearchKit) -> None:
    """The stars job has fetched every roster, as it has when a request comes."""
    await kit.run_stars(kit.clock[0] - dt.timedelta(hours=1))
    kit.clock[0] += dt.timedelta(hours=1)


@dataclass(frozen=True)
class Case:
    name: str
    make: Callable[[Path], Any]
    kinds: Callable[[Any], list[object]]
    module: ModuleType
    kind: str
    # The declared budget of a complete build.
    budget: int
    prepare: Callable[[Any], Awaitable[None]]
    # The constant to cut for the over budget test, the limit it is cut to and
    # the limit the build then reports.
    over: str
    over_limit: int
    # The adapter whose reads a rate limit answers.
    limited: str


CASES = [
    Case(
        "playoffs",
        PlayoffsKit,
        lambda kit: [kit.playoffs],
        playoffs_feed,
        playoffs_feed.KIND,
        playoffs_feed.WINDOW_READS + playoffs_feed.OTHER_READS + DAYS,
        nothing,
        "WINDOW_READS",
        1,
        "season_type",
    ),
    Case(
        "cup",
        CupKit,
        lambda kit: [kit.cup],
        cup_feed,
        cup_feed.KIND,
        44,
        nothing,
        "READ_BUDGET",
        3,
        "season_schedule",
    ),
    Case(
        "standings",
        make_standings,
        lambda kit: [kit.standings],
        standings_feed,
        standings_feed.KIND,
        32,
        nothing,
        "READ_BUDGET",
        3,
        "team_info",
    ),
    Case(
        "search",
        make_search,
        lambda kit: [kit.search],
        search_feed,
        search_feed.KIND,
        33,
        prepare_search,
        "READ_BUDGET",
        3,
        "team_info",
    ),
]
IDS = [case.name for case in CASES]


@dataclass
class Run:
    case: Case
    kit: Any
    recorder: ReadRecorder
    sleeps: list[float]

    async def ready(self) -> None:
        await self.case.prepare(self.kit)
        self.recorder.reset()

    async def serve(self) -> object:
        return await self.kit.serve()

    def stored(self) -> bytes | None:
        return read_by_id(self.kit.path, self.case.kind, "league")

    def failure(self) -> str | None:
        found = self.kit.store.feed_build(self.case.kind, "league")
        return None if found is None else found.last_failure_reason


@pytest.fixture
def router() -> Iterator[respx.MockRouter]:
    with respx.mock as mock:
        yield mock


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Every delay above zero a build asks for (it asks for none)."""
    delays: list[float] = []

    async def recording(seconds: float, *args: Any) -> None:
        if seconds > 0:
            delays.append(seconds)
        await REAL_SLEEP(seconds, *args)

    monkeypatch.setattr(asyncio, "sleep", recording)
    return delays


def run_of(
    case: Case, tmp_path: Path, router: respx.MockRouter, sleeps: list[float]
) -> Run:
    kit = case.make(tmp_path)
    recorder = ReadRecorder()
    recorder.install(router)
    count_reads(case.kinds(kit), kit.client)
    return Run(case, kit, recorder, sleeps)


@pytest.fixture(params=CASES, ids=IDS)
def run(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
) -> Run:
    return run_of(request.param, tmp_path, router, sleeps)


def test_the_budgets_are_the_declared_ones() -> None:
    assert playoffs_feed.WINDOW_READS == 2 and playoffs_feed.OTHER_READS == 60
    assert [case.budget for case in CASES[1:]] == [44, 32, 33]
    assert cup_feed.READ_BUDGET == 44
    assert standings_feed.READ_BUDGET == 32
    assert search_feed.READ_BUDGET == 33


@pytest.mark.anyio
async def test_a_complete_build_stores_a_feed_within_its_declared_budget(
    run: Run,
) -> None:
    await run.ready()

    await run.serve()

    assert run.stored() is not None
    assert 0 < run.recorder.count <= run.case.budget
    assert not run.sleeps


@pytest.mark.anyio
async def test_over_budget_the_build_fails_logs_the_reason_stores_nothing_and_reads_no_more(
    run: Run, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    await run.ready()
    limit = run.case.over_limit
    monkeypatch.setattr(run.case.module, run.case.over, limit)

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.serve()

    reason = f"read budget of {limit} reached"
    assert f"not built: {reason}" in caplog.text
    assert run.failure() == reason
    assert run.stored() is None
    assert run.recorder.count == limit


@pytest.mark.anyio
async def test_at_most_four_requests_are_in_flight_and_the_build_never_pauses(
    run: Run,
) -> None:
    await run.ready()

    await run.serve()

    assert run.recorder.narrow_peak <= 4
    if run.case.name in ("playoffs", "cup"):
        assert run.recorder.narrow_peak == 4
    assert not run.sleeps


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limited_cup_schedule_is_skipped_and_the_build_stores_a_feed(
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    status: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run = run_of(CASES[1], tmp_path, router, sleeps)
    run.kit.pairs = [*group_pairs({})]
    await run.ready()
    # The client pauses every request after a rate limit, so the last schedule
    # read is the one limited: the 29 others are read before the pause.
    schedules = 0
    answer = run.recorder._answer

    async def one_schedule(request: httpx.Request) -> httpx.Response:
        response = await answer(request)
        nonlocal schedules
        if "/season_schedule/" in request.url.path:
            schedules += 1
            if schedules == len(cup_feed.CODES):
                return httpx.Response(status)
        return response

    router.get(url__startswith=BASE).mock(side_effect=one_schedule)

    with caplog.at_level(logging.WARNING):
        await run.serve()

    assert run.stored() is not None
    assert run.failure() is None
    assert "rate limited" not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("limited", ["group_table", "conference_table"])
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limited_cup_table_read_fails_the_build_as_an_ordinary_failed_read(
    limited: str,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    status: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run = run_of(CASES[1], tmp_path, router, sleeps)
    await run.ready()
    run.recorder.limit_on = limited
    run.recorder.status = status

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.serve()

    assert run.failure() != "rate limited"
    assert "not built: rate limited" not in caplog.text
    assert run.stored() is None


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["standings", "search"])
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limited_team_info_leaves_null_colors_and_the_build_succeeds(
    name: str,
    status: int,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
) -> None:
    case = next(case for case in CASES if case.name == name)
    run = run_of(case, tmp_path, router, sleeps)
    await run.ready()
    run.recorder.limit_on = "team_info"
    run.recorder.status = status

    body = await run.serve()

    assert run.stored() is not None
    assert run.failure() is None
    assert run.recorder.count <= run.case.budget
    if name == "standings":
        feed = StandingsFeed.model_validate_json(body)  # type: ignore[arg-type]
        assert {row.colors.primary for row in feed.conferences[0].teams} == {None}


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["standings", "search"])
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limited_standings_read_fails_the_build_as_an_ordinary_failed_read(
    name: str,
    status: int,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
) -> None:
    case = next(case for case in CASES if case.name == name)
    run = run_of(case, tmp_path, router, sleeps)
    await run.ready()
    run.recorder.limit_on = "division_standings"
    run.recorder.status = status

    with pytest.raises(FeedUnavailableError):
        await run.serve()

    assert run.failure() == f"responded with status {status}"
    assert run.stored() is None


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limited_season_type_read_fails_the_playoffs_build_as_an_ordinary_failed_read(
    status: int,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
) -> None:
    run = run_of(CASES[0], tmp_path, router, sleeps)
    await run.ready()
    run.recorder.limit_on = "season_type"
    run.recorder.status = status

    with pytest.raises(FeedUnavailableError):
        await run.serve()

    assert run.failure() in {f"responded with status {status}", "source paused"}
    assert run.stored() is None
