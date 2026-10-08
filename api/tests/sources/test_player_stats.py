# api/tests/sources/test_player_stats.py
#
# Tests for the player stats adapter.
#
# Tested:
# - Maps the recorded per-season averages, totals and miscellaneous rows and the career rows
# - Uses the combined row of a season played for two teams with the per-team codes in their order
# - Requests the playoffs with the playoffs season type in the URL's query and keeps the template's own query
# - Maps the recorded playoffs
# - Returns no rows on a 404
# - Raises the source error on a row whose column count does not match the labels, a row without a team, an unknown team id and a malformed stat
# - Raises the source error on an invalid payload, a timeout, an error status and a missing URL
# - Reuses stats for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are recorded responses trimmed to the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_player_stats.py
#
# SEE: api/app/sources/player_stats.py

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
from app.sources.player_stats import PlayerStats, fetch_player_stats
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "player_stats"
TEMPLATE = "https://example.com/athletes/{player_id}/stats?region=us"
URL = "https://example.com/athletes/3945274/stats?region=us"

Payload = dict[str, Any]


def load(name: str = "regular.json") -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, player_stats_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings, playoffs: bool = False) -> PlayerStats:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_player_stats(
                client, "3945274", settings, playoffs=playoffs
            )


async def fetch_error(settings: Settings, playoffs: bool = False) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_the_recorded_per_season_rows_and_the_career_rows(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    stats = await fetch(settings)

    assert [row.season for row in stats.per_game] == ["2018-19", "2024-25", "2025-26"]
    first = stats.per_game[0]
    assert first.teams == ["DAL"]
    assert (first.games_played, first.games_started, first.minutes) == (72, 72, 32.2)
    assert (first.field_goals, first.field_goal_pct) == ("7.0-16.5", 42.7)
    assert (first.offensive_rebounds, first.defensive_rebounds) == (1.2, 6.6)
    assert (first.rebounds, first.assists, first.points) == (7.8, 6.0, 21.2)
    total = stats.totals[0]
    assert total.field_goals == "506-1186"
    assert (total.games_played, total.games_started, total.minutes) == (
        None,
        None,
        None,
    )
    assert total.points == 1526
    misc = stats.misc[0]
    assert (misc.season, misc.double_doubles, misc.triple_doubles) == ("2018-19", 24, 8)
    assert (misc.assist_turnover_ratio, misc.steal_turnover_ratio) == (1.7, 0.3)
    assert stats.career_per_game is not None
    assert stats.career_per_game.season is None
    assert (stats.career_per_game.games_played, stats.career_per_game.points) == (
        514,
        29.2,
    )
    assert stats.career_totals is not None
    assert stats.career_totals.field_goals == "5052-10778"
    assert stats.career_misc is not None
    assert (stats.career_misc.double_doubles, stats.career_misc.technicals) == (
        273,
        111,
    )


@pytest.mark.anyio
async def test_uses_the_combined_row_of_a_two_team_season_with_the_codes_in_order(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    stats = await fetch(settings)

    row = stats.per_game[1]
    assert (row.season, row.teams) == ("2024-25", ["DAL", "LAL"])
    assert (row.games_played, row.points) == (50, 28.2)
    assert stats.totals[1].teams == ["DAL", "LAL"]
    assert stats.totals[1].field_goals == "461-1025"
    assert stats.misc[1].double_doubles == 21
    assert len(stats.per_game) == 3


@pytest.mark.anyio
async def test_requests_the_playoffs_with_the_season_type_and_keeps_the_templates_query(
    mock: respx.MockRouter, settings: Settings
) -> None:
    regular = mock.get(URL).respond(json=load())
    playoffs = mock.get(URL + "&seasontype=3").respond(json=load("playoffs.json"))

    await fetch(settings, playoffs=False)
    await fetch(settings, playoffs=True)

    assert regular.calls.last.request.url == httpx.URL(URL)
    assert playoffs.calls.last.request.url == httpx.URL(
        "https://example.com/athletes/3945274/stats?region=us&seasontype=3"
    )


@pytest.mark.anyio
async def test_maps_the_recorded_playoffs(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL + "&seasontype=3").respond(json=load("playoffs.json"))

    stats = await fetch(settings, playoffs=True)

    assert [row.season for row in stats.per_game] == ["2019-20", "2024-25"]
    assert (stats.per_game[0].games_played, stats.per_game[0].points) == (6, 31.0)
    assert stats.per_game[1].teams == ["LAL"]
    assert stats.career_per_game is not None
    assert stats.career_per_game.games_played == 55


@pytest.mark.anyio
async def test_returns_no_rows_on_a_404(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(status_code=404)

    assert await fetch(settings) == PlayerStats()


@pytest.mark.anyio
async def test_returns_no_rows_for_a_player_without_categories(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json={})

    assert await fetch(settings) == PlayerStats()


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_row_whose_column_count_does_not_match(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["categories"][0]["statistics"][0]["stats"].pop()
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == "invalid payload: 1 errors, first at averages stats"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_row_without_a_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del payload["categories"][0]["statistics"][0]["teamId"]
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert (
        error.reason == "invalid payload: 1 errors, first at averages team of 2018-19"
    )


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["categories"][0]["statistics"][0]["teamId"] = "999"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == "unknown team id '999'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_malformed_stat(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["categories"][0]["statistics"][0]["stats"][3] = "7.0/16.5"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith("player 3945274 is invalid: ")
    assert error.reason.endswith("per_game.0.field_goals")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload", [{"categories": 3}, {"categories": [{"name": "averages"}]}], ids=str
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.source == "player_stats"
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
    unset = Settings(_env_file=None, player_stats_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "player stats URL is not configured"


@pytest.mark.anyio
async def test_reuses_stats_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_player_stats(client, "3945274", settings, playoffs=False)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_player_stats(client, "3945274", settings, playoffs=False)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_player_stats(client, "3945274", settings, playoffs=False)

    assert route.call_count == 2
