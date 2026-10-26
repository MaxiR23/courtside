# api/tests/sources/test_season_leaders.py
#
# Tests for the season leaders adapter.
#
# Tested:
# - Maps the four categories in source order with their athlete ids and display values
# - Ignores the percentage and other categories
# - Leaves a missing category and a category with no leaders out
# - Maps the team code of each leader from its team link
# - Gives a leader without a team link, or with a team that is not in the league, no team
# - Raises the source error on a link without an athlete id, an invalid payload, a timeout, an error status and a missing URL
# - Formats only the season into the template, so the season type stays in the URL
# - Reuses a read for one hour
#
# What is covered:
# - Valid responses mapped, invalid payloads rejected, upstream failures handled
#
# The fixtures are made-up payloads of the shape docs/api/home.md documents (Read budget).
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_season_leaders.py
#
# SEE: api/app/sources/season_leaders.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.playoffs import LeaderCategory
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.season_leaders import SeasonLeaders, fetch_season_leaders
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "season_leaders"
TEMPLATE = "https://example.com/{season}/leaders"
URL = "https://example.com/2027/leaders"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, season_leaders_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def leaders(settings: Settings, tmp_path: Path) -> SeasonLeaders:
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store) as client:
        return await fetch_season_leaders(client, 2027, settings)


@pytest.mark.anyio
async def test_maps_the_four_categories_in_source_order(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).respond(json=load("leaders.json"))

    result = await leaders(settings, tmp_path)

    assert route.call_count == 1
    assert list(result.categories) == [
        LeaderCategory.POINTS,
        LeaderCategory.REBOUNDS,
        LeaderCategory.ASSISTS,
        LeaderCategory.BLOCKS,
    ]
    pairs = {
        category: [(e.player_id, e.value) for e in entries]
        for category, entries in result.categories.items()
    }
    assert pairs[LeaderCategory.POINTS] == [
        ("100", "30.0"),
        ("101", "29.0"),
        ("102", "28.0"),
    ]
    assert pairs[LeaderCategory.REBOUNDS] == [
        ("200", "12.0"),
        ("201", "11.0"),
        ("202", "10.0"),
    ]
    assert pairs[LeaderCategory.ASSISTS][0] == ("300", "10.0")
    assert pairs[LeaderCategory.BLOCKS][2] == ("402", "2.0")


@pytest.mark.anyio
async def test_ignores_the_percentage_and_other_categories(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("leaders.json"))

    result = await leaders(settings, tmp_path)

    ids = {e.player_id for entries in result.categories.values() for e in entries}
    assert not ids & {"950", "951", "952"}
    assert LeaderCategory.STEALS not in result.categories
    assert LeaderCategory.FIELD_GOAL_PCT not in result.categories


@pytest.mark.anyio
async def test_leaves_a_missing_category_and_a_category_with_no_leaders_out(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("missing-category.json"))

    result = await leaders(settings, tmp_path)

    assert LeaderCategory.BLOCKS not in result.categories
    assert LeaderCategory.REBOUNDS not in result.categories
    assert LeaderCategory.POINTS in result.categories


@pytest.mark.anyio
async def test_maps_the_team_code_of_each_leader_from_its_team_link(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("leaders.json"))

    result = await leaders(settings, tmp_path)

    assists = result.categories[LeaderCategory.ASSISTS]
    assert [str(e.team_code) for e in assists] == ["ATL", "BOS", "CHI"]
    points = result.categories[LeaderCategory.POINTS]
    assert str(points[0].team_code) == "BOS"
    assert str(points[2].team_code) == "DAL"


@pytest.mark.anyio
async def test_a_leader_without_a_team_link_or_with_a_non_league_team_has_no_team(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    mock.get(URL).respond(json=load("leaders.json"))

    result = await leaders(settings, tmp_path)

    points = result.categories[LeaderCategory.POINTS]
    rebounds = result.categories[LeaderCategory.REBOUNDS]
    assert points[1].team_code is None
    assert points[0].team_code is not None
    assert rebounds[1].team_code is None
    assert rebounds[0].team_code is not None


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_link_without_an_athlete_id(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    payload = load("leaders.json")
    payload["categories"][0]["leaders"][0]["athlete"]["$ref"] = (
        "https://example.com/v2/seasons/2027"
    )
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await leaders(settings, tmp_path)

    assert raised.value.reason == "athlete link has no athlete id"
    assert raised.value.source == "season_leaders"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"categories": 3},
        {"categories": [{"name": "pointsPerGame", "leaders": 3}]},
        {"categories": [{"name": "pointsPerGame", "leaders": [{"athlete": {}}]}]},
    ],
    ids=str,
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path, payload: Any
) -> None:
    mock.get(URL).respond(json=payload)

    with pytest.raises(SourceError) as raised:
        await leaders(settings, tmp_path)

    assert raised.value.reason.startswith("invalid payload: ")
    assert raised.value.source == "season_leaders"


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
    fails(mock.get(URL))

    with pytest.raises(SourceError) as raised:
        await leaders(settings, tmp_path)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured(
    tmp_path: Path,
) -> None:
    unset = Settings(_env_file=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await leaders(unset, tmp_path)

    assert raised.value.reason == "season leaders URL is not configured"


@pytest.mark.anyio
async def test_formats_only_the_season_into_the_template(
    mock: respx.MockRouter, tmp_path: Path
) -> None:
    own_query = Settings(  # type: ignore[call-arg]
        _env_file=None, season_leaders_url=TEMPLATE + "?type=2"
    )
    route = mock.get(URL + "?type=2").respond(json=load("leaders.json"))

    await leaders(own_query, tmp_path)

    assert str(route.calls.last.request.url) == URL + "?type=2"


@pytest.mark.anyio
async def test_reuses_a_read_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2027, 1, 1, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load("leaders.json"))
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_season_leaders(client, 2027, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_season_leaders(client, 2027, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_season_leaders(client, 2027, settings)

    assert route.call_count == 2
