# api/tests/sources/test_player_bio.py
#
# Tests for the player bio adapter.
#
# Tested:
# - Maps the season summary with values, ranks and the season the summary names
# - Gives a stat without a rank a null rank
# - Returns no summary when the bio has none
# - Raises the source error on an invalid payload, a summary missing a statistic, a summary without a season, a timeout, an error status and a missing URL
# - Reuses a bio for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixture is a recorded response trimmed to the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_player_bio.py
#
# SEE: api/app/sources/player_bio.py

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
from app.sources.player_bio import PlayerBio, fetch_player_bio
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "player_bio"
TEMPLATE = "https://example.com/athletes/{player_id}"
URL = "https://example.com/athletes/4278073"

Payload = dict[str, Any]


def load() -> Payload:
    payload: Payload = json.loads((FIXTURES / "bio.json").read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, player_bio_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> PlayerBio | None:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_player_bio(client, "4278073", settings)


async def fetch_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_the_season_summary_with_values_and_ranks(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    bio = await fetch(settings)

    assert bio is not None
    assert bio.season == "2025-26"
    assert bio.points.value == pytest.approx(31.132353)
    assert bio.points.rank == 2
    assert bio.rebounds.value == pytest.approx(4.2941175)
    assert bio.rebounds.rank == 103
    assert bio.assists.value == pytest.approx(6.5882354)
    assert bio.assists.rank == 14
    assert bio.field_goal_pct.value == pytest.approx(55.337, abs=0.001)
    assert bio.field_goal_pct.rank == 12


@pytest.mark.anyio
async def test_gives_a_stat_without_a_rank_a_null_rank(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del payload["athlete"]["statsSummary"]["statistics"][1]["rank"]
    mock.get(URL).respond(json=payload)

    bio = await fetch(settings)

    assert bio is not None
    assert bio.rebounds.rank is None
    assert bio.points.rank == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "athlete", [{}, {"statsSummary": {"displayName": "x", "statistics": []}}], ids=str
)
async def test_returns_no_summary_when_the_bio_has_none(
    mock: respx.MockRouter, settings: Settings, athlete: Payload
) -> None:
    mock.get(URL).respond(json={"athlete": athlete})

    assert await fetch(settings) is None


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_summary_missing_a_statistic(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del payload["athlete"]["statsSummary"]["statistics"][3]
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")
    assert "fieldGoalPct" in error.reason


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_summary_without_a_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["athlete"]["statsSummary"]["displayName"] = "regular season stats"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"athlete": 3},
        {
            "athlete": {
                "statsSummary": {
                    "displayName": "x",
                    "statistics": [{"name": "avgPoints"}],
                }
            }
        },
    ],
    ids=str,
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.source == "player_bio"
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
    unset = Settings(_env_file=None, player_bio_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "player bio URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_bio_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_player_bio(client, "4278073", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_player_bio(client, "4278073", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_player_bio(client, "4278073", settings)

    assert route.call_count == 2
