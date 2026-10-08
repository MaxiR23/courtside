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
# - Picks the star from the roster players' individual averages when no roster player is among the season leaders, for the season in use
# - Asks for the individual averages of the previous season when it is the season in use
# - Makes no individual request when a roster player is among the leaders
# - Skips a roster player who has no individual averages
# - A failed individual fetch keeps the last known star and records the reason
# - A failed individual fetch moves on to the previous season's leaders
# - A failed individual fetch with no star from the previous season either records its reason and keeps the stored star
# - Keeps the last known star when no star can be picked
# - Replaces a stored star who left the roster only once a new one is picked
# - Fetches every due team concurrently
# - Has every star only once every team has one, and from the start when the store holds every team
# - A failed team keeps its stored star, records the reason, does not stop the other teams, and is retried no sooner than five minutes later
# - Records failure when a team has no averages in either season
# - A team that fails is retried five minutes after the moment it failed, not after the start of the run
# - Records no success while a failed team waits for its retry, and records it once the team is stored
# - A successful run records success; a run with nothing due makes no request and records nothing
# - Passes the final time of the team's latest final game to individual requests
# - Passes no final game when the team has no known final game
# - A team without a leader on its roster costs one request per player and none the next day without a game
# - Requests each player's individual averages once more after the team has a final game
# - A team with a leader on its roster makes no individual request
# - Requests each team's roster and leaders once, also when a team is retried the same day
# - A run a few seconds earlier than the previous day's does not reuse the previous day's roster and leaders
# - Exposes every fetched roster's players with their team, with no request beyond the roster fetches
# - Is not ready until every team's roster has been fetched, and a failed roster fetch keeps it not ready until the retry succeeds
# - Records a roster even when the team's averages then fail
# - A newer roster replaces the team's players, and a player listed by another team's newer roster belongs to it
# - Calls after_run after a run with due teams and not after a run with none
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
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import HttpUrl

from app.feeds.games import GameStatus, Star
from app.jobs.stars import JOB, NO_FINAL_GAME, RETRY, StarsJob, pick_star
from app.settings import Settings
from app.sources import team_players
from app.sources.http import Freshness, SourceError, create_client
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
        self.player_averages: dict[tuple[str, int], PlayerAverages] = {}
        self.player_errors: dict[str, SourceError] = {}
        self.player_calls: list[tuple[str, int]] = []
        self.roster_errors: dict[str, SourceError] = {}
        self.roster_calls: list[str] = []
        self.averages_calls: list[tuple[str, int]] = []
        self.player_fresh: list[tuple[str, Freshness]] = []

    async def fetch_roster(
        self,
        client: httpx.AsyncClient,
        code: str,
        settings: Settings,
    ) -> Roster:
        self.roster_calls.append(code)
        if code in self.roster_errors:
            raise self.roster_errors[code]
        return self.rosters[code]

    async def fetch_season_averages(
        self,
        client: httpx.AsyncClient,
        team_id: str,
        season: int,
        settings: Settings,
    ) -> list[PlayerAverages]:
        self.averages_calls.append((team_id, season))
        return list(self.averages.get((team_id, season), []))

    async def fetch_player_averages(
        self,
        client: httpx.AsyncClient,
        player_id: str,
        season: int,
        settings: Settings,
        fresh: Freshness,
    ) -> PlayerAverages | None:
        self.player_fresh.append((player_id, fresh))
        self.player_calls.append((player_id, season))
        if player_id in self.player_errors:
            raise self.player_errors[player_id]
        return self.player_averages.get((player_id, season))


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
    state.migrate()
    return state


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path)  # type: ignore[call-arg]


def make_job(settings: Settings, store: StateStore, sources: FakeSources) -> StarsJob:
    return StarsJob(
        settings,
        store,
        create_client(store),
        fetch_roster=sources.fetch_roster,
        fetch_season_averages=sources.fetch_season_averages,
        fetch_player_averages=sources.fetch_player_averages,
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
    assert ("BOS1", SEASON) in sources.player_calls


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
async def test_keeps_the_last_known_star_when_no_star_can_be_picked(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_star(player("BOS", 9))
    sources.averages[("id-BOS", SEASON)] = []
    sources.averages[("id-BOS", SEASON - 1)] = []
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS9"
    stars = job.stars_of(a_game("BOS", "NYK"))
    assert stars is not None and stars.away.player_id == "BOS9"
    assert store.job_states()[0].last_failure is not None


@pytest.mark.anyio
async def test_replaces_a_stored_star_who_left_the_roster_once_a_new_one_is_picked(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_star(player("BOS", 9))
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS2"
    stars = job.stars_of(a_game("BOS", "NYK"))
    assert stars is not None and stars.away.player_id == "BOS2"


@pytest.mark.anyio
async def test_picks_the_star_from_individual_averages_when_no_roster_player_is_among_the_leaders(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 99)]
    sources.player_averages[("BOS1", SEASON)] = averages("BOS1", 10)
    sources.player_averages[("BOS2", SEASON)] = averages("BOS2", 30)
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS2"
    boston = [call for call in sources.player_calls if call[0].startswith("BOS")]
    assert boston == [("BOS1", SEASON), ("BOS2", SEASON)]


@pytest.mark.anyio
async def test_asks_individual_averages_for_the_previous_season_when_it_is_the_season_in_use(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = []
    sources.averages[("id-BOS", SEASON - 1)] = [averages("gone", 99)]
    sources.player_averages[("BOS1", SEASON - 1)] = averages("BOS1", 10)
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS1"
    boston = [call for call in sources.player_calls if call[0].startswith("BOS")]
    assert all(season == SEASON - 1 for _, season in boston)
    assert boston


@pytest.mark.anyio
async def test_does_not_fetch_individual_averages_when_a_roster_player_is_among_the_leaders(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert sources.player_calls == []


@pytest.mark.anyio
async def test_skips_a_roster_player_without_individual_averages(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 99)]
    sources.player_averages[("BOS2", SEASON)] = averages("BOS2", 5)
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS2"


@pytest.mark.anyio
async def test_a_failed_individual_fetch_keeps_the_last_known_star_and_records_the_reason(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_star(player("BOS", 9))
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 99)]
    sources.player_errors["BOS1"] = SourceError("team_players", "request failed")
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS9"
    assert store.job_states()[0].last_failure_reason == ("team_players: request failed")


@pytest.mark.anyio
async def test_a_failed_individual_fetch_moves_on_to_the_previous_season(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 99)]
    sources.averages[("id-BOS", SEASON - 1)] = [averages("BOS2", 11)]
    sources.player_errors["BOS1"] = SourceError("team_players", "request failed")
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS2"
    assert ("id-BOS", SEASON - 1) in sources.averages_calls


@pytest.mark.anyio
async def test_a_failed_individual_fetch_is_recorded_when_the_previous_season_gives_no_star(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    store.set_star(player("BOS", 9))
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 99)]
    sources.averages[("id-BOS", SEASON - 1)] = [averages("gone", 99)]
    sources.player_errors["BOS1"] = SourceError("team_players", "request failed")
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert store.stars()["BOS"].player_id == "BOS9"
    assert store.job_states()[0].last_failure_reason == ("team_players: request failed")


@pytest.mark.anyio
async def test_fetches_every_due_team_concurrently(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    in_flight = 0
    most = 0
    original = sources.fetch_roster

    async def roster(
        client: httpx.AsyncClient, code: str, settings: Settings
    ) -> Roster:
        nonlocal in_flight, most
        in_flight += 1
        most = max(most, in_flight)
        for _ in range(3):
            await asyncio.sleep(0)
        in_flight -= 1
        return await original(client, code, settings)

    job = StarsJob(
        settings,
        store,
        create_client(store),
        fetch_roster=roster,
        fetch_season_averages=sources.fetch_season_averages,
        fetch_player_averages=sources.fetch_player_averages,
        clock=lambda: NOON,
    )

    await job.run(NOON)

    assert most == len(set(CODES))


@pytest.mark.anyio
async def test_has_every_star_only_once_every_team_has_one(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.roster_errors["BOS"] = SourceError("team_players", "down")
    job = make_job(settings, store, sources)
    assert not job.has_every_star()

    await job.run(NOON)
    assert not job.has_every_star()

    del sources.roster_errors["BOS"]
    await job.run(NOON + RETRY)
    assert job.has_every_star()


@pytest.mark.anyio
async def test_has_every_star_on_start_when_the_store_holds_every_team(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    for code in set(CODES):
        store.set_star(player(code, 1))

    assert make_job(settings, store, sources).has_every_star()


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


# Group 3: timing, with a clock the fakes move


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
        self,
        client: httpx.AsyncClient,
        code: str,
        settings: Settings,
    ) -> Roster:
        self.clock.advance(self.cost)
        if self.fails:
            self.roster_calls.append(code)
            raise SourceError("team_players", "request failed")
        return await super().fetch_roster(client, code, settings)


def make_slow_job(
    settings: Settings, store: StateStore, sources: SlowSources, clock: Clock
) -> StarsJob:
    return StarsJob(
        settings,
        store,
        create_client(store),
        fetch_roster=sources.fetch_roster,
        fetch_season_averages=sources.fetch_season_averages,
        fetch_player_averages=sources.fetch_player_averages,
        clock=clock,
    )


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
    assert len(sources.roster_calls) == len(set(CODES))

    # The team failed at NOON + 10 s: not due yet one second before RETRY later.
    sources.roster_calls.clear()
    await job.run(NOON + RETRY + dt.timedelta(seconds=9))
    assert first not in sources.roster_calls
    sources.roster_calls.clear()
    await job.run(NOON + RETRY + dt.timedelta(seconds=10))
    assert first in sources.roster_calls


# Group 4: freshness passed to the source cache


FIXTURES = Path(__file__).parent / "fixtures" / "stars"


def final_game(game_id: str, away: str, home: str) -> ScoreboardGame:
    return a_game(away, home).model_copy(update={"id": game_id})


def make_job_with_games(
    settings: Settings,
    store: StateStore,
    sources: FakeSources,
    games: list[ScoreboardGame],
) -> StarsJob:
    return StarsJob(
        settings,
        store,
        create_client(store),
        fetch_roster=sources.fetch_roster,
        fetch_season_averages=sources.fetch_season_averages,
        fetch_player_averages=sources.fetch_player_averages,
        final_games=lambda: games,
        clock=lambda: NOON,
    )


@pytest.mark.anyio
async def test_passes_the_final_time_of_the_teams_latest_final_game_to_individual_requests(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 5)]
    earlier = NOON - dt.timedelta(days=2)
    later = NOON - dt.timedelta(days=1)
    other = NOON - dt.timedelta(hours=1)
    games = [
        final_game("g1", "BOS", "MIA"),
        final_game("g2", "NYK", "BOS"),
        final_game("g3", "NYK", "MIA"),
    ]
    store.set_final_time("g1", dt.date(2026, 10, 3), earlier)
    store.set_final_time("g2", dt.date(2026, 10, 4), later)
    store.set_final_time("g3", dt.date(2026, 10, 5), other)
    job = make_job_with_games(settings, store, sources, games)

    await job.run(NOON)

    assert sources.player_fresh == [("BOS1", later), ("BOS2", later)]


@pytest.mark.anyio
async def test_passes_no_final_game_when_the_team_has_no_known_final_game(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = [averages("gone", 5)]
    games = [final_game("g1", "NYK", "MIA"), final_game("g2", "BOS", "MIA")]
    store.set_final_time("g1", dt.date(2026, 10, 5), NOON)
    job = make_job_with_games(settings, store, sources, games)

    await job.run(NOON)

    assert sources.player_fresh == [("BOS1", NO_FINAL_GAME), ("BOS2", NO_FINAL_GAME)]


# Group 5: source requests over the real team players adapters

MORNING = dt.datetime(2026, 10, 5, 10, 0, tzinfo=dt.UTC)
BASE = "https://example.com/"


def read_fixture(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


class RequestsHarness:
    """A stars job over the real adapters, one client and one counted respx route.

    Route answers are source requests: the source cache decides which go out.
    """

    def __init__(self, path: Path) -> None:
        self.clock = [MORNING]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(  # type: ignore[call-arg]
            _env_file=None,
            data_dir=path,
            team_roster_url=BASE + "teams/{team}/roster",
            team_averages_url=BASE + "seasons/{season}/teams/{team}/leaders",
            player_averages_url=BASE + "seasons/{season}/athletes/{player_id}/stats",
            player_photo_url=BASE + "players/{player_id}.png",
        )
        self.paths: list[str] = []
        self.games: list[ScoreboardGame] = []
        self.failing_once: set[str] = set()
        respx.get(url__startswith=BASE).mock(side_effect=self.answer)
        self.job = StarsJob(
            self.settings,
            self.store,
            create_client(self.store, clock=lambda: self.clock[0]),
            final_games=lambda: self.games,
            clock=lambda: self.clock[0],
        )

    def answer(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.paths.append(path)
        parts = path.strip("/").split("/")
        if parts[0] == "teams":
            code = TEAM_CODES[parts[1]]
            roster = read_fixture("roster.json")
            roster["team"]["id"] = f"id-{code}"
            for athlete, number in zip(roster["athletes"], (1, 2), strict=True):
                athlete["id"] = f"{code}{number}"
            return httpx.Response(200, json=roster)
        if parts[0] == "seasons" and parts[2] == "teams":
            if parts[1] != str(SEASON):
                return httpx.Response(404)
            code = parts[3].removeprefix("id-")
            leaders = read_fixture("leaders.json")
            leader = leaders["categories"][0]["leaders"][0]["athlete"]
            owner = "gone" if code == "BOS" else f"{code}2"
            leader["$ref"] = f"https://example.com/athletes/{owner}"
            return httpx.Response(200, json=leaders)
        if parts[1] != str(SEASON):
            return httpx.Response(404)
        if parts[3] in self.failing_once:
            self.failing_once.discard(parts[3])
            return httpx.Response(503)
        return httpx.Response(200, json=read_fixture("player_averages.json"))

    async def run(self, now: dt.datetime) -> None:
        self.clock[0] = now
        await self.job.run(now)

    def count(self, path: str) -> int:
        return self.paths.count(path)

    def individual(self, player_id: str) -> int:
        return self.count(f"/seasons/{SEASON}/athletes/{player_id}/stats")

    def roster_and_leaders(self, code: str) -> tuple[int, int]:
        provider = team_players.PROVIDER_CODES[code]
        return (
            self.count(f"/teams/{provider}/roster"),
            self.count(f"/seasons/{SEASON}/teams/id-{code}/leaders"),
        )


@pytest.fixture
def requests(tmp_path: Path) -> RequestsHarness:
    return RequestsHarness(tmp_path)


@pytest.mark.anyio
async def test_a_team_without_a_leader_on_its_roster_costs_one_request_per_player_and_none_the_next_day_without_a_game(
    requests: RequestsHarness,
) -> None:
    requests.games = [final_game("g1", "NYK", "MIA"), final_game("g2", "BOS", "MIA")]
    requests.store.set_final_time(
        "g1", dt.date(2026, 10, 5), MORNING + dt.timedelta(hours=1)
    )
    requests.store.set_final_time(
        "g2", dt.date(2026, 10, 4), MORNING - dt.timedelta(hours=1)
    )

    await requests.run(MORNING)
    assert (requests.individual("BOS1"), requests.individual("BOS2")) == (1, 1)

    await requests.run(NEXT_MORNING)
    assert (requests.individual("BOS1"), requests.individual("BOS2")) == (1, 1)
    assert requests.store.stars()["BOS"].player_id in {"BOS1", "BOS2"}


@pytest.mark.anyio
async def test_fetches_individual_averages_again_once_each_the_day_after_the_team_has_a_final_game(
    requests: RequestsHarness,
) -> None:
    await requests.run(MORNING)
    requests.games = [final_game("g1", "BOS", "MIA")]
    requests.store.set_final_time(
        "g1", dt.date(2026, 10, 5), MORNING + dt.timedelta(hours=5)
    )

    await requests.run(NEXT_MORNING)
    assert (requests.individual("BOS1"), requests.individual("BOS2")) == (2, 2)

    await requests.run(NEXT_MORNING + dt.timedelta(days=1))
    assert (requests.individual("BOS1"), requests.individual("BOS2")) == (2, 2)


@pytest.mark.anyio
async def test_a_team_with_a_leader_on_its_roster_makes_no_individual_request(
    requests: RequestsHarness,
) -> None:
    requests.games = [final_game("g1", "NYK", "BOS")]
    requests.store.set_final_time(
        "g1", dt.date(2026, 10, 5), MORNING + dt.timedelta(hours=5)
    )

    await requests.run(MORNING)
    await requests.run(NEXT_MORNING)

    athlete_paths = {path for path in requests.paths if "/athletes/" in path}
    assert athlete_paths
    assert all("/athletes/BOS" in path for path in athlete_paths)


@pytest.mark.anyio
async def test_requests_each_teams_roster_and_leaders_once_also_when_a_team_is_retried_the_same_day(
    requests: RequestsHarness,
) -> None:
    requests.failing_once.add("BOS1")

    await requests.run(MORNING)
    assert "BOS" not in requests.store.stars()
    await requests.run(MORNING + RETRY)
    assert "BOS" in requests.store.stars()
    await requests.run(MORNING + dt.timedelta(hours=5))

    for code in set(CODES):
        assert requests.roster_and_leaders(code) == (1, 1)
    assert (requests.individual("BOS1"), requests.individual("BOS2")) == (2, 1)


@pytest.mark.anyio
async def test_exposes_every_fetched_rosters_players_with_their_team_and_no_extra_request(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert job.player_team("BOS1") == "BOS"
    assert job.player_team("NYK2") == "NYK"
    assert job.player_team("nobody") is None
    assert sorted(sources.roster_calls) == sorted(CODES)
    assert job.rosters_ready()


@pytest.mark.anyio
async def test_is_not_ready_until_every_roster_is_fetched_and_a_failed_fetch_keeps_it_not_ready(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    assert not job.rosters_ready()
    sources.roster_errors["BOS"] = SourceError("roster", "down")

    await job.run(NOON)

    assert not job.rosters_ready()
    assert job.player_team("BOS1") is None
    assert job.player_team("NYK1") == "NYK"
    del sources.roster_errors["BOS"]
    await job.run(NOON + RETRY)
    assert job.rosters_ready()
    assert job.player_team("BOS1") == "BOS"


@pytest.mark.anyio
async def test_records_a_roster_even_when_the_teams_averages_then_fail(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    sources.averages[("id-BOS", SEASON)] = []
    job = make_job(settings, store, sources)

    await job.run(NOON)

    assert "BOS" not in store.stars()
    assert job.player_team("BOS1") == "BOS"


@pytest.mark.anyio
async def test_a_newer_roster_replaces_the_teams_players_and_moves_a_player_to_the_new_team(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    job = make_job(settings, store, sources)
    await job.run(NOON)
    sources.rosters["BOS"] = Roster(
        season=SEASON,
        team_id="id-BOS",
        players=[player("BOS", 3), player("BOS", 4)],
    )
    sources.rosters["NYK"] = Roster(
        season=SEASON,
        team_id="id-NYK",
        players=[player("NYK", 1), player("BOS", 2)],
    )
    sources.averages[("id-BOS", SEASON)] = [averages("BOS3", 20)]
    sources.averages[("id-NYK", SEASON)] = [averages("NYK1", 20)]

    await job.run(NEXT_MORNING)

    assert job.player_team("BOS1") is None
    assert job.player_team("BOS3") == "BOS"
    assert job.player_team("NYK2") is None
    assert job.player_team("BOS2") == "NYK"
    assert job.player_team("NYK1") == "NYK"


@pytest.mark.anyio
async def test_calls_after_run_after_a_run_with_due_teams_and_not_after_a_run_with_none(
    settings: Settings, store: StateStore, sources: FakeSources
) -> None:
    calls: list[int] = []
    job = StarsJob(
        settings,
        store,
        create_client(store),
        fetch_roster=sources.fetch_roster,
        fetch_season_averages=sources.fetch_season_averages,
        fetch_player_averages=sources.fetch_player_averages,
        clock=lambda: NOON,
        after_run=lambda: calls.append(1),
    )

    await job.run(NOON)
    await job.run(NOON + dt.timedelta(seconds=30))

    assert calls == [1]
