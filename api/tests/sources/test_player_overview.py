# api/tests/sources/test_player_overview.py
#
# Tests for the player overview adapter.
#
# Tested:
# - Maps the recorded awards with count text and season end years
# - Returns no awards when the overview has none
# - Raises the source error on an award with a season that is not a year or a count that is not a number of times
# - Raises the source error on an invalid payload, a timeout, an error status and a missing URL
# - Reuses an overview for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixture is a recorded response trimmed to the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_player_overview.py
#
# SEE: api/app/sources/player_overview.py

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
from app.sources.player_overview import ProviderAward, fetch_player_awards
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "player_overview"
TEMPLATE = "https://example.com/athletes/{player_id}/overview"
URL = "https://example.com/athletes/4278073/overview"

Payload = dict[str, Any]


def load() -> Payload:
    payload: Payload = json.loads(
        (FIXTURES / "overview.json").read_text(encoding="utf-8")
    )
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, player_overview_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> list[ProviderAward]:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_player_awards(client, "4278073", settings)


async def fetch_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_the_recorded_awards_with_count_text_and_season_end_years(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    awards = await fetch(settings)

    assert [(a.name, a.display_count, a.seasons) for a in awards][:2] == [
        ("MVP", "2x", [2026, 2025]),
        ("All-NBA 1st Team", "4x", [2026, 2025, 2024, 2023]),
    ]
    assert len(awards) == 7


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"awards": []}], ids=str)
async def test_returns_no_awards_when_the_overview_has_none(
    mock: respx.MockRouter, settings: Settings, payload: Payload
) -> None:
    mock.get(URL).respond(json=payload)

    assert await fetch(settings) == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value"),
    [("seasons", ["2026", "last"]), ("seasons", ["26"]), ("displayCount", "many")],
    ids=str,
)
async def test_raises_the_source_error_on_a_season_or_count_it_cannot_read(
    mock: respx.MockRouter, settings: Settings, field: str, value: Any
) -> None:
    payload = load()
    payload["awards"][0][field] = value
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload", [{"awards": 3}, {"awards": [{"name": "MVP"}]}], ids=str
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.source == "player_overview"
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
    unset = Settings(_env_file=None, player_overview_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "player overview URL is not configured"


@pytest.mark.anyio
async def test_reuses_an_overview_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_player_awards(client, "4278073", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_player_awards(client, "4278073", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_player_awards(client, "4278073", settings)

    assert route.call_count == 2
