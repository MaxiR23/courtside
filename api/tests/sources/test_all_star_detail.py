# api/tests/sources/test_all_star_detail.py
#
# Tests for the All-Star view of the game detail adapter.
#
# Tested:
# - Maps the regulation format (1 period, 720 seconds), the attendance, a TV and a streaming broadcast, and the jerseys and positions by player id
# - Skips a broadcast of another type or with no name
# - Missing extras give null and empty values, not an error
# - A game with no box score players has no jerseys or positions
# - An attendance of zero is no attendance
# - Raises the source error on an invalid payload, a missing URL, a 500 and a timeout
# - Shares one request with the sections function of the game detail adapter
#
# What is covered:
# - Happy path, edge cases and error cases of the All-Star extras mapping
#
# The fixtures are invented: clubs, players, broadcasters and the arena are made
# up, and every URL uses example.com.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_all_star_detail.py
#
# SEE: api/app/sources/all_star_detail.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.all_star import Broadcast, BroadcastKind
from app.settings import Settings
from app.sources.all_star_detail import AllStarDetailExtras, fetch_all_star_extras
from app.sources.game_detail import fetch_game_detail, fetch_game_detail_sections
from app.sources.http import SourceError, create_client
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "all_star_detail"
FRESH = dt.timedelta(hours=1)
TEMPLATE = "https://example.com/summary/{game_id}"
PHOTO = "https://example.com/photos/{player_id}.png"
URL = "https://example.com/summary/9001"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, game_detail_url=TEMPLATE, player_photo_url=PHOTO
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> AllStarDetailExtras:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_all_star_extras(client, "9001", settings, FRESH)


@pytest.mark.anyio
async def test_maps_the_format_attendance_broadcasts_jerseys_and_positions(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("final.json"))

    extras = await fetch(settings)

    assert extras.regulation_periods == 1
    assert extras.regulation_seconds == 720.0
    assert extras.attendance == 18500
    assert extras.broadcasts == [
        Broadcast(name="Example Network", kind=BroadcastKind.TV),
        Broadcast(name="Example Stream", kind=BroadcastKind.STREAMING),
    ]
    assert extras.jerseys == {"1001": "7", "1002": "23", "2001": "3", "2002": "11"}
    assert extras.positions == {"1001": "G", "1002": "F", "2001": "C", "2002": "G"}


@pytest.mark.anyio
async def test_skips_a_broadcast_with_no_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    payload["broadcasts"][0]["media"] = {}
    mock.get(URL).respond(json=payload)

    extras = await fetch(settings)

    assert [b.name for b in extras.broadcasts] == ["Example Stream"]


@pytest.mark.anyio
async def test_missing_extras_give_null_and_empty_values(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("missing-extras.json"))

    extras = await fetch(settings)

    assert extras.attendance is None
    assert extras.broadcasts == []
    assert extras.jerseys == {} and extras.positions == {}
    assert extras.regulation_periods == 1


@pytest.mark.anyio
async def test_a_game_with_no_box_score_players_has_no_jerseys_or_positions(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("scheduled.json"))

    extras = await fetch(settings)

    assert extras.jerseys == {} and extras.positions == {}


@pytest.mark.anyio
async def test_an_attendance_of_zero_is_no_attendance(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    payload["gameInfo"]["attendance"] = 0
    mock.get(URL).respond(json=payload)

    assert (await fetch(settings)).attendance is None


@pytest.mark.anyio
async def test_a_payload_without_a_format_has_a_null_format(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    del payload["format"]
    mock.get(URL).respond(json=payload)

    extras = await fetch(settings)

    assert extras.regulation_periods is None and extras.regulation_seconds is None


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json={"boxscore": {"players": "none"}})

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await fetch(unset)

    assert raised.value.reason == "game detail URL is not configured"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_error_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(status_code=500)

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "responded with status 500"


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_request_times_out(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == "request timed out"


@pytest.mark.anyio
async def test_shares_one_request_with_the_core_adapter_for_the_same_freshness(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(URL).respond(json=load("final.json"))
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            sections = await fetch_game_detail_sections(client, "9001", settings, FRESH)
            detail = await fetch_game_detail(client, "9001", settings, FRESH)
            extras = await fetch_all_star_extras(client, "9001", settings, FRESH)

    assert route.call_count == 1
    assert sections.box_score is not None
    assert detail.leaders.away.points == 12
    assert extras.attendance == 18500
