# api/tests/sources/test_season_team.py
#
# Tests for the season team adapter.
#
# Tested:
# - Maps a recorded season team's abbreviation, names and location
# - Maps a season team whose isActive is false, and a body without isActive
# - Returns None on a 404
# - A 404 is requested once and not again within 30 days, and again at 30 days; it stores no source cache entry (ADR 0064)
# - A 404 read with record_absence=False records no absence and is requested again (ADR 0064)
# - Requests the season and the provider team id of the code
# - Raises the source error on an invalid payload, an unknown team code, a timeout, an error status and a missing URL
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_season_team.py
#
# SEE: api/app/sources/season_team.py

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


T0 = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)


@pytest.mark.anyio
async def test_a_404_is_requested_once_and_not_again_within_30_days(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).respond(404)
    clock = [T0]
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        first = await fetch_season_team(client, "OKC", 2004, settings)
        assert (first, route.call_count) == (None, 1)

        clock[0] = T0 + dt.timedelta(days=29)
        within = await fetch_season_team(client, "OKC", 2004, settings)
        assert (within, route.call_count) == (None, 1)

        clock[0] = T0 + dt.timedelta(days=30)
        after = await fetch_season_team(client, "OKC", 2004, settings)
        assert (after, route.call_count) == (None, 2)


@pytest.mark.anyio
async def test_a_recorded_absence_is_of_one_team_and_one_season(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(404)
    other = mock.get("https://example.com/seasons/2004/teams/17").respond(
        json=load("inactive")
    )
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: T0) as client:
        await fetch_season_team(client, "OKC", 2004, settings)
        found = await fetch_season_team(client, "BKN", 2004, settings)

    assert found is not None
    assert other.call_count == 1


@pytest.mark.anyio
async def test_a_404_stores_no_source_cache_entry(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(404)
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: T0) as client:
        await fetch_season_team(client, "OKC", 2004, settings)

    assert store.source_entry(URL) is None
    assert store.season_team_absent("OKC", 2004, T0 - dt.timedelta(seconds=1))


@pytest.mark.anyio
async def test_a_404_with_record_absence_false_records_nothing_and_is_requested_again(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).respond(404)
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: T0) as client:
        first = await fetch_season_team(
            client, "OKC", 2004, settings, record_absence=False
        )
        second = await fetch_season_team(
            client, "OKC", 2004, settings, record_absence=False
        )

    assert (first, second, route.call_count) == (None, None, 2)
    assert not store.season_team_absent("OKC", 2004, T0 - dt.timedelta(days=1))
