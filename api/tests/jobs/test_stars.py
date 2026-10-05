# api/tests/jobs/test_stars.py
#
# Tests for the stars job.
#
# Tested:
# - Picks the roster player with the highest points plus rebounds plus assists
# - Keeps the first in roster order on a tie
# - Never picks a player who is not on the roster, even with the highest total
# - Returns no star when no roster player has averages
# - Picks the star from the current season when the provider has it for the team
# - Falls back to the previous season, limited to the current roster, when the current season has no averages
# - Falls back to the previous season when the current season has averages only for players who left
# - Asks for the season the roster states and the one before, never one computed from the date
# - Stores each team's star and serves it to a game of those two teams
# - Serves no stars for a game whose team has no star yet
# - Loads the stored stars on start, before any fetch
# - Fetches every team on the first run and not again before the next morning, then again at the morning time the next day
# - Drops a stored star who is no longer on the roster
# - A failed team keeps its stored star, records the reason, does not stop the other teams, and is retried no sooner than five minutes later
# - Records failure when a team has no averages in either season
# - A run stops starting teams once its ten second budget is spent and leaves the rest due for the next tick
# - A team that fails is retried five minutes after the moment it failed, not after the start of the run
# - With a roster fetch that takes the full timeout and always fails, the games job still runs every tick within the budget plus one team, for hours, and on the restart run too
# - A run cut short by its budget records no success, and the run that stores the last team records it
# - Records no success while a failed team waits for its retry, and records it once the team is stored
# - A successful run records success; a run with nothing due makes no request and records nothing
#
# What is covered:
# - Pure logic: happy path, edge cases, error case
# - Job: success, failed run keeps the last valid state
#
# Adapters are fakes passed to the job and times are passed to run(), so no test
# uses the real clock. Every test runs in an empty respx mock: a real request fails.
# The data has one source, so there is no fallback source to test.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_stars.py
#
# SEE: api/app/jobs/stars.py

import asyncio
import datetime as dt
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import HttpUrl

from app.feeds.games import GameStatus, Star
from app.jobs.scheduler import TICK_SECONDS, Scheduler
from app.jobs.stars import JOB, RETRY, RUN_BUDGET, StarsJob, pick_star
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.scoreboard import ScoreboardGame
from app.sources.team_players import PlayerAverages, Roster
from app.sources.teams import TEAM_CODES
from app.storage.state import StateStore

# 12:00 US Eastern (EDT) on 2026-10-05.
NOON = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.UTC)
# 06:00 US Eastern the next day.
NEXT_MORNING = dt.datetime(2026, 10, 6, 10, 0, tzinfo=dt.UTC)
SEASON = 2027
CODES = list(TEAM_CODES.values())


def player(code: str, number: int) -> Star:
    return Star(
        player_id=f"{code}{number}",
        first_name="Ann",
        last_name="Bee",
        team_code=code,
        photo_url=HttpUrl("https://example.com/p.png"),
        short_name="A. Bee",
    )


def averages(player_id: str, total: float) -> PlayerAverages:
    return PlayerAverages(player_id=player_id, points=total, rebounds=0, assists=0)


class FakeSources:
    def __init__(self) -> None:
        self.rosters: dict[str, Roster] = {
            code: Roster(
                season=SEASON,
                team_id=f"id-{code}",
                players=[player(code, 1), player(code, 2)],
            )
            for code in CODES
        }
        self.averages: dict[tuple[str, int], list[PlayerAverages]] = {}
        for code in CODES:
            self.averages[(f"id-{code}", SEASON)] = [
                averages(f"{code}1", 10),
                averages(f"{code}2", 20),
            ]
        self.roster_errors: dict[str, SourceError] = {}
        self.roster_calls: list[str] = []
        self.averages_calls: list[tuple[str, int]] = []

    async def fetch_roster(
        self, client: httpx.AsyncClient, code: str, settings: Settings
    ) -> Roster:
        self.roster_calls.append(code)
        if code in self.roster_errors:
            raise self.roster_errors[code]
        return self.rosters[code]

    async def fetch_season_averages(
        self, client: httpx.AsyncClient, team_id: str, season: int, settings: Settings
    ) -> list[PlayerAverages]:
        self.averages_calls.append((team_id, season))
        return list(self.averages.get((team_id, season), []))


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def sources() -> FakeSources:
    return FakeSources()


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.create_tables()
    return state


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]


def make_job(settings: Settings, store: StateStore, sources: FakeSources) -> StarsJob:
    return StarsJob(
        settings,
        store,
        create_client(),
        fetch_roster=sources.fetch_roster,
        fetch_season_averages=sources.fetch_season_averages,
        clock=lambda: NOON,
    )


def a_game(away: str, home: str) -> ScoreboardGame:
    def team(code: str) -> dict[str, str]:
        return {"code": code, "name": code.title(), "city": code.title()}

    return ScoreboardGame.model_validate(
        {
            "id": "g1",
            "away": team(away),
            "home": team(home),
            "status": GameStatus.SCHEDULED,
            "start_time": NOON,
            "venue": "Arena",
        }
    )


# Group 1: pick_star


def test_picks_the_roster_player_with_the_highest_points_rebounds_and_assists() -> None:
    players = [player("BOS", 1), player("BOS", 2)]
    stats = [
        PlayerAverages(player_id="BOS1", points=20, rebounds=2, assists=2),
        PlayerAverages(player_id="BOS2", points=10, rebounds=8, assists=7),
    ]

    assert pick_star(players, stats) == players[1]


def test_keeps_the_first_in_roster_order_on_a_tie() -> None:
    players = [player("BOS", 1), player("BOS", 2)]
    stats = [averages("BOS2", 15), averages("BOS1", 15)]

    assert pick_star(players, stats) == players[0]


def test_never_picks_a_player_who_is_not_on_the_roster() -> None:
    players = [player("BOS", 1)]
    stats = [averages("gone", 50), averages("BOS1", 5)]

    assert pick_star(players, stats) == players[0]


def test_returns_no_star_when_no_roster_player_has_averages() -> None:
    assert pick_star([player("BOS", 1)], [averages("gone", 50)]) is None
    assert pick_star([player("BOS", 1)], []) is None


# Group 2: the job


@pytest.mark.anyio
async def test_picks_the_star_from_the_current_season_when_the_provider_has_it(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS2"
    assert ("id-BOS", SEASON - 1) not in sources.averages_calls


@pytest.mark.anyio
async def test_falls_back_to_the_previous_season_limited_to_the_current_roster(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = []
    sources.averages[("id-BOS", SEASON - 1)] = [
        averages("gone", 99),
        averages("BOS1", 12),
        averages("BOS2", 11),
    ]
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS1"
    assert store.job_states()[0].last_failure is None


@pytest.mark.anyio
async def test_falls_back_when_the_current_season_has_averages_only_for_players_who_left(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 99)]
    sources.averages[("id-BOS", SEASON - 1)] = [averages("BOS2", 11)]
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS2"


@pytest.mark.anyio
async def test_asks_for_the_season_the_roster_states_and_the_one_before(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.rosters["BOS"] = Roster(
        season=2031, team_id="id-BOS", players=[player("BOS", 1)]
    )
    sources.averages[("id-BOS", 2030)] = [averages("BOS1", 3)]
    job = make_job(settings, store, sources)

    await job.run(NOON)

    boston = [call for call in sources.averages_calls if call[0] == "id-BOS"]
    assert boston == [("id-BOS", 2031), ("id-BOS", 2030)]


@pytest.mark.anyio
async def test_stores_each_teams_star_and_serves_it_to_a_game_of_those_teams(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    await job.run(NOON)

    stars = job.stars_of(a_game("BOS", "NYK"))
    assert stars is not None
    assert (stars.away.player_id, stars.home.player_id) == ("BOS2", "NYK2")
    assert set(store.stars()) == set(CODES)


@pytest.mark.anyio
async def test_serves_no_stars_for_a_game_whose_team_has_no_star_yet(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    assert job.stars_of(a_game("BOS", "NYK")) is None

    sources.roster_errors["NYK"] = SourceError("team_players", "down")
    await job.run(NOON)

    assert job.stars_of(a_game("BOS", "NYK")) is None


@pytest.mark.anyio
async def test_loads_the_stored_stars_on_start_before_any_fetch(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_star(player("BOS", 1))
    store.set_star(player("NYK", 1))

    job = make_job(settings, store, sources)

    stars = job.stars_of(a_game("BOS", "NYK"))
    assert stars is not None and stars.away.player_id == "BOS1"
    assert sources.roster_calls == []


@pytest.mark.anyio
async def test_fetches_every_team_once_a_day_in_the_morning(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    await job.run(NOON)
    assert sorted(sources.roster_calls) == sorted(CODES)

    await job.run(NOON + dt.timedelta(hours=5))
    assert len(sources.roster_calls) == len(CODES)

    await job.run(NEXT_MORNING - dt.timedelta(minutes=1))
    assert len(sources.roster_calls) == len(CODES)

    await job.run(NEXT_MORNING)
    assert len(sources.roster_calls) == 2 * len(CODES)


@pytest.mark.anyio
async def test_drops_a_stored_star_who_is_no_longer_on_the_roster(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_star(player("BOS", 9))
    sources.averages[("id-BOS", SEASON)] = []
    sources.averages[("id-BOS", SEASON - 1)] = []
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert "BOS" not in store.stars()
    assert job.stars_of(a_game("BOS", "NYK")) is None


@pytest.mark.anyio
async def test_a_failed_team_keeps_its_star_records_the_reason_and_retries_later(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_star(player("BOS", 1))
    sources.roster_errors["BOS"] = SourceError("team_players", "request failed")
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS1"
    assert store.stars()["NYK"].player_id == "NYK2"
    state = store.job_states()[0]
    assert state.name == JOB
    assert state.last_failure_reason == "team_players: request failed"
    assert len(store.stars()) == len(CODES)
    calls = len(sources.roster_calls)

    await job.run(NOON + RETRY - dt.timedelta(seconds=1))
    assert len(sources.roster_calls) == calls

    del sources.roster_errors["BOS"]
    await job.run(NOON + RETRY)
    assert sources.roster_calls[calls:] == ["BOS"]
    assert store.stars()["BOS"].player_id == "BOS2"
    assert store.job_states()[0].last_success == NOON + RETRY


@pytest.mark.anyio
async def test_records_failure_when_a_team_has_no_averages_in_either_season(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = []
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.job_states()[0].last_failure_reason == (
        "team_players: team BOS has no season averages for its current roster"
    )
    assert "BOS" not in store.stars()


@pytest.mark.anyio
async def test_a_successful_run_records_success_and_a_run_with_nothing_due_records_nothing(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    await job.run(NOON)
    first = store.job_states()
    await job.run(NOON + dt.timedelta(hours=1))

    assert first[0].last_success == NOON
    assert first[0].last_failure is None
    assert store.job_states() == first


# Group 3: the run budget


class Clock:
    def __init__(self, start: dt.datetime) -> None:
        self.now = start

    def __call__(self) -> dt.datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += dt.timedelta(seconds=seconds)


class SlowSources(FakeSources):
    """Every roster fetch costs `cost` seconds of the clock and may then fail."""

    def __init__(self, clock: Clock, cost: float, *, fails: bool) -> None:
        super().__init__()
        self.clock = clock
        self.cost = cost
        self.fails = fails

    async def fetch_roster(
        self, client: httpx.AsyncClient, code: str, settings: Settings
    ) -> Roster:
        self.clock.advance(self.cost)
        if self.fails:
            self.roster_calls.append(code)
            raise SourceError("team_players", "request failed")
        return await super().fetch_roster(client, code, settings)


class GamesStub:
    name = "games"

    def __init__(self) -> None:
        self.runs: list[dt.datetime] = []

    async def run(self, now: dt.datetime) -> None:
        self.runs.append(now)


class Driver:
    """Runs a scheduler for a number of ticks on a clock that only the fakes move."""

    def __init__(self, clock: Clock, ticks: int) -> None:
        self.clock = clock
        self.left = ticks
        self.done = asyncio.Event()

    async def sleep(self, seconds: float) -> None:
        self.left -= 1
        if self.left <= 0:
            self.done.set()
            await asyncio.Event().wait()
        self.clock.advance(seconds)


async def drive(
    job: StarsJob, games: GamesStub, store: StateStore, clock: Clock, ticks: int
) -> None:
    driver = Driver(clock, ticks)
    scheduler = Scheduler([job, games], store, clock=clock, sleep=driver.sleep)
    scheduler.start()
    await driver.done.wait()
    await scheduler.stop()


def make_slow_job(
    settings: Settings, store: StateStore, sources: SlowSources, clock: Clock
) -> StarsJob:
    return StarsJob(
        settings,
        store,
        create_client(),
        fetch_roster=sources.fetch_roster,
        fetch_season_averages=sources.fetch_season_averages,
        clock=clock,
    )


@pytest.mark.anyio
async def test_a_run_stops_starting_teams_once_its_budget_is_spent(
    settings: Settings, store: StateStore
) -> None:
    clock = Clock(NOON)
    sources = SlowSources(clock, 3, fails=False)
    job = make_slow_job(settings, store, sources, clock)

    await job.run(NOON)

    # Teams start at 0, 3, 6 and 9 seconds; the one at 12 seconds does not.
    assert len(sources.roster_calls) == 4
    await job.run(clock.now)
    assert len(sources.roster_calls) == 8


@pytest.mark.anyio
async def test_a_run_cut_short_by_its_budget_records_no_success(
    settings: Settings, store: StateStore
) -> None:
    clock = Clock(NOON)
    sources = SlowSources(clock, 3, fails=False)
    job = make_slow_job(settings, store, sources, clock)

    await job.run(NOON)
    assert store.job_states() == []

    last = clock.now
    for _ in range(len(CODES)):
        if len(store.stars()) >= len(set(CODES)):
            break
        assert store.job_states() == []
        last = clock.now
        await job.run(last)

    assert len(store.stars()) == len(set(CODES))
    state = store.job_states()[0]
    assert state.last_success == last
    assert state.last_failure is None


@pytest.mark.anyio
async def test_records_no_success_while_a_failed_team_waits_for_its_retry(
    settings: Settings, store: StateStore
) -> None:
    clock = Clock(NOON)
    sources = SlowSources(clock, 1, fails=False)
    sources.roster_errors[CODES[0]] = SourceError("team_players", "request failed")
    job = make_slow_job(settings, store, sources, clock)

    for _ in range(5):
        await job.run(clock.now)

    assert len(store.stars()) == len(set(CODES)) - 1
    state = store.job_states()[0]
    assert state.last_success is None
    assert state.last_failure_reason == "team_players: request failed"

    del sources.roster_errors[CODES[0]]
    later = NOON + RETRY + dt.timedelta(minutes=1)
    await job.run(later)
    assert store.job_states()[0].last_success == later


@pytest.mark.anyio
async def test_a_failed_team_is_retried_five_minutes_after_it_failed(
    settings: Settings, store: StateStore
) -> None:
    clock = Clock(NOON)
    sources = SlowSources(clock, 10, fails=True)
    job = make_slow_job(settings, store, sources, clock)

    await job.run(NOON)
    first = sources.roster_calls[0]
    assert sources.roster_calls == [first]

    # The team failed at NOON + 10 s: not due yet one second before RETRY later.
    sources.roster_calls.clear()
    await job.run(NOON + RETRY + dt.timedelta(seconds=9))
    assert first not in sources.roster_calls
    sources.roster_calls.clear()
    await job.run(NOON + RETRY + dt.timedelta(seconds=10))
    assert first in sources.roster_calls


@pytest.mark.anyio
async def test_a_total_outage_never_delays_the_games_job_by_more_than_the_budget_and_a_team(
    settings: Settings, store: StateStore
) -> None:
    clock = Clock(NOON)
    sources = SlowSources(clock, 10, fails=True)
    job = make_slow_job(settings, store, sources, clock)
    games = GamesStub()
    ticks = 2 * 60 * 2  # two hours of 30 second ticks, from the restart run

    await drive(job, games, store, clock, ticks)

    assert len(games.runs) == ticks
    bound = dt.timedelta(seconds=TICK_SECONDS) + RUN_BUDGET + dt.timedelta(seconds=10)
    gaps = [b - a for a, b in zip(games.runs, games.runs[1:], strict=False)]
    assert max(gaps) <= bound
    assert dt.timedelta(seconds=TICK_SECONDS) <= min(gaps)


@pytest.mark.anyio
async def test_the_restart_run_is_bounded_and_the_other_teams_are_done_on_later_ticks(
    settings: Settings, store: StateStore
) -> None:
    clock = Clock(NOON)
    sources = SlowSources(clock, 3, fails=False)
    job = make_slow_job(settings, store, sources, clock)
    games = GamesStub()

    await drive(job, games, store, clock, 10)

    assert len(store.stars()) == len(CODES)
    gaps = [b - a for a, b in zip(games.runs, games.runs[1:], strict=False)]
    assert max(gaps) <= dt.timedelta(seconds=TICK_SECONDS) + RUN_BUDGET + dt.timedelta(
        seconds=3
    )
