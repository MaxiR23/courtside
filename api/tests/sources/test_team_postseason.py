# api/tests/sources/test_team_postseason.py
#
# Tests for the team postseason adapter.
#
# Tested:
# - Maps the overall, home and road records, with a missing or malformed one as null
# - Maps the 2005 record items overall, home and road
# - Maps the eight statistics and the games played, with a missing statistic as null, and never reads the plus-minus statistic
# - Requests the URL built from the season and the provider team id
# - Raises the source error, for both functions, on an unknown team code, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a read for one hour
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are made-up payloads of the shape docs/api/playoffs.md documents.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_team_postseason.py
#
# SEE: api/app/sources/team_postseason.py

import datetime as dt
import json
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.team_postseason import (
    fetch_team_postseason_record,
    fetch_team_postseason_stats,
)
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "team_postseason"
RECORD_URL = "https://example.com/{season}/teams/{team_id}/record"
STATS_URL = "https://example.com/{season}/teams/{team_id}/stats"
ATL_RECORD = "https://example.com/2027/teams/1/record"
ATL_STATS = "https://example.com/2027/teams/1/stats"

Payload = dict[str, Any]
Fetch = Callable[[SourceClient, str, int, Settings], Awaitable[Any]]
# (function, URL of ATL, message when the URL is not configured, source)
CASES = [
    (fetch_team_postseason_record, ATL_RECORD, "team postseason record URL"),
    (fetch_team_postseason_stats, ATL_STATS, "team postseason stats URL"),
]
IDS = ["record", "stats"]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        team_postseason_record_url=RECORD_URL,
        team_postseason_stats_url=STATS_URL,
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def read(
    fetch: Fetch, settings: Settings, tmp_path: Path, code: str = "ATL"
) -> Any:
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store) as client:
        return await fetch(client, code, 2027, settings)


@pytest.mark.anyio
async def test_maps_the_overall_home_and_road_records(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(ATL_RECORD).respond(json=load("record.json"))

    result = await read(fetch_team_postseason_record, settings, tmp_path)

    assert route.call_count == 1
    assert (result.overall, result.home, result.road) == ("16-6", "9-2", "7-4")


@pytest.mark.anyio
async def test_maps_a_missing_or_malformed_record_to_null(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(ATL_RECORD).respond(json=load("record-partial.json"))

    result = await read(fetch_team_postseason_record, settings, tmp_path)

    assert (result.overall, result.home, result.road) == ("16-6", None, None)


@pytest.mark.anyio
async def test_maps_the_statistics_and_the_games_played(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(ATL_STATS).respond(json=load("stats.json"))

    result = await read(fetch_team_postseason_stats, settings, tmp_path)

    assert result.model_dump(by_alias=False) == {
        "points": 112.4,
        "rebounds": 44.0,
        "assists": 25.1,
        "blocks": 5.2,
        "steals": 7.9,
        "field_goal_pct": 47.2,
        "effective_fg_pct": 54.9,
        "technical_fouls": 3.0,
        "games_played": 22,
    }


@pytest.mark.anyio
async def test_maps_a_missing_statistic_to_null(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(ATL_STATS).respond(json=load("stats-missing.json"))

    result = await read(fetch_team_postseason_stats, settings, tmp_path)

    assert result.points == 112.4
    assert result.assists is None
    assert result.games_played is None


@pytest.mark.anyio
async def test_requests_the_url_built_from_the_season_and_the_provider_team_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    record = mock.get("https://example.com/2027/teams/9/record").respond(
        json=load("record.json")
    )
    stats = mock.get("https://example.com/2027/teams/9/stats").respond(
        json=load("stats.json")
    )

    await read(fetch_team_postseason_record, settings, tmp_path, "GSW")
    await read(fetch_team_postseason_stats, settings, tmp_path, "GSW")

    assert record.call_count == 1
    assert stats.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(("fetch", "url", "message"), CASES, ids=IDS)
async def test_raises_the_source_error_on_an_unknown_team_code(
    fetch: Fetch, url: str, message: str, settings: Settings, tmp_path: Path
) -> None:
    with respx.mock, pytest.raises(SourceError) as raised:
        await read(fetch, settings, tmp_path, "XXX")

    assert raised.value.reason == "unknown team code 'XXX'"


@pytest.mark.anyio
@pytest.mark.parametrize(("fetch", "url", "message"), CASES, ids=IDS)
@pytest.mark.parametrize("payload", [[], {"items": 3, "splits": 3}, {}])
async def test_raises_the_source_error_on_an_invalid_payload(
    fetch: Fetch,
    url: str,
    message: str,
    payload: Any,
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
) -> None:
    mock.get(url).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await read(fetch, settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize(("fetch", "url", "message"), CASES, ids=IDS)
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
    fetch: Fetch,
    url: str,
    message: str,
    fails: Any,
    reason: str,
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
) -> None:
    fails(mock.get(url))

    with pytest.raises(SourceError) as raised:
        await read(fetch, settings, tmp_path)

    assert raised.value.reason == reason


@pytest.mark.anyio
@pytest.mark.parametrize(("fetch", "url", "message"), CASES, ids=IDS)
async def test_raises_the_source_error_when_the_url_is_not_configured(
    fetch: Fetch, url: str, message: str, tmp_path: Path
) -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await read(fetch, unset, tmp_path)

    assert raised.value.reason == f"{message} is not configured"


@pytest.mark.anyio
async def test_reuses_a_read_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2027, 6, 21, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(ATL_RECORD).respond(json=load("record.json"))
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_team_postseason_record(client, "ATL", 2027, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_team_postseason_record(client, "ATL", 2027, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_team_postseason_record(client, "ATL", 2027, settings)

    assert route.call_count == 2


@pytest.mark.anyio
async def test_maps_the_2005_record_items_overall_home_and_road(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(ATL_RECORD).respond(json=load("record-2005.json"))

    result = await read(fetch_team_postseason_record, settings, tmp_path)

    assert (result.overall, result.home, result.road) == ("16-7", "9-3", "7-4")
