# api/tests/jobs/test_past_page_reads.py
#
# Tests for the source reads of the five past page builds: the season team and
# season player feeds, the day feed, the past game detail and the season standings
# (ADR 0059).
#
# Tested:
# - A complete past item builds, and the requests that reach the network are the expected list and at most the declared READ_BUDGET
# - Over budget, the build fails, the reason "read budget of N reached" is logged and recorded, nothing is stored and no request goes past the budget
# - At most four requests are in flight in each build, and no build pauses
# - A 429 and a 503 stop the build with the reason "rate limited", logged and recorded, with nothing stored and no new request inside the retry window
# - The five budgets are 5, 4, 1, 1 and 1
# - No build sends a season names read: the names kind is wrapped, so one would count as a season team read
#
# What is covered:
# - Job minimums for the five kinds: success publishes a valid feed, failure with nothing stored is unavailable
# - The cross-cutting rules of ADR 0058 and ADR 0059, counted where a read is made: the shared client
#
# Each kit keeps its fake adapters; count_reads makes every call of one send one
# request through the client to a respx route, so the counts are the build's own
# call plan and the budget, the limit of four and the rate-limit stop are the
# real ones. The franchise names of the team and the player are stored before the
# count starts, as a request finds them. No test uses a real source or the real
# clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_past_page_reads.py
#
# SEE: api/app/sources/http.py, api/tests/jobs/past_season_source.py,
# api/tests/jobs/test_past_build_reads.py

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import respx

from app.feeds.games import GameStatus
from app.feeds.team import NameRun
from app.jobs import (
    day_feed,
    past_game_detail_feed,
    season_player_feed,
    season_standings_feed,
    season_team_feed,
    team_names,
)
from app.jobs.on_demand import RETRY_AFTER, FeedUnavailableError
from app.storage.feeds import read_by_id
from tests.jobs.past_season_source import REAL_SLEEP, ReadRecorder, count_reads
from tests.jobs.test_day_feed import PAST, game
from tests.jobs.test_past_game_detail_feed import PastKit
from tests.jobs.test_season_player_feed import SeasonPlayerKit
from tests.jobs.test_season_standings_feed import StandingsKit
from tests.jobs.test_season_team_feed import SeasonTeamKit


def runs(code: str) -> list[NameRun]:
    return [
        NameRun(from_=1994, to=None, name="Example Club", location="Example", code=code)
    ]


async def prepare_team(kit: SeasonTeamKit) -> None:
    """The names list of the team is stored, as it is when a request comes."""
    await kit.cache.serve(team_names.KIND, "okc")
    await kit.settle()


async def prepare_player(kit: SeasonPlayerKit) -> None:
    kit.publish_names("okc", runs("OKC"))
    kit.publish_names("mem", runs("MEM"))


async def prepare_day(kit: Any) -> None:
    kit.days[PAST] = [game("1", GameStatus.FINAL)]


async def prepare_past(kit: PastKit) -> None:
    await kit.store_day(game("1", GameStatus.FINAL))


async def nothing(kit: Any) -> None:
    return None


async def serve_team(kit: SeasonTeamKit) -> object:
    return await kit.serve("2004-okc")


async def serve_player(kit: SeasonPlayerKit) -> object:
    return await kit.serve("2004-77")


async def serve_day(kit: Any) -> object:
    return await kit.serve(PAST)


async def serve_past(kit: PastKit) -> object:
    return await kit.serve_past("1")


async def serve_standings(kit: StandingsKit) -> object:
    return await kit.serve("1996")


@dataclass(frozen=True)
class Case:
    name: str
    make: Callable[[Path], Any]
    kinds: Callable[[Any], list[object]]
    module: ModuleType
    kind: str
    feed_id: str
    budget: int
    prepare: Callable[[Any], Awaitable[None]]
    serve: Callable[[Any], Awaitable[object]]
    # The adapter whose reads a rate limit answers.
    limited: str
    # The over budget limit to set.
    over: int
    # The requests of a complete build by adapter.
    expected: dict[str, int]


CASES = [
    Case(
        "team",
        SeasonTeamKit,
        lambda kit: [kit.teams, kit.names],
        season_team_feed,
        season_team_feed.KIND,
        "2004-okc",
        5,
        prepare_team,
        serve_team,
        "season_schedule",
        2,
        {"season_team": 1, "division_standings": 1, "season_schedule": 2},
    ),
    Case(
        "player",
        SeasonPlayerKit,
        lambda kit: [kit.kind, kit.names],
        season_player_feed,
        season_player_feed.KIND,
        "2004-77",
        4,
        prepare_player,
        serve_player,
        "player_stats",
        2,
        {"player_athlete": 1, "player_gamelog": 1, "player_stats": 2},
    ),
    Case(
        "day",
        PastKit,
        lambda kit: [kit.days_kind, kit.names],
        day_feed,
        day_feed.KIND,
        PAST.isoformat(),
        1,
        prepare_day,
        serve_day,
        "past_day",
        0,
        {"past_day": 1},
    ),
    Case(
        "past game detail",
        PastKit,
        lambda kit: [kit.past_kind],
        past_game_detail_feed,
        past_game_detail_feed.KIND,
        "1",
        1,
        prepare_past,
        serve_past,
        "sections",
        0,
        {"sections": 1},
    ),
    Case(
        "standings",
        StandingsKit,
        lambda kit: [kit.kind, kit.names],
        season_standings_feed,
        season_standings_feed.KIND,
        "1996",
        1,
        nothing,
        serve_standings,
        "division_standings",
        0,
        {"division_standings": 1},
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
        """Build what the build depends on, then count from zero."""
        await self.case.prepare(self.kit)
        self.recorder.reset()
        # What the build before read is stale now, as it is when a later request
        # comes: a cache hit is not a read.
        self.kit.clock[0] += dt.timedelta(hours=2)

    def stored(self) -> bytes | None:
        return read_by_id(self.kit.path, self.case.kind, self.case.feed_id)

    def failure(self) -> str | None:
        found = self.kit.store.feed_build(self.case.kind, self.case.feed_id)
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


@pytest.fixture(params=CASES, ids=IDS)
def run(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
) -> Run:
    case: Case = request.param
    kit = case.make(tmp_path)
    recorder = ReadRecorder()
    recorder.install(router)
    count_reads(case.kinds(kit), kit.client)
    return Run(case, kit, recorder, sleeps)


def test_the_five_budgets_are_the_declared_ones() -> None:
    assert [case.module.READ_BUDGET for case in CASES] == [5, 4, 1, 1, 1]
    assert [case.budget for case in CASES] == [5, 4, 1, 1, 1]


@pytest.mark.anyio
async def test_a_complete_past_item_builds_within_its_budget_with_only_the_listed_reads(
    run: Run,
) -> None:
    await run.ready()

    await run.case.serve(run.kit)

    assert run.stored() is not None
    assert 0 < run.recorder.count <= run.case.budget
    assert run.recorder.by_adapter() == run.case.expected
    assert not run.sleeps


@pytest.mark.anyio
async def test_over_budget_the_build_fails_logs_the_reason_stores_nothing_and_reads_no_more(
    run: Run, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    await run.ready()
    limit = run.case.over
    monkeypatch.setattr(run.case.module, "READ_BUDGET", limit)

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.case.serve(run.kit)

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

    await run.case.serve(run.kit)

    assert run.recorder.peak <= 4
    if run.case.name == "player":
        assert run.recorder.peak == 4
    assert not run.sleeps


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limit_stops_the_build_with_the_reason_logged_nothing_stored_and_a_retry_after_ten_minutes(
    run: Run, status: int, caplog: pytest.LogCaptureFixture
) -> None:
    await run.ready()
    run.recorder.limit_on = run.case.limited
    run.recorder.status = status
    start = run.kit.clock[0]

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.case.serve(run.kit)

    assert "not built: rate limited" in caplog.text
    assert run.failure() == "rate limited"
    assert run.stored() is None
    sent = run.recorder.count

    run.kit.clock[0] = start + RETRY_AFTER - dt.timedelta(minutes=1)
    with pytest.raises(FeedUnavailableError):
        await run.case.serve(run.kit)
    assert run.recorder.count == sent

    run.recorder.limit_on = None
    run.kit.clock[0] = start + RETRY_AFTER
    await run.case.serve(run.kit)
    assert run.stored() is not None
    assert run.recorder.count > sent
