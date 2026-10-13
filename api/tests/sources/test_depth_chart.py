# api/tests/sources/test_depth_chart.py
#
# Tests for the depth chart adapter.
#
# Tested:
# - Maps the five positions to ranked athlete ids
# - Accepts a chart with missing positions and maps an empty chart to no positions
# - Ignores a position outside the five
# - Requests the URL built from the season and the provider team id
# - Raises the source error on an unknown team code, an athlete link without an id or with an empty id, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a chart for 24 hours
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are made-up payloads of the shape docs/api/cup-matchup.md documents.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_depth_chart.py
#
# SEE: api/app/sources/depth_chart.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.depth_chart import DepthChart, fetch_depth_chart
from app.sources.http import SourceError, create_client
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "depth_chart"
TEMPLATE = "https://example.com/{season}/teams/{team_id}/depthcharts"
ATL_URL = "https://example.com/2027/teams/1/depthcharts"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, depth_chart_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def chart(settings: Settings, tmp_path: Path, code: str = "ATL") -> DepthChart:
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store) as client:
        return await fetch_depth_chart(client, code, 2027, settings)


@pytest.mark.anyio
async def test_maps_the_five_positions_to_ranked_athlete_ids(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(ATL_URL).respond(json=load("chart.json"))

    result = await chart(settings, tmp_path)

    assert route.call_count == 1
    assert result.positions == {
        "pg": ["101", "102", "103"],
        "sg": ["201", "202"],
        "sf": ["301", "302", "303"],
        "pf": ["401", "402"],
        "c": ["501", "502"],
    }


@pytest.mark.anyio
async def test_accepts_a_chart_with_missing_positions(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(ATL_URL).respond(json=load("chart-missing-positions.json"))

    result = await chart(settings, tmp_path)

    assert sorted(result.positions) == ["c", "pg", "sg"]


@pytest.mark.anyio
async def test_maps_an_empty_chart_to_no_positions(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(ATL_URL).respond(json=load("chart-empty.json"))

    assert (await chart(settings, tmp_path)).positions == {}


@pytest.mark.anyio
async def test_ignores_a_position_outside_the_five(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("chart.json")
    payload["items"][0]["positions"]["g"] = payload["items"][0]["positions"]["pg"]
    mock.get(ATL_URL).respond(json=payload)

    result = await chart(settings, tmp_path)

    assert sorted(result.positions) == ["c", "pf", "pg", "sf", "sg"]


@pytest.mark.anyio
async def test_requests_the_url_built_from_the_season_and_the_provider_team_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get("https://example.com/2027/teams/9/depthcharts").respond(
        json=load("chart-empty.json")
    )

    await chart(settings, tmp_path, "GSW")

    assert route.call_count == 1


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    with pytest.raises(SourceError) as raised:
        await chart(settings, tmp_path, "XXX")

    assert raised.value.source == "depth_chart"
    assert raised.value.reason == "unknown team code 'XXX'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_athlete_link_without_an_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("chart.json")
    payload["items"][0]["positions"]["pg"]["athletes"][0]["athlete"]["$ref"] = (
        "https://example.com/v2/seasons/2027"
    )
    mock.get(ATL_URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await chart(settings, tmp_path)

    assert raised.value.reason == "athlete link has no athlete id"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_athlete_link_with_an_empty_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("chart.json")
    payload["items"][0]["positions"]["pg"]["athletes"][0]["athlete"]["$ref"] = (
        "https://example.com/athletes//5"
    )
    mock.get(ATL_URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await chart(settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"items": 3},
        {"items": [{"positions": 3}]},
        {"items": [{"positions": {"pg": {"athletes": 3}}}]},
        {"items": [{"positions": {"pg": {"athletes": [{"athlete": {}}]}}}]},
    ],
    ids=str,
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path, payload: Any
) -> None:
    mock.get(ATL_URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await chart(settings, tmp_path)

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
    fails(mock.get(ATL_URL))

    with pytest.raises(SourceError) as raised:
        await chart(settings, tmp_path)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured(
    tmp_path: Path,
) -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await chart(unset, tmp_path)

    assert raised.value.reason == "depth chart URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_chart_for_24_hours(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(ATL_URL).respond(json=load("chart.json"))
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_depth_chart(client, "ATL", 2027, settings)
        clock[0] = start + dt.timedelta(hours=24) - dt.timedelta(seconds=1)
        await fetch_depth_chart(client, "ATL", 2027, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=24)
        await fetch_depth_chart(client, "ATL", 2027, settings)

    assert route.call_count == 2
