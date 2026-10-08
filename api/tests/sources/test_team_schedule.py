# api/tests/sources/test_team_schedule.py
#
# Tests for the team schedule adapter.
#
# Tested:
# - Maps the last five completed games newest first with both scores
# - Marks home games and results from the side of the requested team
# - Dates games on the US Eastern day
# - Returns no last games when no game is completed
# - Maps the arena of each completed game by game id
# - Requests the schedule URL built from the template and the provider team code, including a code that differs from the standard one
# - Raises the source error when the team is missing from a game, on a game without a score, an unknown team code, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a team's schedule for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are a recorded schedule trimmed to the fields the adapter
# reads: schedule.json keeps seven completed games, the four games of one
# season series among them, and schedule-preseason.json keeps two games not
# yet played, without scores.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_team_schedule.py
#
# SEE: api/app/sources/team_schedule.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.game_detail import GameResult
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.team_schedule import TeamSchedule, fetch_team_schedule
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "team_schedule"
TEMPLATE = "https://example.com/teams/{team}/schedule"
URL = "https://example.com/teams/BOS/schedule"

Payload = dict[str, Any]


def load(name: str = "schedule.json") -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


def event(payload: Payload, game_id: str) -> Payload:
    found: Payload = next(e for e in payload["events"] if e["id"] == game_id)
    return found


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, team_schedule_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings, team_code: str = "BOS") -> TeamSchedule:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_team_schedule(client, team_code, settings)


async def fetch_error(settings: Settings, team_code: str = "BOS") -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings, team_code)
    return raised.value


async def fetch_error_of(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> SourceError:
    mock.get(URL).respond(json=payload)
    return await fetch_error(settings)


@pytest.mark.anyio
async def test_maps_the_last_five_completed_games_newest_first_with_both_scores(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    schedule = await fetch(settings)

    games = schedule.last_games
    assert [g.date.isoformat() for g in games] == [
        "2026-04-12",
        "2025-11-23",
        "2025-11-09",
        "2025-11-07",
        "2025-10-26",
    ]
    assert [g.opponent for g in games] == ["ORL", "ORL", "ORL", "ORL", "DET"]
    assert [(g.team_score, g.opponent_score) for g in games] == [
        (113, 108),
        (138, 129),
        (111, 107),
        (110, 123),
        (113, 119),
    ]


@pytest.mark.anyio
async def test_marks_home_games_and_results_from_the_team_side(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    games = (await fetch(settings)).last_games

    assert [g.is_home for g in games] == [True, True, False, False, False]
    assert [g.result for g in games] == [
        GameResult.WIN,
        GameResult.WIN,
        GameResult.WIN,
        GameResult.LOSS,
        GameResult.LOSS,
    ]


@pytest.mark.anyio
async def test_dates_games_on_the_us_eastern_day(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    assert event(payload, "401809510")["date"] == "2025-11-08T00:00Z"
    mock.get(URL).respond(json=payload)

    games = (await fetch(settings)).last_games

    assert games[3].date.isoformat() == "2025-11-07"


@pytest.mark.anyio
async def test_returns_no_last_games_when_none_is_completed(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("schedule-preseason.json"))

    schedule = await fetch(settings)

    assert schedule.last_games == []
    assert schedule.arenas == {}


@pytest.mark.anyio
async def test_maps_the_arena_of_each_completed_game_by_game_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    arenas = (await fetch(settings)).arenas

    assert len(arenas) == 7
    assert arenas["401811041"] == "TD Garden"
    assert arenas["401809510"] == "Kia Center"
    assert arenas["401809945"] == "Madison Square Garden"


@pytest.mark.anyio
async def test_requests_the_schedule_url_built_from_the_provider_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    for e in payload["events"]:
        for competitor in e["competitions"][0]["competitors"]:
            if competitor["team"]["abbreviation"] == "BOS":
                competitor["team"]["abbreviation"] = "GS"
    route = mock.get("https://example.com/teams/GS/schedule").respond(json=payload)

    schedule = await fetch(settings, "GSW")

    assert route.call_count == 1
    assert len(schedule.last_games) == 5


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_team_is_missing_from_a_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    competitors = event(payload, "401811041")["competitions"][0]["competitors"]
    competitors[0]["team"]["abbreviation"] = "MIA"

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "team BOS is missing from game 401811041"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_completed_game_without_a_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del event(payload, "401811041")["competitions"][0]["competitors"][0]["score"]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "game 401811041 has no score"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    settings: Settings,
) -> None:
    with respx.mock:
        error = await fetch_error(settings, "XXX")

    assert error.reason == "unknown team code 'XXX'"


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"events": 3}, {"events": [{"id": "1"}]}])
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("fails", "reason"),
    [
        (
            lambda route: route.mock(side_effect=httpx.ReadTimeout("slow")),
            "request timed out",
        ),
        (lambda route: route.respond(status_code=500), "responded with status 500"),
    ],
    ids=["timeout", "error status"],
)
async def test_raises_the_source_error_on_a_timeout_and_an_error_status(
    mock: respx.MockRouter, settings: Settings, fails: Any, reason: str
) -> None:
    fails(mock.get(URL))

    error = await fetch_error(settings)

    assert error.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_schedule_url_is_not_configured() -> (
    None
):
    unset = Settings(_env_file=None, team_schedule_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "team schedule URL is not configured"


def clocked(tmp_path: Path, clock: list[dt.datetime]) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: clock[0])


@pytest.mark.anyio
async def test_reuses_a_team_schedule_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    async with clocked(tmp_path, clock) as client:
        await fetch_team_schedule(client, "BOS", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_team_schedule(client, "BOS", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_team_schedule(client, "BOS", settings)

    assert route.call_count == 2
