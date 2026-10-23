# api/tests/jobs/test_past_build_reads.py
#
# Tests for the source reads of the five past builds: the season playoffs,
# playoffs finals, Cup, Cup matchup and All-Star feeds (ADR 0058).
#
# Tested:
# - A complete past season builds, and the requests that reach the network are the expected list and at most the declared READ_BUDGET; a repeated game URL is one read
# - Over budget, the build fails, the reason "read budget of N reached" is logged and recorded, nothing is stored and no request goes past the budget
# - At most four narrow requests are in flight in each build (and, in the playoffs build, at most eight identity reads), and no build pauses
# - A 429 and a 503 stop the build with the reason "rate limited", logged and recorded, with nothing stored and no new request inside the retry window
# - The Finals build after the playoffs build makes at most 12 reads, and the Cup matchup after the Cup 2
# - The five budgets are 142, 12, 44, 2 and 60
# - The current Cup after a cold previous season builds both under 44 reads each: the previous season's reads are not counted in the current build
# - The identity reads of the playoffs build reach eight in flight, and a rate limit on one stops the build with nothing stored (ADR 0061)
# - The worst-case playoffs build (20 schedules, 5 play-in days, 26 awards reads, a 7-game Finals, 27 leader reads, 52 award winner reads) sends exactly READ_BUDGET reads, and one read fewer allowed fails with "read budget of N reached"
#
# What is covered:
# - Job minimums for the five kinds: success publishes a valid feed, failure with nothing stored is unavailable
# - The cross-cutting rules of ADR 0058, counted where a read is made: the shared client
#
# Each kit keeps its fake adapters; count_reads makes every call of one send one
# request through the client to a respx route, so the counts are the build's own
# call plan and the budget, the limit of four and the rate-limit stop are the
# real ones. No test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_past_build_reads.py
#
# SEE: api/app/sources/http.py, api/tests/jobs/past_season_source.py

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

from app.feeds.playoffs import AwardCode, LeaderCategory
from app.jobs import (
    cup_feed,
    season_all_star_feed,
    season_cup_feed,
    season_cup_matchup_feed,
    season_playoffs_feed,
    season_playoffs_finals_feed,
)
from app.jobs.on_demand import RETRY_AFTER, FeedUnavailableError
from app.sources.http import SourceClient, get_json
from app.sources.postseason_leaders import LeaderEntry, PostseasonLeaders
from app.sources.season_awards import AWARDS, SeasonAwards
from app.storage.feeds import read_by_id
from tests.jobs.past_season_source import (
    BASE,
    FRESH,
    REAL_SLEEP,
    ReadRecorder,
    count_reads,
)
from tests.jobs.test_playoffs_feed import (
    EAST,
    award,
    both,
    finals,
    round_one,
    round_three,
    round_two,
    seed,
)
from tests.jobs.test_season_all_star_feed import SeasonAllStarKit
from tests.jobs.test_season_cup_feed import SeasonCupKit
from tests.jobs.test_season_cup_matchup_feed import SeasonMatchupKit
from tests.jobs.test_season_playoffs_feed import SeasonPlayoffsKit
from tests.jobs.test_season_playoffs_finals_feed import FinalsKit


async def nothing(kit: Any) -> None:
    return None


async def build_playoffs(kit: Any) -> None:
    await kit.serve_season("2025")


async def build_cup(kit: Any) -> None:
    await kit.serve_season("2025")


async def serve_playoffs(kit: Any) -> object:
    return await kit.serve_season("2025")


async def serve_finals(kit: Any) -> object:
    return await kit.serve_finals("2025")


async def serve_cup(kit: Any) -> object:
    return await kit.serve_season("2025")


async def serve_matchup(kit: Any) -> object:
    return await kit.serve_slot()


async def serve_all_star(kit: Any) -> object:
    body = await kit.cache.serve(season_all_star_feed.KIND, "2025")
    await kit.settle()
    return body


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
    # The requests of a complete build by adapter; none: only the sum is checked.
    expected: dict[str, int] | None


CASES = [
    Case(
        "playoffs",
        SeasonPlayoffsKit,
        lambda kit: [kit.season_playoffs, kit.identities],
        season_playoffs_feed,
        season_playoffs_feed.KIND,
        "2025",
        142,
        nothing,
        serve_playoffs,
        "postseason_schedule",
        {
            "division_standings": 1,
            "postseason_schedule": 20,
            "season_type": 1,
            "postseason_games": 5,
            "postseason_leaders": 1,
            "season_awards": 1,
            "team_postseason_record": 2,
            "game": 5,
            "player_athlete": 3,
        },
    ),
    Case(
        "finals",
        FinalsKit,
        lambda kit: [kit.season_playoffs, kit.season_finals],
        season_playoffs_finals_feed,
        season_playoffs_finals_feed.KIND,
        "2025",
        12,
        build_playoffs,
        serve_finals,
        "game",
        {
            "game": 5,
            "team_postseason_record": 2,
            "team_postseason_stats": 2,
            "player_stats": 1,
        },
    ),
    Case(
        "cup",
        SeasonCupKit,
        lambda kit: [kit.season_cups],
        season_cup_feed,
        season_cup_feed.KIND,
        "2025",
        44,
        nothing,
        serve_cup,
        "season_schedule",
        {
            "group_teams": 6,
            "group_table": 6,
            "conference_table": 2,
            "season_schedule": 30,
        },
    ),
    Case(
        "cup matchup",
        SeasonMatchupKit,
        lambda kit: [kit.season_cups, kit.season_matchups],
        season_cup_matchup_feed,
        season_cup_matchup_feed.KIND,
        "2025-east-qf-1",
        2,
        build_cup,
        serve_matchup,
        "season_schedule",
        {"season_schedule": 2},
    ),
    Case(
        "all-star",
        SeasonAllStarKit,
        lambda kit: [kit.season_feeds],
        season_all_star_feed,
        season_all_star_feed.KIND,
        "2025",
        60,
        nothing,
        serve_all_star,
        "game",
        None,
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


def make_run(
    case: Case, path: Path, router: respx.MockRouter, sleeps: list[float]
) -> Run:
    kit = case.make(path)
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
    return make_run(request.param, tmp_path, router, sleeps)


def test_the_five_budgets_are_the_declared_ones() -> None:
    assert [case.module.READ_BUDGET for case in CASES] == [142, 12, 44, 2, 60]
    assert [case.budget for case in CASES] == [142, 12, 44, 2, 60]
    assert season_playoffs_feed.LEADER_READS == 27


@pytest.mark.anyio
async def test_a_complete_past_season_builds_within_its_budget_with_the_expected_reads(
    run: Run,
) -> None:
    await run.ready()

    await run.case.serve(run.kit)

    assert run.stored() is not None
    assert 0 < run.recorder.count <= run.case.budget
    if run.case.expected is not None:
        assert run.recorder.by_adapter() == run.case.expected
    assert not run.sleeps


@pytest.mark.anyio
async def test_the_all_star_build_reads_the_calendar_the_days_the_details_and_the_awards(
    tmp_path: Path, router: respx.MockRouter, sleeps: list[float]
) -> None:
    run = make_run(CASES[4], tmp_path, router, sleeps)

    await run.case.serve(run.kit)

    counts = run.recorder.by_adapter()
    assert counts["season_calendar"] == 1
    assert counts["all_star_games"] == 2
    assert counts["season_awards"] == 1
    assert 0 < run.recorder.count <= run.case.budget
    assert not any("2024" in call for call in run.kit.calls)


@pytest.mark.anyio
async def test_over_budget_the_build_fails_logs_the_reason_stores_nothing_and_reads_no_more(
    run: Run, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    await run.ready()
    limit = 1 if run.case.name == "cup matchup" else 3
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

    assert run.recorder.narrow_peak <= 4
    if run.case.name in ("playoffs", "cup"):
        assert run.recorder.narrow_peak == 4
    if run.case.name == "playoffs":
        assert run.recorder.wide_peak <= 8
    else:
        assert run.recorder.wide_peak == 0
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


@pytest.mark.anyio
async def test_the_finals_build_after_the_playoffs_build_makes_at_most_12_reads(
    tmp_path: Path, router: respx.MockRouter, sleeps: list[float]
) -> None:
    run = make_run(CASES[1], tmp_path, router, sleeps)
    await run.kit.serve_season("2025")
    playoffs_reads = run.recorder.count
    run.recorder.reset()

    await run.kit.serve_finals("2025")

    assert playoffs_reads <= season_playoffs_feed.READ_BUDGET
    assert 0 < run.recorder.count <= 12


@pytest.mark.anyio
async def test_the_cup_matchup_after_the_cup_makes_at_most_2_reads(
    tmp_path: Path, router: respx.MockRouter, sleeps: list[float]
) -> None:
    run = make_run(CASES[3], tmp_path, router, sleeps)
    await run.kit.serve_season("2025")
    cup_reads = run.recorder.count
    run.recorder.reset()

    # Later than the hour the Cup's schedules stay fresh: the slot reads again.
    await run.kit.serve_slot(at=run.kit.clock[0] + dt.timedelta(hours=2))

    assert cup_reads <= 44
    assert 0 < run.recorder.count <= 2


@pytest.mark.anyio
async def test_the_current_cup_after_a_cold_previous_season_keeps_each_build_in_its_own_budget(
    tmp_path: Path, router: respx.MockRouter
) -> None:
    kit = SeasonCupKit(tmp_path)
    recorder = ReadRecorder()
    recorder.install(router)
    count_reads([kit.cup, kit.season_cups], kit.client)

    await kit.serve()

    assert read_by_id(kit.path, cup_feed.KIND, cup_feed.FEED_ID) is not None
    assert read_by_id(kit.path, season_cup_feed.KIND, "2026") is not None
    assert cup_feed.READ_BUDGET == 44 == season_cup_feed.READ_BUDGET
    assert recorder.count > 44
    assert recorder.by_adapter() == {
        "group_teams": 12,
        "group_table": 12,
        "conference_table": 4,
        "season_schedule": 60,
    }


AWARD_DOCUMENTS = 25
FINALS_GAMES = 7
# The award winners of the worst case, all different from the leaders: the
# declared maximum, one per single-winner award and five per team award.
WINNERS = 52


def distinct_leaders() -> PostseasonLeaders:
    """Nine categories of five leaders: 45 different players, of which the build
    names the first three of each category."""
    return PostseasonLeaders(
        categories={
            category: [
                LeaderEntry(
                    player_id=str(100 + 5 * index + place),
                    value="9.0",
                    team_code=seed(EAST, 1),
                )
                for place in range(5)
            ]
            for index, category in enumerate(LeaderCategory)
        }
    )


def distinct_awards() -> SeasonAwards:
    """Every award of the table with all its winners different: 52 players."""
    awards = []
    for index, (code, team) in enumerate(AWARDS.values()):
        size = 5 if team is not None or code is AwardCode.CUP_ALL_TOURNAMENT else 1
        awards.append(
            award(
                code,
                [str(500 + 10 * index + n) for n in range(size)],
                team,
                team_code=seed(EAST, 1),
            )
        )
    return SeasonAwards(awards=awards)


async def worst_case_playoffs(
    path: Path, router: respx.MockRouter, sleeps: list[float]
) -> Run:
    """The playoffs kit with the most reads a build can send: the awards adapter
    reads its index and 25 documents, and the Finals goes the distance."""
    kit = SeasonPlayoffsKit(path)
    kit.load(both(round_one) + both(round_two) + both(round_three) + finals("TTBBTBT"))
    kit.leaders_source = distinct_leaders()
    kit.awards_source = distinct_awards()
    recorder = ReadRecorder()
    recorder.install(router)
    client: SourceClient = kit.client
    awards = kit.season_playoffs._fetch_season_awards

    async def with_documents(*args: Any, **kwargs: Any) -> Any:
        for number in range(AWARD_DOCUMENTS):
            await get_json(
                client,
                f"{BASE}award_documents/{number}",
                source="test",
                fresh=FRESH,
            )
        return await awards(*args, **kwargs)

    kit.season_playoffs._fetch_season_awards = with_documents
    count_reads([kit.season_playoffs, kit.identities], client)
    return Run(CASES[0], kit, recorder, sleeps)


@pytest.mark.anyio
async def test_the_worst_case_playoffs_build_sends_exactly_the_budget(
    tmp_path: Path, router: respx.MockRouter, sleeps: list[float]
) -> None:
    run = await worst_case_playoffs(tmp_path, router, sleeps)

    await run.case.serve(run.kit)

    counts = run.recorder.by_adapter()
    assert counts["postseason_games"] == 5
    assert counts["season_awards"] + counts["award_documents"] == 26
    assert counts["game"] == FINALS_GAMES
    assert run.stored() is not None
    assert counts["player_athlete"] == 27 + WINNERS
    assert run.recorder.wide_peak <= 8
    assert run.recorder.count == season_playoffs_feed.READ_BUDGET


@pytest.mark.anyio
async def test_the_worst_case_playoffs_build_with_one_read_fewer_fails_over_budget(
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await worst_case_playoffs(tmp_path, router, sleeps)
    limit = season_playoffs_feed.READ_BUDGET - 1
    monkeypatch.setattr(season_playoffs_feed, "READ_BUDGET", limit)

    with pytest.raises(FeedUnavailableError):
        await run.case.serve(run.kit)

    assert run.failure() == f"read budget of {limit} reached"
    assert run.stored() is None
    assert run.recorder.count == limit


@pytest.mark.anyio
async def test_the_identity_reads_reach_eight_in_flight(
    tmp_path: Path, router: respx.MockRouter, sleeps: list[float]
) -> None:
    run = await worst_case_playoffs(tmp_path, router, sleeps)

    await run.case.serve(run.kit)

    assert run.recorder.wide_peak == 8
    assert run.recorder.narrow_peak <= 4


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limit_on_an_identity_read_stops_the_playoffs_build_with_nothing_stored(
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    caplog: pytest.LogCaptureFixture,
    status: int,
) -> None:
    run = make_run(CASES[0], tmp_path, router, sleeps)
    run.recorder.limit_on = "player_athlete"
    run.recorder.status = status

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.case.serve(run.kit)

    assert "not built: rate limited" in caplog.text
    assert run.failure() == "rate limited"
    assert run.stored() is None
