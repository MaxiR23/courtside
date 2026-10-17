# api/tests/sources/test_season_team.py
#
# Tests for the season team adapter.
#
# Tested:
# - Maps a recorded season team's abbreviation, names and location
# - Maps a season team whose isActive is false, and a body without isActive
# - Returns None on a 404
# - Requests the season and the provider team id of the code
# - Raises the source error on an invalid payload, an unknown team code, a timeout, an error status and a missing URL
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_season_team.py
#
# SEE: api/app/sources/season_team.py

import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.season_team import SeasonTeam, fetch_season_team
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "season_team"
TEMPLATE = "https://example.com/seasons/{season}/teams/{team_id}"
URL = "https://example.com/seasons/2004/teams/25"

Payload = dict[str, Any]


def load(name: str = "active") -> Payload:
    payload: Payload = json.loads(
        (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    )
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, season_team_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings, team_code: str = "OKC") -> SeasonTeam | None:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_season_team(client, team_code, 2004, settings)


async def fetch_error(settings: Settings, team_code: str = "OKC") -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings, team_code)
    return raised.value


@pytest.mark.anyio
async def test_maps_a_recorded_season_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    team = await fetch(settings)

    assert team is not None
    assert team.team_id == "25"
    assert team.abbreviation == "OKC"
    assert team.display_name == "Oklahoma City Thunder"
    assert (team.location, team.name) == ("Oklahoma City", "Thunder")


@pytest.mark.anyio
async def test_maps_a_season_team_whose_is_active_is_false(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("inactive"))

    team = await fetch(settings)

    assert team is not None
    assert team.abbreviation == "SEA"
    assert (team.location, team.name) == ("Seattle", "Harbor Gulls")


@pytest.mark.anyio
async def test_maps_a_body_without_is_active(
    mock: respx.MockRouter, settings: Settings
) -> None:
    body = load()
    del body["isActive"]
    mock.get(URL).respond(json=body)

    team = await fetch(settings)

    assert team is not None
    assert team.name == "Thunder"


@pytest.mark.anyio
async def test_returns_none_on_a_404(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(status_code=404)

    assert await fetch(settings) is None


@pytest.mark.anyio
async def test_requests_the_season_and_the_provider_team_id_of_the_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get("https://example.com/seasons/2004/teams/9").respond(json=load())

    await fetch(settings, "GSW")

    assert route.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["invalid"])
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, name: str
) -> None:
    mock.get(URL).respond(json=load(name))

    error = await fetch_error(settings)

    assert error.source == "season_team"
    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    error = await fetch_error(settings, "XXX")

    assert error.reason == "unknown team code 'XXX'"


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
    unset = Settings(_env_file=None, season_team_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "season team URL is not configured"
