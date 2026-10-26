# api/tests/sources/test_power_index.py
#
# Tests for the power index adapter.
#
# Tested:
# - Maps 30 teams over two pages in the provider's order with their ranks, ratings, record, projections and chances
# - Reads one page when the first holds fewer than 25 items
# - Never asks for a third page when the second page is full too
# - Formats the season and the page into the template and keeps its own query
# - Keeps only the regular-season items of a payload with three runs
# - Maps a negative rank to its absolute value with tied true
# - Gives null for a stat that is absent, null or has an empty display value
# - Maps the numeric team id of the link to the standard code
# - Raises the source error on an unknown team id, a link without a team id, an invalid payload, a stat that is not a number, a rank that is not whole, a timeout, an error status and a missing URL
# - Reuses a read for one hour
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are made-up payloads of the shape docs/api/power-ranking.md documents (Read budget).
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_power_index.py
#
# SEE: api/app/sources/power_index.py

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
from app.sources.power_index import PowerIndex, fetch_power_index
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "power_index"
TEMPLATE = "https://example.com/{season}/ranking?lang=en&page={page}"
PAGE_1 = "https://example.com/2027/ranking?lang=en&page=1"
PAGE_2 = "https://example.com/2027/ranking?lang=en&page=2"
PAGE_3 = "https://example.com/2027/ranking?lang=en&page=3"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, power_index_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def index(settings: Settings, tmp_path: Path) -> PowerIndex:
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store) as client:
        return await fetch_power_index(client, 2027, settings)


def one_page(mock: respx.MockRouter, name: str) -> respx.Route:
    return mock.get(PAGE_1).respond(json=load(name))


@pytest.mark.anyio
async def test_maps_30_teams_over_two_pages_in_the_provider_order(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    first = mock.get(PAGE_1).respond(json=load("page-1.json"))
    second = mock.get(PAGE_2).respond(json=load("page-2.json"))

    result = await index(settings, tmp_path)

    assert (first.call_count, second.call_count) == (1, 1)
    assert [team.rank for team in result.teams] == list(range(1, 31))
    top = result.teams[0]
    assert (top.code, top.tied, top.wins, top.losses) == ("ATL", False, 59, 21)
    assert (top.rating, top.offense, top.defense) == (7.5, 3.8, 2.9)
    assert (top.projected_wins, top.projected_losses) == (59.4, 22.6)
    assert (top.playoffs, top.title) == (97.0, 30.0)
    assert (top.playoffs_text, top.title_text) == ("97.0%", "30.0%")


@pytest.mark.anyio
async def test_reads_one_page_when_the_first_holds_fewer_than_25_items(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    first = one_page(mock, "tie.json")
    second = mock.get(PAGE_2).respond(json=load("page-2.json"))

    result = await index(settings, tmp_path)

    assert len(result.teams) == 2
    assert (first.call_count, second.call_count) == (1, 0)


@pytest.mark.anyio
async def test_never_asks_for_a_third_page(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    first = mock.get(PAGE_1).respond(json=load("page-1.json"))
    second = mock.get(PAGE_2).respond(json=load("full-page-2.json"))
    third = mock.get(PAGE_3).respond(json=load("page-2.json"))

    result = await index(settings, tmp_path)

    assert (first.call_count, second.call_count, third.call_count) == (1, 1, 0)
    assert len(result.teams) == 50


@pytest.mark.anyio
async def test_formats_the_season_and_the_page_and_keeps_the_own_query(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    first = mock.get(PAGE_1).respond(json=load("page-1.json"))
    second = mock.get(PAGE_2).respond(json=load("page-2.json"))

    await index(settings, tmp_path)

    assert str(first.calls.last.request.url) == PAGE_1
    assert str(second.calls.last.request.url) == PAGE_2


@pytest.mark.anyio
async def test_keeps_only_the_regular_season_items(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    one_page(mock, "three-runs.json")

    result = await index(settings, tmp_path)

    assert [(team.code, team.rank) for team in result.teams] == [("LAL", 1), ("MIN", 2)]


@pytest.mark.anyio
async def test_maps_a_negative_rank_to_its_absolute_value_with_tied(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    one_page(mock, "tie.json")

    result = await index(settings, tmp_path)

    assert [(team.rank, team.tied) for team in result.teams] == [(3, True), (4, False)]


@pytest.mark.anyio
async def test_gives_null_for_a_missing_null_or_empty_stat(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    one_page(mock, "missing-stats.json")

    first, second, third = (await index(settings, tmp_path)).teams

    assert first.rating is None
    assert second.offense is None
    assert (third.title, third.title_text) == (None, None)
    assert third.playoffs_text is not None


@pytest.mark.anyio
async def test_maps_the_numeric_team_id_to_the_standard_code(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(PAGE_1).respond(json=load("page-1.json"))
    mock.get(PAGE_2).respond(json=load("page-2.json"))

    result = await index(settings, tmp_path)

    assert result.teams[8].code == "GSW"
    assert len({team.code for team in result.teams}) == 30


def with_ref(ref: str) -> Payload:
    payload = load("tie.json")
    payload["items"][0]["team"]["$ref"] = ref
    return payload


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        (with_ref("https://example.com/teams/9999"), "unknown team id '9999'"),
        (with_ref("https://example.com/seasons/2027"), "team link has no team id"),
    ],
    ids=["unknown id", "no id"],
)
async def test_raises_the_source_error_on_a_bad_team_link(
    mock: respx.MockRouter,
    settings: Settings,
    tmp_path: Path,
    payload: Payload,
    reason: str,
) -> None:
    mock.get(PAGE_1).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await index(settings, tmp_path)

    assert raised.value.reason == reason
    assert raised.value.source == "power_index"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [[], {}, {"items": 3}, {"items": [{"seasonType": 2}]}],
    ids=str,
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path, payload: Any
) -> None:
    mock.get(PAGE_1).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await index(settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_payload_without_items(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    one_page(mock, "invalid.json")

    with pytest.raises(SourceError) as raised:
        await index(settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_stat_that_is_not_a_number(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("tie.json")
    payload["items"][0]["stats"][1]["value"] = "high"
    mock.get(PAGE_1).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await index(settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_rank_that_is_not_whole(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("tie.json")
    payload["items"][0]["stats"][0]["value"] = 2.5
    mock.get(PAGE_1).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await index(settings, tmp_path)

    assert raised.value.reason == "stat bpirank is not a whole number"


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
    fails(mock.get(PAGE_1))

    with pytest.raises(SourceError) as raised:
        await index(settings, tmp_path)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured(
    tmp_path: Path,
) -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await index(unset, tmp_path)

    assert raised.value.reason == "power index URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_read_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2027, 1, 1, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = one_page(mock, "tie.json")
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_power_index(client, 2027, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_power_index(client, 2027, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_power_index(client, 2027, settings)

    assert route.call_count == 2
