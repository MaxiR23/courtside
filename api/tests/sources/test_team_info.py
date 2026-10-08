# api/tests/sources/test_team_info.py
#
# Tests for the team info adapter.
#
# Tested:
# - Maps a recorded team's identity, colors without the hash, venue and photo
# - Keeps a venue without images or city as a null photo and city
# - Requests the URL built from the provider team code, including a code that differs from the standard one
# - Raises the source error on an invalid payload, a color that is not six hex digits, an empty venue name, an unknown team code, a timeout, an error status and a missing URL
# - Reuses a team's info for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixture is a recorded team trimmed to the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_team_info.py
#
# SEE: api/app/sources/team_info.py

import datetime as dt
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
from app.sources.team_info import TeamInfo, fetch_team_info
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "team_info"
TEMPLATE = "https://example.com/teams/{team}"
URL = "https://example.com/teams/OKC"

Payload = dict[str, Any]


def load() -> Payload:
    payload: Payload = json.loads((FIXTURES / "okc.json").read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, team_info_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings, team_code: str = "OKC") -> TeamInfo:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_team_info(client, team_code, settings)


async def fetch_error(settings: Settings, team_code: str = "OKC") -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings, team_code)
    return raised.value


@pytest.mark.anyio
async def test_maps_a_recorded_teams_identity_colors_venue_and_photo(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    info = await fetch(settings)

    assert (info.location, info.name) == ("Oklahoma City", "Thunder")
    assert (info.color, info.alternate_color) == ("007ac1", "ef3b24")
    assert info.venue_name == "Paycom Center"
    assert info.venue_city == "Oklahoma City"
    assert info.venue_photo_url == "https://example.com/i/venues/nba/day/2559.jpg"


@pytest.mark.anyio
async def test_keeps_a_venue_without_images_or_city_as_null(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    venue = payload["team"]["franchise"]["venue"]
    del venue["images"]
    del venue["address"]
    mock.get(URL).respond(json=payload)

    info = await fetch(settings)

    assert (info.venue_photo_url, info.venue_city) == (None, None)
    assert info.venue_name == "Paycom Center"


@pytest.mark.anyio
async def test_requests_the_url_built_from_the_provider_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get("https://example.com/teams/GS").respond(json=load())

    await fetch(settings, "GSW")

    assert route.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload", [{}, {"team": 3}, {"team": {"name": "Thunder"}}], ids=str
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.source == "team_info"
    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize("color", ["#007ac1", "007ac", "gggggg", ""])
async def test_raises_the_source_error_on_a_color_that_is_not_six_hex_digits(
    mock: respx.MockRouter, settings: Settings, color: str
) -> None:
    payload = load()
    payload["team"]["color"] = color
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == "invalid payload: 1 errors, first at team.color"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_empty_venue_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["team"]["franchise"]["venue"]["fullName"] = ""
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("team OKC is invalid: ")


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
    unset = Settings(_env_file=None, team_info_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "team info URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_teams_info_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_team_info(client, "OKC", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_team_info(client, "OKC", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_team_info(client, "OKC", settings)

    assert route.call_count == 2
