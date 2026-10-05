# api/tests/sources/test_game_detail.py
#
# Tests for the game detail adapter.
#
# Tested:
# - Maps a recorded final game to leaders and team stats
# - Requests the URL built from the template and the game id
# - Picks the top scorer of each team, the first in provider order on a tie, skipping players without a stat line
# - Builds photo URLs from the template and keeps the display name exactly as the provider gives it
# - Converts shooting percentages to fractions and takes team turnovers from the box score
# - Maps the provider team codes that differ from the standard ones
# - Raises the source error on an invalid payload, an unknown team, a missing home or away team, a team without player stats, a missing team stat, a stat that is not a number, an empty display name, a timeout, an error status and a missing URL
# - GameDetail uses the same field types as the contract Game
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
# - Happy path, edge cases and error cases of the leader and team stat mapping
#
# The recorded final fixture is a real box score trimmed to the fields the
# adapter reads: every URL-valued key is removed and the players keep their
# stat lines. A live fixture and its test come in a later change: no game is
# live when this one is written.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_game_detail.py
#
# SEE: api/app/sources/game_detail.py

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
import respx

from app.feeds.games import Game
from app.settings import Settings
from app.sources.game_detail import GameDetail, fetch_game_detail
from app.sources.http import SourceError, create_client

FIXTURES = Path(__file__).parent / "fixtures" / "game_detail"
GAME_ID = "401918010"
TEMPLATE = "https://example.com/games/{game_id}"
URL = f"https://example.com/games/{GAME_ID}"
PHOTO_TEMPLATE = "https://example.com/players/{player_id}.png"

Payload = dict[str, Any]


def load(name: str) -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


def team_players(payload: Payload, abbreviation: str) -> Payload:
    found: Payload = next(
        p
        for p in payload["boxscore"]["players"]
        if p["team"]["abbreviation"] == abbreviation
    )
    group: Payload = found["statistics"][0]
    return group


def athlete(payload: Payload, abbreviation: str, name: str) -> Payload:
    found: Payload = next(
        a
        for a in team_players(payload, abbreviation)["athletes"]
        if a["athlete"]["displayName"] == name
    )
    return found


def set_stat(line: Payload, abbreviation_group: Payload, key: str, value: str) -> None:
    line["stats"][abbreviation_group["keys"].index(key)] = value


def box_team(payload: Payload, side: str) -> Payload:
    found: Payload = next(
        t for t in payload["boxscore"]["teams"] if t["homeAway"] == side
    )
    return found


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, game_detail_url=TEMPLATE, player_photo_url=PHOTO_TEMPLATE
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings, game_id: str = GAME_ID) -> GameDetail:
    async with create_client() as client:
        return await fetch_game_detail(client, game_id, settings)


async def fetch_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_a_recorded_final_game_to_leaders_and_team_stats(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("final.json"))

    detail = await fetch(settings)

    away, home = detail.leaders.away, detail.leaders.home
    assert (away.team_code, away.player_id, away.display_name) == (
        "GSW",
        "4397886",
        "Charles Bassey",
    )
    assert (away.points, away.rebounds, away.assists) == (12, 8, 1)
    assert (home.team_code, home.player_id, home.display_name) == (
        "LAC",
        "4066648",
        "Rui Hachimura",
    )
    assert (home.points, home.rebounds, home.assists) == (21, 5, 0)
    stats = detail.team_stats
    assert stats.away.field_goal_pct == pytest.approx(0.39)
    assert stats.away.three_point_pct == pytest.approx(0.18)
    assert (stats.away.rebounds, stats.away.assists, stats.away.turnovers) == (
        49,
        23,
        16,
    )
    assert stats.home.field_goal_pct == pytest.approx(0.40)
    assert stats.home.three_point_pct == pytest.approx(0.31)
    assert (stats.home.rebounds, stats.home.assists, stats.home.turnovers) == (
        52,
        18,
        21,
    )


@pytest.mark.anyio
async def test_requests_the_url_built_from_the_template_and_the_game_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(URL).respond(json=load("final.json"))

    await fetch(settings)

    assert route.call_count == 1


@pytest.mark.anyio
async def test_picks_the_top_scorer_of_each_team_as_its_leader(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    for abbreviation, leader in (
        ("GS", detail.leaders.away),
        ("LAC", detail.leaders.home),
    ):
        group = team_players(payload, abbreviation)
        index = group["keys"].index("points")
        best = max(int(a["stats"][index]) for a in group["athletes"] if a["stats"])
        assert leader.points == best


@pytest.mark.anyio
async def test_keeps_the_first_player_in_provider_order_on_a_tie_in_points(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    group = team_players(payload, "LAC")
    set_stat(athlete(payload, "LAC", "Keaton Wagler"), group, "points", "21")
    set_stat(athlete(payload, "LAC", "Darius Garland"), group, "points", "21")
    names = [a["athlete"]["displayName"] for a in group["athletes"]]
    first = min(("Rui Hachimura", "Keaton Wagler", "Darius Garland"), key=names.index)
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.leaders.home.display_name == first


@pytest.mark.anyio
async def test_skips_players_without_a_stat_line(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    group = team_players(payload, "LAC")
    assert any(not a["stats"] for a in group["athletes"])
    athlete(payload, "LAC", "Rui Hachimura")["stats"] = []
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.leaders.home.display_name != "Rui Hachimura"
    assert detail.leaders.home.points == 15


@pytest.mark.anyio
async def test_builds_the_photo_url_from_the_template_in_settings(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("final.json"))

    detail = await fetch(settings)

    for leader in (detail.leaders.away, detail.leaders.home):
        assert (
            str(leader.photo_url)
            == f"https://example.com/players/{leader.player_id}.png"
        )


@pytest.mark.anyio
async def test_keeps_the_display_name_exactly_as_the_provider_gives_it(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    group = team_players(payload, "LAC")
    jones = athlete(payload, "LAC", "Derrick Jones Jr.")
    set_stat(jones, group, "points", "40")
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.leaders.home.display_name == "Derrick Jones Jr."


@pytest.mark.anyio
async def test_converts_shooting_percentages_to_a_fraction(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    assert {
        s["name"]: s["displayValue"] for s in box_team(payload, "away")["statistics"]
    }["fieldGoalPct"] == "39"
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.team_stats.away.field_goal_pct == pytest.approx(0.39)
    for side in (detail.team_stats.away, detail.team_stats.home):
        assert 0 <= side.field_goal_pct <= 1
        assert 0 <= side.three_point_pct <= 1


@pytest.mark.anyio
async def test_takes_team_turnovers_from_the_box_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    home = {
        s["name"]: s["displayValue"] for s in box_team(payload, "home")["statistics"]
    }
    assert home["turnovers"] != home["totalTurnovers"]
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.team_stats.home.turnovers == int(home["turnovers"])


@pytest.mark.anyio
async def test_maps_the_team_codes_that_differ(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    assert box_team(payload, "away")["team"]["abbreviation"] == "GS"
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.leaders.away.team_code == "GSW"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"boxscore": {"teams": []}},
        {"boxscore": 3},
        [],
    ],
)
async def test_raises_the_source_error_on_a_payload_missing_a_used_field(
    mock: respx.MockRouter, settings: Settings, body: Any
) -> None:
    mock.get(URL).respond(json=body)

    error = await fetch_error(settings)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    box_team(payload, "away")["team"]["abbreviation"] = "ZZZ"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == "unknown team code 'ZZZ'"


@pytest.mark.anyio
async def test_raises_the_source_error_without_one_home_and_one_away_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    box_team(payload, "away")["homeAway"] = "home"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == f"game {GAME_ID} needs one home and one away team"


@pytest.mark.anyio
async def test_raises_the_source_error_when_a_team_has_no_player_stats(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    for line in team_players(payload, "LAC")["athletes"]:
        line["stats"] = []
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == f"game {GAME_ID} has no player stats for LAC"


@pytest.mark.anyio
async def test_raises_the_source_error_when_a_team_has_no_player_list(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    payload["boxscore"]["players"] = payload["boxscore"]["players"][:1]
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == f"game {GAME_ID} has no players for LAC"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "name",
    ["fieldGoalPct", "threePointFieldGoalPct", "totalRebounds", "assists", "turnovers"],
)
async def test_raises_the_source_error_on_a_missing_team_stat(
    mock: respx.MockRouter, settings: Settings, name: str
) -> None:
    payload = load("final.json")
    team = box_team(payload, "home")
    team["statistics"] = [s for s in team["statistics"] if s["name"] != name]
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == f"game {GAME_ID} has no {name} stat"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_team_stat_that_is_not_a_number(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    for stat in box_team(payload, "home")["statistics"]:
        if stat["name"] == "fieldGoalPct":
            stat["displayValue"] = "--"
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == f"game {GAME_ID} has a stat that is not a number"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_player_stat_that_is_not_a_number(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    group = team_players(payload, "LAC")
    set_stat(athlete(payload, "LAC", "Rui Hachimura"), group, "points", "--")
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason == f"game {GAME_ID} has a stat that is not a number"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_player_without_a_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    athlete(payload, "LAC", "Rui Hachimura")["athlete"]["displayName"] = ""
    mock.get(URL).respond(json=payload)

    error = await fetch_error(settings)

    assert error.reason.startswith(f"game {GAME_ID} is invalid")


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_request_times_out(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).mock(side_effect=httpx.ReadTimeout("slow"))

    error = await fetch_error(settings)

    assert error.reason == "request timed out"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_error_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(status_code=500)

    error = await fetch_error(settings)

    assert error.reason == "responded with status 500"


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_game_detail_url_is_not_configured() -> (
    None
):
    unset = Settings(  # type: ignore[call-arg]
        _env_file=None, game_detail_url=None, player_photo_url=PHOTO_TEMPLATE
    )
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "game detail URL is not configured"


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_player_photo_url_is_not_configured() -> (
    None
):
    unset = Settings(  # type: ignore[call-arg]
        _env_file=None, game_detail_url=TEMPLATE, player_photo_url=None
    )
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "player photo URL is not configured"


def test_game_detail_fields_match_the_contract_game() -> None:
    for name, field in GameDetail.model_fields.items():
        assert name in Game.model_fields
        assert Game.model_fields[name].annotation == cast(Any, field.annotation) | None
        assert field.metadata == Game.model_fields[name].metadata
