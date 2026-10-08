# api/tests/sources/test_team_players.py
#
# Tests for the team players adapter.
#
# Tested:
# - Maps a recorded roster to stars with the names exactly as the provider gives them and the provider's current season
# - Requests the roster URL built from the template and the provider team code, including a code that differs from the standard one
# - Builds photo URLs from the template and the player id
# - Roster players use the contract Star type
# - Maps recorded season averages to per-game points, rebounds and assists in provider order
# - Takes the player id from the athlete link, with or without a query
# - Requests the averages URL built from the template, the team id and the season
# - Returns no averages when the provider has none for the team and season
# - Returns no averages when the provider lists no categories
# - Counts a category the player is missing from as zero
# - Maps recorded player averages to points, rebounds and assists, picking stats by name
# - Requests the player averages URL built from the template, the player id and the season
# - Returns no player averages when the provider has none for the player and season
# - Counts a player stat that is missing as zero
# - Raises the source error on an invalid player averages payload, a player stat that is not a number, a negative player stat, a timeout, an error status and a missing player averages URL
# - Raises the source error on an invalid roster payload, an invalid averages payload, an empty roster, an empty name, a stat that is not a number, a negative stat, an unknown team code, a timeout, an error status, a missing roster URL, a missing averages URL and a missing photo URL
# - Reuses a roster and the team leaders for twenty-four hours, and a player's averages for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are a real roster and real season averages trimmed to the fields
# the adapter reads: every URL-valued key is removed except the athlete links,
# which are rewritten to an example.com address. The averages list players
# who are not on the roster.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_team_players.py
#
# SEE: api/app/sources/team_players.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.games import Star
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.team_players import (
    PlayerAverages,
    Roster,
    fetch_player_averages,
    fetch_roster,
    fetch_season_averages,
)
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "team_players"
ROSTER_TEMPLATE = "https://example.com/teams/{team}/roster"
AVERAGES_TEMPLATE = "https://example.com/seasons/{season}/teams/{team}/leaders"
PLAYER_TEMPLATE = "https://example.com/seasons/{season}/athletes/{player_id}/statistics"
PHOTO_TEMPLATE = "https://example.com/players/{player_id}.png"
ROSTER_URL = "https://example.com/teams/GS/roster"
AVERAGES_URL = "https://example.com/seasons/2026/teams/9/leaders"
PLAYER_URL = "https://example.com/seasons/2026/athletes/6430/statistics"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        team_roster_url=ROSTER_TEMPLATE,
        team_averages_url=AVERAGES_TEMPLATE,
        player_averages_url=PLAYER_TEMPLATE,
        player_photo_url=PHOTO_TEMPLATE,
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def roster_of(settings: Settings, code: str = "GSW") -> Roster:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_roster(client, code, settings)


async def averages_of(
    settings: Settings, team_id: str = "9", season: int = 2026
) -> list[PlayerAverages]:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_season_averages(client, team_id, season, settings)


async def player_of(
    settings: Settings, player_id: str = "6430", season: int = 2026
) -> PlayerAverages | None:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_player_averages(client, player_id, season, settings)


async def player_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await player_of(settings)
    return raised.value


async def roster_error(settings: Settings, code: str = "GSW") -> SourceError:
    with pytest.raises(SourceError) as raised:
        await roster_of(settings, code)
    return raised.value


async def averages_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await averages_of(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_a_recorded_roster_to_stars_and_the_current_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("roster.json")
    mock.get(ROSTER_URL).respond(json=payload)

    roster = await roster_of(settings)

    assert roster.season == 2027
    assert roster.team_id == "9"
    assert len(roster.players) == len(payload["athletes"])
    butler = roster.players[1]
    assert (butler.player_id, butler.first_name, butler.last_name) == (
        "6430",
        "Jimmy",
        "Butler III",
    )
    assert butler.short_name == "J. Butler III"
    assert butler.team_code == "GSW"


@pytest.mark.anyio
async def test_requests_the_roster_url_built_from_the_provider_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(ROSTER_URL).respond(json=load("roster.json"))

    await roster_of(settings, "GSW")

    assert route.call_count == 1


@pytest.mark.anyio
async def test_builds_photo_urls_from_the_template_and_the_player_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(ROSTER_URL).respond(json=load("roster.json"))

    roster = await roster_of(settings)

    assert str(roster.players[3].photo_url) == "https://example.com/players/3975.png"


@pytest.mark.anyio
async def test_roster_players_use_the_contract_star_type(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(ROSTER_URL).respond(json=load("roster.json"))

    roster = await roster_of(settings)

    assert all(type(player) is Star for player in roster.players)


@pytest.mark.anyio
async def test_maps_recorded_season_averages_in_provider_order(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("averages.json")
    mock.get(AVERAGES_URL).respond(json=payload)

    averages = await averages_of(settings)

    points = payload["categories"][0]["leaders"]
    assert len(averages) == len(points) == 22
    assert averages[0].player_id == "4709138"
    assert averages[0].points == pytest.approx(13.817, abs=1e-3)
    assert averages[0].rebounds == pytest.approx(5.110, abs=1e-3)
    assert averages[0].assists == pytest.approx(3.707, abs=1e-3)
    curry = next(a for a in averages if a.player_id == "3975")
    assert curry.points == pytest.approx(26.558, abs=1e-3)


@pytest.mark.anyio
async def test_takes_the_player_id_from_the_athlete_link_with_or_without_a_query(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("averages.json")
    payload["categories"] = [
        {
            "name": "pointsPerGame",
            "leaders": [
                {"value": 1.0, "athlete": {"$ref": "https://example.com/a/11?lang=en"}},
                {"value": 2.0, "athlete": {"$ref": "https://example.com/a/22"}},
            ],
        }
    ]
    mock.get(AVERAGES_URL).respond(json=payload)

    averages = await averages_of(settings)

    assert [a.player_id for a in averages] == ["11", "22"]


@pytest.mark.anyio
async def test_requests_the_averages_url_built_from_the_team_id_and_the_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(AVERAGES_URL).respond(json=load("averages.json"))

    await averages_of(settings, "9", 2026)

    assert route.call_count == 1


@pytest.mark.anyio
async def test_returns_no_averages_when_the_provider_has_none_for_the_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(AVERAGES_URL).respond(404)

    assert await averages_of(settings) == []


@pytest.mark.anyio
async def test_returns_no_averages_when_the_provider_lists_no_categories(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(AVERAGES_URL).respond(json={"categories": []})

    assert await averages_of(settings) == []


@pytest.mark.anyio
async def test_counts_a_category_the_player_is_missing_from_as_zero(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("averages.json")
    assists = next(c for c in payload["categories"] if c["name"] == "assistsPerGame")
    assists["leaders"] = [
        leader
        for leader in assists["leaders"]
        if not leader["athlete"]["$ref"].endswith("/4709138")
    ]
    mock.get(AVERAGES_URL).respond(json=payload)

    averages = await averages_of(settings)

    missing = next(a for a in averages if a.player_id == "4709138")
    assert missing.assists == 0
    assert missing.points > 0


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_roster_payload(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("roster.json")
    del payload["season"]
    mock.get(ROSTER_URL).respond(json=payload)

    error = await roster_error(settings)

    assert error.source == "team_players"
    assert error.reason == "invalid payload: 1 errors, first at season"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_empty_roster(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("roster.json")
    payload["athletes"] = []
    mock.get(ROSTER_URL).respond(json=payload)

    error = await roster_error(settings)

    assert error.reason == "team GSW is invalid: too_short at players"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_empty_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("roster.json")
    payload["athletes"][0]["lastName"] = ""
    mock.get(ROSTER_URL).respond(json=payload)

    error = await roster_error(settings)

    assert (
        error.reason == "team GSW is invalid: string_too_short at players.0.last_name"
    )


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_averages_payload(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(AVERAGES_URL).respond(json={"categories": "none"})

    error = await averages_error(settings)

    assert error.reason == "invalid payload: 1 errors, first at categories"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_stat_that_is_not_a_number(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("averages.json")
    payload["categories"][0]["leaders"][0]["value"] = "lots"
    mock.get(AVERAGES_URL).respond(json=payload)

    error = await averages_error(settings)

    assert error.reason == "team 9 has a stat that is not a number"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_negative_stat(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("averages.json")
    payload["categories"][0]["leaders"][0]["value"] = -1.0
    mock.get(AVERAGES_URL).respond(json=payload)

    error = await averages_error(settings)

    assert error.reason.startswith("team 9 is invalid:")


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    error = await roster_error(settings, "XXX")

    assert error.reason == "unknown team code 'XXX'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_timeout(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(ROSTER_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    mock.get(AVERAGES_URL).mock(side_effect=httpx.ReadTimeout("slow"))

    assert (await roster_error(settings)).reason == "request timed out"
    assert (await averages_error(settings)).reason == "request timed out"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_error_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(ROSTER_URL).respond(404)
    mock.get(AVERAGES_URL).respond(500)

    assert (await roster_error(settings)).reason == "responded with status 404"
    assert (await averages_error(settings)).reason == "responded with status 500"


@pytest.mark.anyio
async def test_raises_the_source_error_when_a_url_is_not_configured(
    mock: respx.MockRouter,
) -> None:
    full: dict[str, Any] = {
        "team_roster_url": ROSTER_TEMPLATE,
        "team_averages_url": AVERAGES_TEMPLATE,
        "player_photo_url": PHOTO_TEMPLATE,
    }
    for name, reason in (
        ("team_roster_url", "team roster URL is not configured"),
        ("player_photo_url", "player photo URL is not configured"),
    ):
        settings = Settings(_env_file=None, **{**full, name: None})  # type: ignore[call-arg]
        assert (await roster_error(settings)).reason == reason
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, **{**full, "team_averages_url": None}
    )
    assert (await averages_error(settings)).reason == (
        "team averages URL is not configured"
    )


@pytest.mark.anyio
async def test_maps_recorded_player_averages_to_points_rebounds_and_assists(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(PLAYER_URL).respond(json=load("player_averages.json"))

    found = await player_of(settings)

    assert found == PlayerAverages(
        player_id="6430", points=21.4, rebounds=7.1, assists=5.2
    )


@pytest.mark.anyio
async def test_requests_the_player_averages_url_built_from_the_player_id_and_the_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get("https://example.com/seasons/2025/athletes/77/statistics").respond(
        json=load("player_averages.json")
    )

    found = await player_of(settings, "77", 2025)

    assert route.called
    assert found is not None
    assert found.player_id == "77"


@pytest.mark.anyio
async def test_returns_no_player_averages_when_the_provider_has_none_for_the_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(PLAYER_URL).respond(404)

    assert await player_of(settings) is None


@pytest.mark.anyio
async def test_counts_a_stat_the_player_is_missing_as_zero(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("player_averages.json")
    payload["splits"]["categories"][1]["stats"] = [{"name": "avgPoints", "value": 21.4}]
    mock.get(PLAYER_URL).respond(json=payload)

    found = await player_of(settings)

    assert found == PlayerAverages(
        player_id="6430", points=21.4, rebounds=7.1, assists=0.0
    )


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_player_averages_payload(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(PLAYER_URL).respond(json={"splits": "none"})

    error = await player_error(settings)

    assert error.reason == "invalid payload: 1 errors, first at splits"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_player_stat_that_is_not_a_number(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("player_averages.json")
    payload["splits"]["categories"][1]["stats"][0]["value"] = "lots"
    mock.get(PLAYER_URL).respond(json=payload)

    error = await player_error(settings)

    assert error.reason == "player 6430 has a stat that is not a number"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_negative_player_stat(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("player_averages.json")
    payload["splits"]["categories"][1]["stats"][0]["value"] = -1.0
    mock.get(PLAYER_URL).respond(json=payload)

    error = await player_error(settings)

    assert error.reason.startswith("player 6430 is invalid:")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_player_averages_timeout_and_error_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(PLAYER_URL).mock(side_effect=httpx.ReadTimeout("slow"))
    assert (await player_error(settings)).reason == "request timed out"

    mock.get(PLAYER_URL).respond(500)
    assert (await player_error(settings)).reason == "responded with status 500"


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_player_averages_url_is_not_configured(
    mock: respx.MockRouter,
) -> None:
    settings = Settings(_env_file=None, player_averages_url=None)  # type: ignore[call-arg]

    assert (await player_error(settings)).reason == (
        "player averages URL is not configured"
    )


def clocked(tmp_path: Path, clock: list[dt.datetime]) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: clock[0])


@pytest.mark.anyio
async def test_reuses_a_roster_for_twenty_four_hours(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(ROSTER_URL).respond(json=load("roster.json"))
    async with clocked(tmp_path, clock) as client:
        await fetch_roster(client, "GSW", settings)
        clock[0] = start + dt.timedelta(hours=24) - dt.timedelta(seconds=1)
        await fetch_roster(client, "GSW", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=24)
        await fetch_roster(client, "GSW", settings)

    assert route.call_count == 2


@pytest.mark.anyio
async def test_reuses_the_team_leaders_for_twenty_four_hours(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(AVERAGES_URL).respond(json=load("averages.json"))
    async with clocked(tmp_path, clock) as client:
        await fetch_season_averages(client, "9", 2026, settings)
        clock[0] = start + dt.timedelta(hours=24) - dt.timedelta(seconds=1)
        await fetch_season_averages(client, "9", 2026, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=24)
        await fetch_season_averages(client, "9", 2026, settings)

    assert route.call_count == 2


@pytest.mark.anyio
async def test_reuses_a_players_averages_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(PLAYER_URL).respond(json=load("player_averages.json"))
    async with clocked(tmp_path, clock) as client:
        await fetch_player_averages(client, "6430", 2026, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_player_averages(client, "6430", 2026, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_player_averages(client, "6430", 2026, settings)

    assert route.call_count == 2
