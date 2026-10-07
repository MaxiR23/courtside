# api/tests/sources/test_league_injuries.py
#
# Tests for the league injuries adapter.
#
# Tested:
# - Maps recorded injuries by team code, with status and comment
# - Attributes the injuries to the team entry, not to the athlete's team
# - Maps the team ids of codes that differ from the standard ones
# - Requests the league injuries URL from the settings
# - Raises the source error on an unknown team id, an unknown injury status, an invalid payload, an empty name, a timeout, an error status and a missing URL
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixture is the recorded league injuries trimmed to three teams and to the
# fields the adapter reads. One athlete's team differs from the entry's team,
# as recorded.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_league_injuries.py
#
# SEE: api/app/sources/league_injuries.py

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.game_detail import InjuryStatus
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.league_injuries import LeagueInjuries, fetch_league_injuries

FIXTURES = Path(__file__).parent / "fixtures" / "league_injuries"
URL = "https://example.com/injuries"

Payload = dict[str, Any]


def load() -> Payload:
    payload: Payload = json.loads(
        (FIXTURES / "injuries.json").read_text(encoding="utf-8")
    )
    return payload


def team_entry(payload: Payload, team_id: str) -> Payload:
    found: Payload = next(e for e in payload["injuries"] if e["id"] == team_id)
    return found


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, league_injuries_url=URL)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> LeagueInjuries:
    async with create_client() as client:
        return await fetch_league_injuries(client, settings)


async def fetch_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


async def fetch_error_of(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> SourceError:
    mock.get(URL).respond(json=payload)
    return await fetch_error(settings)


@pytest.mark.anyio
async def test_maps_recorded_injuries_by_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    league = await fetch(settings)

    assert set(league.teams) == {"GSW", "DAL", "ATL"}
    golden_state = league.teams["GSW"]
    assert [(i.display_name, i.status) for i in golden_state] == [
        ("Stephen Curry", InjuryStatus.DAY_TO_DAY),
        ("Jimmy Butler III", InjuryStatus.OUT),
    ]
    assert golden_state[1].comment is not None
    assert len(league.teams["ATL"]) == 1


@pytest.mark.anyio
async def test_attributes_injuries_to_the_team_entry_not_the_athlete_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    league = await fetch(settings)

    assert {i.display_name for i in league.teams["DAL"]} == {
        "Dereck Lively II",
        "Santi Aldama",
    }
    assert "MEM" not in league.teams


@pytest.mark.anyio
async def test_maps_team_ids_of_codes_that_differ(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    league = await fetch(settings)

    assert "GSW" in league.teams
    assert "GS" not in league.teams


@pytest.mark.anyio
async def test_skips_a_team_without_injuries(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    team_entry(payload, "1")["injuries"] = []

    mock.get(URL).respond(json=payload)

    assert "ATL" not in (await fetch(settings)).teams


@pytest.mark.anyio
async def test_gives_a_missing_comment_as_none(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del team_entry(payload, "1")["injuries"][0]["shortComment"]
    mock.get(URL).respond(json=payload)

    league = await fetch(settings)

    assert league.teams["ATL"][0].comment is None


@pytest.mark.anyio
async def test_requests_the_league_injuries_url_from_settings(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(URL).respond(json=load())

    await fetch(settings)

    assert route.call_count == 1


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    team_entry(payload, "1")["id"] = "99"

    error = await fetch_error_of(mock, settings, payload)

    assert error.source == "league_injuries"
    assert error.reason == "unknown team id '99'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_injury_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    team_entry(payload, "1")["injuries"][0]["status"] = "Suspended"

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "unknown injury status"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_empty_athlete_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    team_entry(payload, "1")["injuries"][0]["athlete"]["displayName"] = ""

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("injuries are invalid: ")


def without_id() -> Payload:
    payload = load()
    del payload["injuries"][0]["id"]
    return payload


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [{}, {"injuries": 3}, without_id()],
    ids=["empty", "not a list", "entry without id"],
)
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
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None, league_injuries_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "league injuries URL is not configured"
