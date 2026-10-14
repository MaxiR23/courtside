# api/tests/sources/test_season_types.py
#
# Tests for the season type adapter.
#
# Tested:
# - Maps the regular season, the play-in and the postseason to their windows in UTC
# - Requests the URL built from the season and the season type
# - Raises the source error on a missing end date, an end before the start, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a read for one hour
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are made-up payloads of the shape docs/api/playoffs.md documents.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_season_types.py
#
# SEE: api/app/sources/season_types.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.season_types import (
    PLAY_IN,
    POSTSEASON,
    REGULAR_SEASON,
    SeasonWindow,
    fetch_season_type,
)
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "season_types"
TEMPLATE = "https://example.com/{season}/types/{type}"
URL = "https://example.com/2027/types/{}"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, season_type_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def window(
    settings: Settings, tmp_path: Path, season_type: int = POSTSEASON
) -> SeasonWindow:
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store) as client:
        return await fetch_season_type(client, 2027, season_type, settings)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("season_type", "name", "start", "end"),
    [
        (
            REGULAR_SEASON,
            "regular-season.json",
            dt.datetime(2026, 10, 20, 7, tzinfo=dt.UTC),
            dt.datetime(2027, 4, 14, 6, 59, tzinfo=dt.UTC),
        ),
        (
            PLAY_IN,
            "play-in.json",
            dt.datetime(2027, 4, 14, 7, tzinfo=dt.UTC),
            dt.datetime(2027, 4, 18, 6, 59, tzinfo=dt.UTC),
        ),
        (
            POSTSEASON,
            "postseason.json",
            dt.datetime(2027, 4, 18, 7, tzinfo=dt.UTC),
            dt.datetime(2027, 6, 21, 6, 59, tzinfo=dt.UTC),
        ),
    ],
    ids=["regular season", "play-in", "postseason"],
)
async def test_maps_a_season_type_to_its_window_in_utc(
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    season_type: int,
    name: str,
    start: dt.datetime,
    end: dt.datetime,
) -> None:
    route = mock.get(URL.format(season_type)).respond(json=load(name))

    result = await window(settings, tmp_path, season_type)

    assert route.call_count == 1
    assert result == SeasonWindow(season_type=season_type, start=start, end=end)


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_missing_end_date(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL.format(POSTSEASON)).respond(json=load("invalid.json"))

    with pytest.raises(SourceError) as raised:
        await window(settings, tmp_path)

    assert raised.value.reason == "invalid payload: 1 errors, first at endDate"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_end_before_the_start(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("postseason.json")
    payload["endDate"] = "2027-04-01T07:00Z"
    mock.get(URL.format(POSTSEASON)).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await window(settings, tmp_path)

    assert raised.value.reason == "the end is not after the start"


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [[], {}, {"startDate": "x", "endDate": "y"}])
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path, payload: Any
) -> None:
    mock.get(URL.format(POSTSEASON)).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await window(settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")


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
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    fails: Any,
    reason: str,
) -> None:
    fails(mock.get(URL.format(POSTSEASON)))

    with pytest.raises(SourceError) as raised:
        await window(settings, tmp_path)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured(
    tmp_path: Path,
) -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await window(unset, tmp_path)

    assert raised.value.reason == "season type URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_read_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2027, 4, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL.format(POSTSEASON)).respond(json=load("postseason.json"))
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_season_type(client, 2027, POSTSEASON, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_season_type(client, 2027, POSTSEASON, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_season_type(client, 2027, POSTSEASON, settings)

    assert route.call_count == 2
