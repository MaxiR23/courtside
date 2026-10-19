# api/tests/jobs/test_on_demand_build_reads.py
#
# Tests for the source reads of the seven on-demand builds that declare a read
# budget in ADR 0067: the current game detail, team, player, Cup matchup,
# playoffs finals, All-Star and calendar builds (the calendar for a current and a
# past season).
#
# Tested:
# - The budgets are 5, 15, 11, 9, 48, 122 and 1, and the Finals reads at most 18 roster players per finalist
# - A worst-case build (every read the code can make, the optional ones included) stores a feed and sends exactly its budget, adapter by adapter; the All-Star worst case is 8 games per edition and 30 award documents per season
# - One read fewer than the worst case (the constant cut by one): the build fails, the reason "read budget of N reached" is logged and recorded, nothing is stored and no request goes past the budget; a failed rebuild keeps the stored team feed
# - At most four requests are in flight in each build, and exactly four in the Finals and the All-Star
# - The six current builds count reads only: a rate-limited optional read nulls its part and the feed is stored, and a rate-limited required read fails the build as an ordinary failed read, with no "rate limited" reason recorded or logged
# - The past calendar keeps the stop on a rate limit: the reason "rate limited" is logged and recorded and nothing is stored
# - The franchise names built first by the team build keep their own budget: they are not charged to the team's
# - A finalist roster of 20 players: 18 are read and the 2 last in jersey order are listed with no values, with one warning
#
# What is covered:
# - Job minimums for the seven kinds: success publishes a valid feed, a failed run keeps the last valid feed published, failure with nothing stored is unavailable
# - The cross-cutting rules of ADR 0058, ADR 0066 and ADR 0067, counted where a read is made: the shared client
#
# Each kit keeps its fake adapters; count_reads makes every call of one send one
# request through the client to a respx route, so the counts are the build's own
# call plan and the budget, the limit of four and the rate-limit rule are the
# real ones. The reads the real adapters send more than once per call (the
# second request of rule L, the previous season of the leaders, the award
# documents) are added by add_reads. The kits' own reads are silenced so that a
# call counts once. No test uses a real source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_on_demand_build_reads.py
#
# SEE: api/app/sources/http.py, api/tests/jobs/past_season_source.py,
# api/tests/jobs/test_current_build_reads.py,
# docs/adr/0067-read-budgets-of-every-on-demand-build.md

import asyncio
import datetime as dt
import itertools
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import respx

from app.feeds.games import GameStatus
from app.feeds.playoffs_finals import PlayoffsFinalsFeed
from app.feeds.team import TeamFeed
from app.jobs import (
    all_star_feed,
    calendar_feed,
    cup_matchup_feed,
    game_detail_feed,
    player_feed,
    playoffs_finals_feed,
    team_feed,
)
from app.jobs.on_demand import FeedUnavailableError
from app.sources.http import SourceClient, get_json
from app.storage.feeds import read_by_id
from tests.jobs import test_all_star_feed as all_star_tests
from tests.jobs import test_calendar_feed as calendar_tests
from tests.jobs import test_cup_matchup_feed as matchup_tests
from tests.jobs import test_game_detail_feed as detail_tests
from tests.jobs import test_player_feed as player_tests
from tests.jobs import test_playoffs_finals_feed as finals_tests
from tests.jobs import test_team_feed as team_tests
from tests.jobs.past_season_source import (
    BASE,
    FRESH,
    REAL_SLEEP,
    ReadRecorder,
    count_reads,
)
from tests.jobs.test_current_build_reads import silence_own_reads
from tests.jobs.test_playoffs_feed import ALL

AWARD_DOCUMENTS = 30
ALL_STAR_GAMES = 8


def add_reads(
    kind: object, attribute: str, name: str, count: int, client: SourceClient
) -> None:
    """Make each call of an adapter send `count` more requests, as the real
    adapter does (a second request, a document per entry). Call it before
    count_reads, which wraps the result."""
    original = getattr(kind, attribute)
    numbers = itertools.count()

    async def with_more(*args: Any, **kwargs: Any) -> Any:
        for _ in range(count):
            await get_json(
                client,
                f"{BASE}{name}/{next(numbers)}",
                source="test",
                fresh=FRESH,
            )
        return await original(*args, **kwargs)

    setattr(kind, attribute, with_more)


async def nothing() -> None:
    return None


@dataclass
class Setup:
    """A kit at the worst case of its build: what to wrap, how to prepare it and
    how to serve the feed."""

    kit: Any
    kinds: list[object]
    serve: Callable[[], Awaitable[object]]
    feed_id: str
    prepare: Callable[[], Awaitable[None]] = nothing


# The game detail build: 1 summary, 1 standings, 1 injuries, 2 team schedules.
def game_detail_setup(path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    kit = detail_tests.Harness(path)

    async def prepare() -> None:
        kit.games = [
            detail_tests.game(
                "1",
                GameStatus.SCHEDULED,
                start=detail_tests.NOON + 5 * detail_tests.HOUR,
            )
        ]
        await kit.run(detail_tests.NOON)

        async def no_read(game_id: str, fresh: Any) -> str:
            return "x"

        silenced: Any = kit
        silenced.read_state = no_read

    return Setup(kit, [kit.feeds], lambda: kit.serve("1"), "1", prepare)


# The team build: 1 roster, 2 leaders, 1 info, 2 division standings, 1 injuries,
# 2 schedules and the 6 Cup group tables.
def team_setup(path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    kit = silence_own_reads(team_tests.TeamKit(path))
    kit.regular = team_tests.season(team_tests.game("g1"))
    add_reads(kit.teams, "_fetch_division_standings", "division_rule_l", 1, kit.client)
    add_reads(kit.teams, "_fetch_team_leaders", "leaders_previous", 1, kit.client)
    return Setup(kit, [kit.teams], lambda: kit.serve("okc"), "okc")


# The player build: 1 athlete, 1 roster, 2 division standings, 1 injuries, 1 bio,
# 1 draft, 1 awards, 1 game log and 2 career statistics.
def player_setup(path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    kit = silence_own_reads(player_tests.PlayerKit(path))
    add_reads(
        kit.players, "_fetch_division_standings", "division_rule_l", 1, kit.client
    )

    async def prepare() -> None:
        await kit.run_stars()
        await kit.serve("okc")

    return Setup(kit, [kit.players], lambda: kit.serve_player("1"), "1", prepare)


# The Cup matchup build: 1 injuries and, per side team, a roster, a schedule, the
# season averages and a depth chart.
def matchup_setup(path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    kit = matchup_tests.MatchupKit(path)

    async def prepare() -> None:
        await kit.serve()

    return Setup(
        kit,
        [kit.matchups],
        lambda: kit.matchup(),
        matchup_tests.EAST_QF_1,
        prepare,
    )


def finals_roster(prefix: str, size: int) -> list[Any]:
    """`size` players of one finalist, ids and jerseys different; none is the
    Finals MVP (101)."""
    return [
        team_tests.player(f"{prefix}{10 + n}", jersey=str(n + 1)) for n in range(size)
    ]


# The Finals build: 7 games, 2 records, 2 team statistics, two rosters of 18
# players and the Finals MVP, last in jersey order of the first finalist, so that
# only the MVP rule reads him.
def finals_setup(
    path: Path, monkeypatch: pytest.MonkeyPatch, top_size: int = 18
) -> Setup:
    kit = finals_tests.FinalsKit(path)
    kit.load(finals_tests.postseason("TTBBTBT"))
    entries = {
        finals_tests.TOP: [
            *finals_roster("1", top_size),
            team_tests.player("101", jersey="99"),
        ],
        finals_tests.BOTTOM: finals_roster("2", 18),
    }
    stars: Any = kit.stars
    stars.roster_entries = lambda: entries
    return Setup(kit, [kit.finals], lambda: kit.serve_finals(), "league")


def finals_with_20(path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    return finals_setup(path, monkeypatch, top_size=20)


def edition_of(prefix: str) -> list[Any]:
    """Eight final games of three sides: seven round robin games and the
    championship."""
    sides = [all_star_tests.STR, all_star_tests.WAV, all_star_tests.PKS]
    games = [
        all_star_tests.game(
            f"{prefix}{n + 1}",
            sides[n % 3],
            sides[(n + 1) % 3],
            score=(21, 18),
            minutes=30 * n,
        )
        for n in range(ALL_STAR_GAMES - 1)
    ]
    games.append(
        all_star_tests.game(
            f"{prefix}{ALL_STAR_GAMES}",
            all_star_tests.STR,
            all_star_tests.WAV,
            note=all_star_tests.CHAMPIONSHIP,
            minutes=30 * ALL_STAR_GAMES,
            score=(25, 23),
        )
    )
    return games


def february(year: int) -> list[dt.datetime]:
    """The season calendar of February 1 to 6: the edition day is the sixth
    candidate, the last the build reads."""
    return [dt.datetime(year, 2, day, 23, 0, tzinfo=dt.UTC) for day in range(1, 7)]


# The All-Star build, per edition (the current and the previous one): 1 calendar,
# 6 days, 8 games and 31 awards (the index and 30 documents); then 30 team infos.
def all_star_setup(path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    sides = {"STR": "S", "WAV": "W", "PKS": "P"}
    players = {
        code: [
            (f"{letter}{n:02d}", f"Player {letter}{n:02d}", 10, 4, 3) for n in range(10)
        ]
        for code, letter in sides.items()
    }
    for code, lines in players.items():
        monkeypatch.setitem(all_star_tests.SIDE_PLAYERS, code, lines)
    kit = all_star_tests.AllStarKit(path)
    ids = [line[0] for lines in players.values() for line in lines]
    kit.stars.teams = dict(zip(ids, ALL, strict=True))
    kit.mvp_id = "S00"
    kit.calendars = {2027: february(2027), 2026: february(2026)}
    kit.days = {
        dt.date(2027, 2, 6): edition_of("g"),
        dt.date(2026, 2, 6): edition_of("p"),
    }
    add_reads(
        kit.feeds,
        "_fetch_season_awards",
        "award_documents",
        AWARD_DOCUMENTS,
        kit.client,
    )
    return Setup(kit, [kit.feeds], lambda: kit.serve(), "league")


def calendar_setup(season: int) -> Callable[[Path, pytest.MonkeyPatch], Setup]:
    def setup(path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
        kit = calendar_tests.CalendarKit(path)
        return Setup(kit, [kit.calendars], lambda: kit.serve(season), str(season))

    return setup


@dataclass(frozen=True)
class Case:
    name: str
    module: ModuleType
    kind: str
    # The declared budget, which is also the reads of the worst case.
    budget: int
    setup: Callable[[Path, pytest.MonkeyPatch], Setup]
    # The reads of the worst case by adapter, for those that prove the plan.
    reads: dict[str, int] = field(default_factory=dict)


CASES = [
    Case(
        "game detail",
        game_detail_feed,
        game_detail_feed.KIND,
        5,
        game_detail_setup,
        {"sections": 1, "standings": 1, "injuries": 1, "team_schedule": 2},
    ),
    Case(
        "team",
        team_feed,
        team_feed.KIND,
        15,
        team_setup,
        {"group_table": 6, "team_leaders": 1, "division_standings": 1},
    ),
    Case(
        "player",
        player_feed,
        player_feed.KIND,
        11,
        player_setup,
        {"player_stats": 2, "division_standings": 1, "player_athlete": 1},
    ),
    Case(
        "cup matchup",
        cup_matchup_feed,
        cup_matchup_feed.KIND,
        9,
        matchup_setup,
        {"league_injuries": 1, "season_averages": 2, "depth_chart": 2},
    ),
    Case(
        "playoffs finals",
        playoffs_finals_feed,
        playoffs_finals_feed.KIND,
        48,
        finals_setup,
        {
            "game": 7,
            "team_postseason_record": 2,
            "team_postseason_stats": 2,
            "player_stats": 37,
        },
    ),
    Case(
        "all-star",
        all_star_feed,
        all_star_feed.KIND,
        122,
        all_star_setup,
        {
            "season_calendar": 2,
            "all_star_games": 12,
            "game": 16,
            "season_awards": 2,
            "award_documents": 60,
            "team_info": 30,
        },
    ),
    Case(
        "calendar current",
        calendar_feed,
        calendar_feed.KIND,
        1,
        calendar_setup(2027),
        {"season_calendar": 1},
    ),
    Case(
        "calendar past",
        calendar_feed,
        calendar_feed.KIND,
        1,
        calendar_setup(2026),
        {"season_calendar": 1},
    ),
]
IDS = [case.name for case in CASES]


@dataclass
class Run:
    case: Case
    setup: Setup
    recorder: ReadRecorder
    sleeps: list[float]

    @property
    def kit(self) -> Any:
        return self.setup.kit

    async def ready(self) -> None:
        await self.setup.prepare()
        self.recorder.reset()

    async def serve(self) -> object:
        return await self.setup.serve()

    def stored(self) -> bytes | None:
        return read_by_id(
            self.kit.settings.data_dir, self.case.kind, self.setup.feed_id
        )

    def failure(self) -> str | None:
        found = self.kit.store.feed_build(self.case.kind, self.setup.feed_id)
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
    case: Case,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
    setup: Callable[[Path, pytest.MonkeyPatch], Setup] | None = None,
) -> Run:
    built = (setup or case.setup)(tmp_path, monkeypatch)
    recorder = ReadRecorder()
    recorder.install(router)
    count_reads(built.kinds, built.kit.client)
    return Run(case, built, recorder, sleeps)


@pytest.fixture(params=CASES, ids=IDS)
def run(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
) -> Run:
    return run_of(request.param, tmp_path, router, sleeps, monkeypatch)


def named(name: str) -> Case:
    return next(case for case in CASES if case.name == name)


def test_the_budgets_are_the_declared_ones() -> None:
    assert [case.module.READ_BUDGET for case in CASES] == [5, 15, 11, 9, 48, 122, 1, 1]
    assert [case.budget for case in CASES] == [5, 15, 11, 9, 48, 122, 1, 1]
    assert playoffs_finals_feed.FINALS_ROSTER_READS == 18
    assert all_star_feed.MAX_EDITION_READS == 6


@pytest.mark.anyio
async def test_the_worst_case_build_sends_exactly_its_budget(run: Run) -> None:
    await run.ready()

    await run.serve()

    assert run.stored() is not None
    counts = run.recorder.by_adapter()
    for adapter, expected in run.case.reads.items():
        assert counts.get(adapter) == expected, adapter
    assert run.recorder.count == run.case.budget
    assert not run.sleeps


@pytest.mark.anyio
async def test_the_worst_case_build_with_one_read_fewer_fails_over_budget_and_stores_nothing(
    run: Run, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    await run.ready()
    limit = run.case.budget - 1
    monkeypatch.setattr(run.case.module, "READ_BUDGET", limit)

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.serve()

    reason = f"read budget of {limit} reached"
    assert f"not built: {reason}" in caplog.text
    assert run.failure() == reason
    assert run.stored() is None
    assert run.recorder.count == limit


@pytest.mark.anyio
async def test_a_failed_rebuild_over_budget_keeps_the_stored_feed(
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = run_of(named("team"), tmp_path, router, sleeps, monkeypatch)
    await run.ready()
    first = await run.serve()
    stored = run.stored()
    assert stored is not None
    monkeypatch.setattr(team_feed, "READ_BUDGET", 3)
    run.kit.clock[0] += team_feed.FEED_LIFETIME + dt.timedelta(days=1)

    await run.serve()

    assert run.failure() == "read budget of 3 reached"
    assert run.stored() == stored
    assert TeamFeed.model_validate_json(stored).code == "OKC"
    assert first == stored


@pytest.mark.anyio
async def test_at_most_four_requests_are_in_flight_and_the_build_never_pauses(
    run: Run,
) -> None:
    await run.ready()

    await run.serve()

    assert run.recorder.narrow_peak <= 4
    if run.case.name in ("playoffs finals", "all-star"):
        assert run.recorder.narrow_peak == 4
    assert not run.sleeps


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize(
    ("name", "limited"),
    [
        ("game detail", "standings"),
        ("game detail", "injuries"),
        ("team", "group_table"),
        ("cup matchup", "season_averages"),
        ("playoffs finals", "team_postseason_record"),
        ("all-star", "team_info"),
    ],
)
async def test_a_rate_limited_optional_read_nulls_its_part_and_the_build_stores_a_feed(
    name: str,
    limited: str,
    status: int,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run = run_of(named(name), tmp_path, router, sleeps, monkeypatch)
    await run.ready()
    run.recorder.limit_on = limited
    run.recorder.status = status

    with caplog.at_level(logging.WARNING):
        await run.serve()

    assert run.stored() is not None
    assert run.failure() is None
    assert "rate limited" not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize(
    ("name", "limited"),
    [
        ("game detail", "sections"),
        ("player", "player_bio"),
        ("calendar current", "season_calendar"),
    ],
)
async def test_a_rate_limited_required_read_fails_the_build_as_an_ordinary_failed_read(
    name: str,
    limited: str,
    status: int,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run = run_of(named(name), tmp_path, router, sleeps, monkeypatch)
    await run.ready()
    run.recorder.limit_on = limited
    run.recorder.status = status

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.serve()

    assert run.failure() in {f"responded with status {status}", "source paused"}
    assert "not built: rate limited" not in caplog.text
    assert run.stored() is None


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limit_stops_the_past_calendar_build(
    status: int,
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run = run_of(named("calendar past"), tmp_path, router, sleeps, monkeypatch)
    await run.ready()
    run.recorder.limit_on = "season_calendar"
    run.recorder.status = status

    with caplog.at_level(logging.WARNING), pytest.raises(FeedUnavailableError):
        await run.serve()

    assert "not built: rate limited" in caplog.text
    assert run.failure() == "rate limited"
    assert run.stored() is None


@pytest.mark.anyio
async def test_the_franchise_names_dependency_keeps_its_own_budget(
    tmp_path: Path,
    router: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    kit = silence_own_reads(team_tests.NamedKit(tmp_path))
    kit.regular = team_tests.season(team_tests.game("g1"))
    recorder = ReadRecorder()
    recorder.install(router)
    count_reads([kit.teams, kit.names], kit.client)
    # The team's own reads: 1 roster, 1 leaders, 1 info, 1 standings, 1 injuries,
    # 2 schedules and 6 group tables.
    monkeypatch.setattr(team_feed, "READ_BUDGET", 13)

    await kit.serve("okc")

    counts = recorder.by_adapter()
    # The current season is read through the current adapter.
    names = counts["season_team"] + counts["current"]
    assert names == 2027 - 1994 + 1
    assert recorder.count == 13 + names
    stored = kit.stored("okc")
    assert stored is not None
    assert [(r.from_, r.name) for r in stored.names] == [(1994, "Thunder")]


@pytest.mark.anyio
async def test_the_finals_reads_at_most_18_players_per_finalist_and_lists_the_rest_without_values(
    tmp_path: Path,
    router: respx.MockRouter,
    sleeps: list[float],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    run = run_of(
        named("playoffs finals"),
        tmp_path,
        router,
        sleeps,
        monkeypatch,
        setup=finals_with_20,
    )
    await run.ready()

    with caplog.at_level(logging.WARNING):
        await run.serve()

    assert run.recorder.by_adapter()["player_stats"] == 18 + 18 + 1
    stored = run.stored()
    assert stored is not None
    feed = PlayoffsFinalsFeed.model_validate_json(stored)
    assert feed.averages is not None
    top = next(a for a in feed.averages if a.team_code == finals_tests.TOP)
    assert len(top.players) == 21
    unread = top.players[-2:]
    assert [p.player_id for p in unread] == ["128", "129"]
    assert all(
        p.points is None and p.field_goal_pct is None and p.blocks is None
        for p in unread
    )
    assert all(p.points is not None for p in top.players[:19])
    warnings = [r for r in caplog.records if "players of" in r.getMessage()]
    assert len(warnings) == 1
    assert finals_tests.TOP in warnings[0].getMessage()
    assert run.recorder.count == run.case.budget
