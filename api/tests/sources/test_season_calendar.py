# api/tests/sources/test_season_calendar.py
#
# Tests for the calendar view of the scoreboard adapter.
#
# Tested:
# - Reads the February 1 URL of the season's end year
# - Returns aware UTC times in provider order, for a lockout season and for a season with a July and August restart
# - Skips each unreadable entry (a number, a bad string, a naive time) with a log line that holds the index and the season
# - Raises the source error for a missing league, a missing or empty calendar, a calendar with no readable entry, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a read within 30 seconds and makes a new request at 30 seconds
#
# What is covered:
# - Happy path, edge cases and error cases of the calendar read
#
# The fixtures are invented: the provider's calendar shape is assumed
# (leagues[0].calendar, a list of UTC timestamps), as the module's header says.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_season_calendar.py
#
# SEE: api/app/sources/season_calendar.py

import datetime as dt
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.season_calendar import fetch_season_calendar
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "season_calendar"
TEMPLATE = "https://example.com/scoreboard/{date}"
NOW = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)


def load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, scoreboard_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(
    settings: Settings, tmp_path: Path, season: int = 1999
) -> list[dt.datetime]:
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: NOW) as client:
        return await fetch_season_calendar(client, season, settings)


@pytest.mark.anyio
async def test_reads_the_february_first_url_of_the_end_year(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get("https://example.com/scoreboard/19990201").respond(
        json=load("lockout.json")
    )

    await fetch(settings, tmp_path)

    assert route.call_count == 1


@pytest.mark.anyio
async def test_returns_aware_utc_times_in_provider_order(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get("https://example.com/scoreboard/19990201").respond(
        json=load("lockout.json")
    )

    moments = await fetch(settings, tmp_path)

    assert moments == [
        dt.datetime(1999, 2, 5, 8, 0, tzinfo=dt.UTC),
        dt.datetime(1999, 2, 6, 8, 0, tzinfo=dt.UTC),
        dt.datetime(1999, 2, 7, 8, 0, tzinfo=dt.UTC),
        dt.datetime(1999, 2, 6, 8, 0, tzinfo=dt.UTC),
    ]
    assert all(m.utcoffset() == dt.timedelta(0) for m in moments)


@pytest.mark.anyio
async def test_returns_a_season_with_a_gap_and_a_restart(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get("https://example.com/scoreboard/20200201").respond(
        json=load("restart.json")
    )

    moments = await fetch(settings, tmp_path, 2020)

    assert [m.month for m in moments] == [3, 3, 7, 8, 8]


@pytest.mark.anyio
async def test_skips_each_unreadable_entry_with_a_log_line_of_its_index_and_season(
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mock.get("https://example.com/scoreboard/20210201").respond(
        json=load("unreadable.json")
    )

    with caplog.at_level(logging.WARNING, logger="app.sources.season_calendar"):
        moments = await fetch(settings, tmp_path, 2021)

    assert [m.day for m in moments] == [5, 7]
    assert [r.getMessage() for r in caplog.records] == [
        "scoreboard: calendar entry 1 of season 2021 skipped",
        "scoreboard: calendar entry 2 of season 2021 skipped",
        "scoreboard: calendar entry 3 of season 2021 skipped",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name",
    [
        "no-league.json",
        "no-calendar.json",
        "empty-calendar.json",
        "all-unreadable.json",
    ],
)
async def test_raises_the_source_error_for_a_missing_or_empty_calendar(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path, name: str
) -> None:
    mock.get("https://example.com/scoreboard/19990201").respond(json=load(name))

    with pytest.raises(SourceError):
        await fetch(settings, tmp_path)


@pytest.mark.anyio
async def test_raises_the_source_error_for_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get("https://example.com/scoreboard/19990201").respond(
        json={"leagues": "none"}
    )

    with pytest.raises(SourceError, match="invalid payload"):
        await fetch(settings, tmp_path)


@pytest.mark.anyio
async def test_raises_the_source_error_for_a_timeout_and_an_error_status(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get("https://example.com/scoreboard/19990201")
    route.mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(SourceError, match="timed out"):
        await fetch(settings, tmp_path)

    route.mock(return_value=httpx.Response(500))
    with pytest.raises(SourceError, match="status 500"):
        await fetch(settings, tmp_path)


@pytest.mark.anyio
async def test_raises_the_source_error_without_a_url(tmp_path: Path) -> None:
    unset = Settings(_env_file=None, scoreboard_url=None)  # type: ignore[call-arg]

    with respx.mock, pytest.raises(SourceError, match="not configured"):
        await fetch(unset, tmp_path)


@pytest.mark.anyio
async def test_reuses_a_read_within_30_seconds(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    clock = [NOW]
    route = mock.get("https://example.com/scoreboard/19990201").respond(
        json=load("lockout.json")
    )
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_season_calendar(client, 1999, settings)
        clock[0] = NOW + dt.timedelta(seconds=29)
        await fetch_season_calendar(client, 1999, settings)
        assert route.call_count == 1
        clock[0] = NOW + dt.timedelta(seconds=30)
        await fetch_season_calendar(client, 1999, settings)

    assert route.call_count == 2
