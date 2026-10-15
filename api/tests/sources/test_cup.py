# api/tests/sources/test_cup.py
#
# Tests for the Cup adapter.
#
# Tested:
# - Maps a Cup note in any letter case to the same round
# - Maps the team links of a group to standard codes, and an empty collection to none
# - Maps a Cup table row with every stat, each clinch letter to its tag, and missing stats to null
# - Logs and nulls an unknown clinch letter
# - Maps a table with no rows to none and a conference table in seeding order
# - Requests the URL built from the season and the group id
# - Maps each Cup note to its round and any other note to none
# - Raises the source error on an unknown team id, a link without a team id, a table that is not the Cup table, a row without the in-season record or without wins, an invalid payload, a timeout, an error status and a missing URL
# - Reuses a read for one hour
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are made-up payloads of the shapes the settings document.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_cup.py
#
# SEE: api/app/sources/cup.py

import datetime as dt
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.cup import CupTag
from app.feeds.game_detail import Conference
from app.feeds.games import CupRound
from app.settings import Settings
from app.sources.cup import (
    CupTable,
    cup_round,
    fetch_conference_table,
    fetch_group_table,
    fetch_group_teams,
)
from app.sources.http import SourceError, create_client
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "cup"
TEAMS = "https://example.com/{season}/groups/{group}/teams"
TABLE = "https://example.com/{season}/groups/{group}/standings"
EAST_A_TEAMS = "https://example.com/2027/groups/22/teams"
EAST_A_TABLE = "https://example.com/2027/groups/22/standings"
WEST_CONFERENCE_TABLE = "https://example.com/2027/groups/29/standings"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, cup_group_url=TEAMS, cup_group_standings_url=TABLE
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def teams(settings: Settings) -> list[str]:
    async with create_client(StateStore(await _migrated())) as client:
        return await fetch_group_teams(client, 2027, Conference.EAST, "A", settings)


_current: list[Path] = []


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path) -> Iterator[None]:
    _current[:] = [tmp_path]
    StateStore(tmp_path).migrate()
    yield
    _current.clear()


async def _migrated() -> Path:
    return _current[0]


async def table(settings: Settings) -> CupTable:
    async with create_client(StateStore(await _migrated())) as client:
        return await fetch_group_table(client, 2027, Conference.EAST, "A", settings)


async def table_error_of(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> SourceError:
    mock.get(EAST_A_TABLE).respond(json=payload)
    with pytest.raises(SourceError) as raised:
        await table(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_the_team_links_of_a_group_to_standard_codes(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(EAST_A_TEAMS).respond(json=load("group-teams.json"))

    codes = await teams(settings)

    assert route.call_count == 1
    assert codes == ["ATL", "BOS", "NOP", "CHI", "CLE"]


@pytest.mark.anyio
async def test_maps_an_empty_teams_collection_to_no_teams(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(EAST_A_TEAMS).respond(json=load("group-teams-empty.json"))

    assert await teams(settings) == []


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("group-teams.json")
    payload["items"][0]["$ref"] = "https://example.com/v2/teams/99?lang=en"
    mock.get(EAST_A_TEAMS).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await teams(settings)

    assert raised.value.source == "cup_group"
    assert raised.value.reason == "unknown team id '99'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_link_without_a_team_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("group-teams.json")
    payload["items"][0]["$ref"] = "https://example.com/v2/groups/22"
    mock.get(EAST_A_TEAMS).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await teams(settings)

    assert raised.value.reason == "team link has no team id"


@pytest.mark.anyio
@pytest.mark.parametrize("payload", [{}, {"items": 3}, {"items": [{}]}], ids=str)
async def test_raises_the_source_error_on_an_invalid_teams_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    mock.get(EAST_A_TEAMS).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await teams(settings)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_maps_a_cup_table_row_with_every_stat(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(EAST_A_TABLE).respond(json=load("group-table.json"))

    result = await table(settings)

    assert [row.code for row in result.rows] == ["ATL", "BOS", "NOP", "CHI", "CLE"]
    first = result.rows[0]
    assert (first.wins, first.losses, first.position) == (4, 0, 1)
    assert first.games_behind == "-"
    assert (first.differential, first.point_differential) == (2.5, 10.0)
    assert (first.points_for, first.points_against) == (400.0, 390.0)
    assert (first.streak, first.ot_wins, first.ot_losses) == ("W2", 1, 0)
    assert (first.home, first.road) == ("2-1", "1-1")


@pytest.mark.anyio
async def test_maps_each_clinch_letter_to_its_tag_and_no_letter_to_null(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(EAST_A_TABLE).respond(json=load("group-table.json"))

    result = await table(settings)

    assert [row.clincher for row in result.rows] == [
        CupTag.WON_GROUP,
        CupTag.WILD_CARD,
        None,
        None,
        CupTag.ELIMINATED,
    ]


@pytest.mark.anyio
async def test_maps_a_missing_optional_stat_to_null(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(EAST_A_TABLE).respond(json=load("group-table.json"))

    result = await table(settings)

    assert result.rows[3].games_behind is None


@pytest.mark.anyio
async def test_maps_a_row_with_only_wins_and_losses_to_nulls(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("group-table.json")
    record = payload["standings"][0]["records"][0]
    record["stats"] = [s for s in record["stats"] if s["name"] in ("wins", "losses")]
    payload["standings"][0]["records"] = [record]

    mock.get(EAST_A_TABLE).respond(json=payload)
    row = (await table(settings)).rows[0]

    assert (row.wins, row.losses) == (4, 0)
    assert row.position is None
    assert row.games_behind is None
    assert row.differential is None
    assert row.point_differential is None
    assert row.points_for is None
    assert row.streak is None
    assert row.ot_wins is None
    assert (row.clincher, row.home, row.road) == (None, None, None)


@pytest.mark.anyio
async def test_logs_and_nulls_an_unknown_clinch_letter(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load("group-table.json")
    for stat in payload["standings"][0]["records"][0]["stats"]:
        if stat["name"] == "clincher":
            stat["displayValue"] = "q"
    mock.get(EAST_A_TABLE).respond(json=payload)

    with caplog.at_level(logging.WARNING):
        result = await table(settings)

    assert result.rows[0].clincher is None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "ATL" in warnings[0].getMessage()


@pytest.mark.anyio
async def test_maps_a_table_with_no_rows_to_no_rows(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(EAST_A_TABLE).respond(json=load("group-table-empty.json"))

    assert (await table(settings)).rows == []


@pytest.mark.anyio
async def test_reads_a_conference_table_of_fifteen_rows_in_order(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(WEST_CONFERENCE_TABLE).respond(json=load("conference-table.json"))

    async with create_client(StateStore(await _migrated())) as client:
        result = await fetch_conference_table(client, 2027, Conference.WEST, settings)

    assert route.call_count == 1
    assert len(result.rows) == 15
    assert [row.position for row in result.rows] == list(range(1, 16))
    assert result.rows[0].code == "ATL"
    assert result.rows[14].code == "MIL"


@pytest.mark.anyio
async def test_requests_each_group_with_its_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    expected = {
        (Conference.EAST, "A"): 22,
        (Conference.EAST, "B"): 23,
        (Conference.EAST, "C"): 24,
        (Conference.WEST, "A"): 25,
        (Conference.WEST, "B"): 26,
        (Conference.WEST, "C"): 27,
    }
    routes = {
        key: mock.get(f"https://example.com/2027/groups/{group}/teams").respond(
            json=load("group-teams-empty.json")
        )
        for key, group in expected.items()
    }

    async with create_client(StateStore(await _migrated())) as client:
        for conference, letter in expected:
            await fetch_group_teams(client, 2027, conference, letter, settings)

    assert all(route.call_count == 1 for route in routes.values())


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_table_that_is_not_the_cup_table(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("group-table.json")
    payload["name"] = "overall"

    error = await table_error_of(mock, settings, payload)

    assert error.source == "cup_group_standings"
    assert error.reason == "table is not the Cup table"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_row_without_the_in_season_record(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("group-table.json")
    payload["standings"][0]["records"] = [{"type": "home", "displayValue": "1-0"}]

    error = await table_error_of(mock, settings, payload)

    assert error.reason == "team ATL has no inseason record"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_row_without_wins(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("group-table.json")
    record = payload["standings"][0]["records"][0]
    record["stats"] = [s for s in record["stats"] if s["name"] != "wins"]

    error = await table_error_of(mock, settings, payload)

    assert error.reason == "team ATL has no wins or losses stat"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_id_in_a_table(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("group-table.json")
    payload["standings"][0]["team"]["$ref"] = "https://example.com/teams/99"

    error = await table_error_of(mock, settings, payload)

    assert error.reason == "unknown team id '99'"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload", [{}, {"name": 3}, {"name": "inseason", "standings": [{}]}], ids=str
)
async def test_raises_the_source_error_on_an_invalid_table_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    error = await table_error_of(mock, settings, payload)

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
    fails(mock.get(EAST_A_TABLE))

    with pytest.raises(SourceError) as raised:
        await table(settings)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_a_url_is_not_configured() -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock:
        with pytest.raises(SourceError) as teams_error:
            await teams(unset)
        with pytest.raises(SourceError) as table_error:
            await table(unset)

    assert teams_error.value.reason == "Cup group URL is not configured"
    assert table_error.value.reason == "Cup table URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_table_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(EAST_A_TABLE).respond(json=load("group-table.json"))
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_group_table(client, 2027, Conference.EAST, "A", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_group_table(client, 2027, Conference.EAST, "A", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_group_table(client, 2027, Conference.EAST, "A", settings)

    assert route.call_count == 2


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("NBA Cup - Group Play", CupRound.GROUP),
        ("NBA Cup - Quarterfinals", CupRound.QUARTERFINALS),
        ("NBA Cup - Semifinals", CupRound.SEMIFINALS),
        ("NBA Cup Championship", CupRound.CHAMPIONSHIP),
        ("NBA Finals - Game 1", None),
        ("NBA Cup", None),
        (None, None),
    ],
)
def test_maps_each_cup_note_to_its_round_and_any_other_to_none(
    note: str | None, expected: CupRound | None
) -> None:
    assert cup_round(note) is expected


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("NBA CUP - GROUP PLAY", CupRound.GROUP),
        ("nba cup - quarterfinals", CupRound.QUARTERFINALS),
        ("NBA CUP CHAMPIONSHIP", CupRound.CHAMPIONSHIP),
    ],
)
def test_maps_a_cup_note_in_any_letter_case_to_the_same_round(
    note: str, expected: CupRound
) -> None:
    assert cup_round(note) is expected
