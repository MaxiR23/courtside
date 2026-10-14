# api/tests/sources/test_finals_plays.py
#
# Tests for the Finals play score adapter.
#
# Tested:
# - Maps the plays' scores and elapsed seconds in game order, overtime included
# - Skips a play without scores or with a clock that cannot be placed
# - Returns an empty list for a response with no plays
# - Raises the source error on an invalid payload, a timeout, an error status and a missing URL
# - Shares one cached response with the game detail sections at the same freshness
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are made-up game summaries with the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_finals_plays.py
#
# SEE: api/app/sources/finals_plays.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.finals_plays import PlayScore, fetch_play_scores
from app.sources.game_detail import fetch_game_detail_sections
from app.sources.http import SourceClient, SourceError, create_client
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "finals_plays"
GAME_ID = "401000001"
TEMPLATE = "https://example.com/games/{game_id}"
URL = f"https://example.com/games/{GAME_ID}"
PHOTO_TEMPLATE = "https://example.com/players/{player_id}.png"
FRESH = dt.timedelta(hours=1)
FETCHED = dt.datetime(2027, 6, 10, 12, 0, tzinfo=dt.UTC)


def load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, game_detail_url=TEMPLATE, player_photo_url=PHOTO_TEMPLATE
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


def clocked(tmp_path: Path) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: FETCHED)


async def scores(settings: Settings, tmp_path: Path) -> list[PlayScore]:
    async with clocked(tmp_path) as client:
        return await fetch_play_scores(client, GAME_ID, settings, FRESH)


@pytest.mark.anyio
async def test_maps_the_scores_and_elapsed_seconds_in_game_order_overtime_included(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).respond(json=load("summary.json"))

    found = await scores(settings, tmp_path)

    assert route.call_count == 1
    assert [(s.elapsed_seconds, s.home_score, s.away_score) for s in found] == [
        (30, 0, 2),
        (120, 3, 2),
        (2880, 100, 100),
        (2910, 102, 100),
    ]


@pytest.mark.anyio
async def test_skips_a_play_without_scores_or_with_a_clock_that_cannot_be_placed(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("summary.json")
    payload["plays"].append(
        {
            "id": "7",
            "period": {"number": 4},
            "clock": {"displayValue": "1:00"},
            "homeScore": 50,
        }
    )

    mock.get(URL).respond(json=payload)
    found = await scores(settings, tmp_path)

    assert len(found) == 4
    assert 9 not in {s.home_score for s in found}


@pytest.mark.anyio
async def test_returns_an_empty_list_for_a_response_with_no_plays(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("no-scores.json"))

    assert await scores(settings, tmp_path) == []


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("invalid.json"))

    with pytest.raises(SourceError) as raised:
        await scores(settings, tmp_path)

    assert raised.value.reason == "invalid payload: 1 errors, first at format"


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
async def test_raises_the_source_error_when_the_request_times_out_or_fails(
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    fails: Any,
    reason: str,
) -> None:
    fails(mock.get(URL))

    with pytest.raises(SourceError) as raised:
        await scores(settings, tmp_path)

    assert raised.value.reason == reason
    assert raised.value.request_failed is True


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured(
    tmp_path: Path,
) -> None:
    unset = Settings(_env_file=None, game_detail_url=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await scores(unset, tmp_path)

    assert raised.value.reason == "game detail URL is not configured"


@pytest.mark.anyio
async def test_shares_one_cached_response_with_the_game_detail_sections(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = json.loads(
        (
            Path(__file__).parent / "fixtures" / "game_detail" / "summary-final.json"
        ).read_text(encoding="utf-8")
    )
    route = mock.get(URL).respond(json=payload)

    async with clocked(tmp_path) as client:
        await fetch_game_detail_sections(client, GAME_ID, settings, FRESH)
        await fetch_play_scores(client, GAME_ID, settings, FRESH)

    assert route.call_count == 1
