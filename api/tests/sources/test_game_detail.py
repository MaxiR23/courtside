# api/tests/sources/test_game_detail.py
#
# Tests for the game detail adapter.
#
# Tested:
# - Maps a recorded final game and a recorded live game to leaders and team stats
# - Requests the URL built from the template and the game id
# - Picks the top scorer of each team, breaking a tie on points by rebounds plus assists and then by provider order, skipping players without a stat line
# - Builds photo URLs from the template and keeps the display name exactly as the provider gives it
# - Converts shooting percentages to fractions and takes team turnovers from the box score
# - Maps the provider team codes that differ from the standard ones
# - Raises the source error on an invalid payload, a missing home or away team, a team without player stats, a missing team stat, a stat that is not a number, an empty display name, a timeout, an error status and a missing URL
# - GameDetail uses the same field types as the contract Game
# - Maps a recorded scheduled game and a recorded final game to their detail sections: venue, box score, team stats, win probability, injuries, season series and videos
# - Maps a venue without an address, or an address without a city, to a null city
# - Maps a recorded live game to a box score for both teams, the team stats with their leading side and win probability points not past the recorded clock
# - Maps recorded videos with their duration as text
# - Places each win probability point at its elapsed game seconds, in regulation and overtime, and drops a point that cannot be placed
# - Orders win probability points by elapsed game seconds, keeping the source order of points at the same second, and keeps the recorded points unchanged
# - Takes the win probability leader from the last published point: the side ahead and its probability, none when even or without points
# - Publishes each period's start and the game end from the game format and the plays' period numbers, and none without win probability
# - Marks the leading side of each team stat row: the lower value leads turnovers and a tie has no leader
# - Drops players without a stat line, splits made and attempted shots, reads plus-minus with its sign and builds photo URLs from the template
# - Counts the series wins of the away and home team and dates series games on the US Eastern day
# - Raises the source error on an unknown injury status, a series game of other teams, a summary missing a used field, a missing detail team stat, a box score stat that is not a number, a timeout, an error status and a missing URL
# - Marks this game in the season series, before and after it is played, with its winner and score only once it is completed
# - Gives each completed series game its winner and the series a leader, or none on a tie
# - Raises the source error on a completed series game without exactly one winner
# - SeriesMeeting uses the same field types as the contract SeriesGame, except the arena
# - A final game's detail attempt fetches again when the stored entry is older than its due time, and reuses one fetched at or after it
# - The sections and the detail of one game share one cached response
# - A guest team keeps its provider code in the leaders, team stats and box score; a guest player photo is the box score headshot or null; a guest game has no season series and may have no win probability
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
# - Happy path, edge cases and error cases of the leader and team stat mapping
#
# The recorded final and live fixtures are real box scores trimmed to the
# fields the adapter reads: every URL-valued key is removed and the players
# keep their stat lines. The live one was recorded early in the first quarter.
#
# The summary-* fixtures are recorded game summaries trimmed to the fields
# fetch_game_detail_sections reads, with the same trimming. The players keep
# the starters, two bench players and one player without a stat line, and the
# plays keep the first three of each period and the last play of the game.
# summary-live.json was recorded in the first quarter with 3:42 left, so its
# box score is partial and its last play is at 3:43. One win probability entry
# of summary-final.json was given a play id that matches no play, to cover the
# dropped point. No overtime summary was recorded: the overtime cases edit
# summary-final.json in the test.
#
# summary-out-of-order-win-probability.json is not recorded. It is built with
# example data only. Its win probability entries go back in game time in the
# second and third quarters, and two entries share a second.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_game_detail.py
#
# SEE: api/app/sources/game_detail.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import httpx
import pytest
import respx

from app.feeds.game_detail import SeriesGame
from app.feeds.games import Game
from app.settings import Settings
from app.sources.game_detail import (
    GameDetail,
    GameDetailSections,
    SeriesMeeting,
    fetch_game_detail,
    fetch_game_detail_sections,
)
from app.sources.http import SourceClient, SourceError, create_client
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "game_detail"
GAME_ID = "401918010"
TEMPLATE = "https://example.com/games/{game_id}"
URL = f"https://example.com/games/{GAME_ID}"
# summary-final.json was recorded for this event: its box totals and venue match it.
SERIES_GAME_ID = "401811041"
# No recorded summary holds a pre-game current game, so that test calls
# summary-scheduled.json with the id of one of its own pre events.
PRE_GAME_SERIES_ID = "401910243"
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
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_game_detail(
                client, game_id, settings, dt.timedelta(hours=1)
            )


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
async def test_maps_a_recorded_live_game_to_leaders_and_team_stats(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("live.json"))

    detail = await fetch(settings)

    away, home = detail.leaders.away, detail.leaders.home
    assert (away.team_code, away.player_id, away.display_name) == (
        "MEM",
        "5112087",
        "Jaylen Wells",
    )
    assert (away.points, away.rebounds, away.assists) == (3, 0, 0)
    assert (home.team_code, home.player_id, home.display_name) == (
        "ATL",
        "4278039",
        "Nickeil Alexander-Walker",
    )
    assert (home.points, home.rebounds, home.assists) == (10, 1, 0)
    stats = detail.team_stats
    assert stats.away.field_goal_pct == pytest.approx(0.36)
    assert stats.away.three_point_pct == pytest.approx(0.14)
    assert (stats.away.rebounds, stats.away.assists, stats.away.turnovers) == (3, 3, 2)
    assert stats.home.field_goal_pct == pytest.approx(0.80)
    assert stats.home.three_point_pct == pytest.approx(0.75)
    assert (stats.home.rebounds, stats.home.assists, stats.home.turnovers) == (5, 5, 0)


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
async def test_breaks_a_tie_in_points_by_rebounds_plus_assists(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    group = team_players(payload, "LAC")
    names = [a["athlete"]["displayName"] for a in group["athletes"]]
    assert names.index("Rui Hachimura") < names.index("Darius Garland")
    set_stat(athlete(payload, "LAC", "Darius Garland"), group, "points", "21")
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.leaders.home.display_name == "Darius Garland"


@pytest.mark.anyio
async def test_keeps_the_first_player_in_provider_order_on_a_tie_in_points_and_rebounds_plus_assists(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    group = team_players(payload, "LAC")
    garland = athlete(payload, "LAC", "Darius Garland")
    set_stat(garland, group, "points", "21")
    set_stat(garland, group, "rebounds", "2")
    set_stat(garland, group, "assists", "3")
    names = [a["athlete"]["displayName"] for a in group["athletes"]]
    first = min(("Rui Hachimura", "Darius Garland"), key=names.index)
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


def rename_team(node: Any, abbreviation: str, guest: str = "HCM") -> None:
    """Renames a team everywhere in a payload: the invented Harbor City Mariners."""
    if isinstance(node, dict):
        if node.get("abbreviation") == abbreviation:
            node["abbreviation"] = guest
        for value in node.values():
            rename_team(value, abbreviation, guest)
    elif isinstance(node, list):
        for value in node:
            rename_team(value, abbreviation, guest)


def headshot(payload: Payload, abbreviation: str, name: str, href: str) -> None:
    found = next(
        a
        for p in payload["boxscore"]["players"]
        if p["team"]["abbreviation"] == abbreviation
        for a in p["statistics"][0]["athletes"]
        if a["athlete"]["displayName"] == name
    )
    found["athlete"]["headshot"] = {"href": href}


@pytest.mark.anyio
async def test_maps_the_leaders_and_team_stats_of_a_guest_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    rename_team(payload, "GS")
    mock.get(URL).respond(json=payload)

    detail = await fetch(settings)

    assert detail.leaders.away.team_code == "HCM"
    assert detail.leaders.home.team_code == "LAC"
    assert detail.leaders.away.points == 12
    assert detail.team_stats.away.rebounds == 49


@pytest.mark.anyio
async def test_a_guest_leader_photo_is_the_box_score_headshot_and_null_without_one(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("final.json")
    rename_team(payload, "GS")
    headshot(
        payload, "HCM", "Charles Bassey", "https://example.com/headshots/bassey.png"
    )
    mock.get(URL).respond(json=payload)
    bare = load("final.json")
    rename_team(bare, "GS")
    mock.get(TEMPLATE.format(game_id="bare")).respond(json=bare)

    with_headshot = await fetch(settings)
    without_headshot = await fetch(settings, game_id="bare")

    assert str(with_headshot.leaders.away.photo_url) == (
        "https://example.com/headshots/bassey.png"
    )
    assert str(with_headshot.leaders.home.photo_url) == (
        "https://example.com/players/4066648.png"
    )
    assert without_headshot.leaders.away.photo_url is None


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


# Game detail sections

SECTIONS_PHOTO = "https://example.com/players/{player_id}.png"


async def fetch_sections(
    settings: Settings, game_id: str = GAME_ID
) -> GameDetailSections:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_game_detail_sections(
                client, game_id, settings, dt.timedelta(hours=1)
            )


async def sections_error(settings: Settings, game_id: str = GAME_ID) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch_sections(settings, game_id)
    return raised.value


async def sections_of(
    mock: respx.MockRouter,
    settings: Settings,
    payload: Payload,
    game_id: str = GAME_ID,
) -> GameDetailSections:
    mock.get(TEMPLATE.format(game_id=game_id)).respond(json=payload)
    return await fetch_sections(settings, game_id)


async def sections_error_of(
    mock: respx.MockRouter,
    settings: Settings,
    payload: Payload,
    game_id: str = GAME_ID,
) -> SourceError:
    mock.get(TEMPLATE.format(game_id=game_id)).respond(json=payload)
    return await sections_error(settings, game_id)


def stat_row(payload: Payload, side: str, name: str) -> Payload:
    found: Payload = next(
        s for s in box_team(payload, side)["statistics"] if s["name"] == name
    )
    return found


def set_team_stat(payload: Payload, side: str, name: str, value: str) -> None:
    stat_row(payload, side, name)["displayValue"] = value


@pytest.mark.anyio
async def test_maps_a_recorded_scheduled_game_to_its_venue_injuries_and_series_without_box_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-scheduled.json"))

    assert (detail.venue.name, detail.venue.city) == ("Hilton Coliseum", "Ames")
    assert detail.venue.photo_url is None
    assert detail.box_score is None
    assert detail.team_stats is None
    assert detail.win_probability is None
    assert detail.win_probability_leader is None
    assert detail.win_probability_periods is None
    assert detail.injuries is not None
    assert detail.injuries.away is not None
    assert detail.injuries.home is not None
    assert [i.display_name for i in detail.injuries.away] == ["Donte DiVincenzo"]
    assert [i.status.value for i in detail.injuries.away] == ["out"]
    assert [i.status.value for i in detail.injuries.home] == [
        "day-to-day",
        "day-to-day",
        "day-to-day",
        "out",
    ]
    assert detail.season_series is not None
    assert detail.season_series.total_games == 2
    assert detail.season_series.games == []
    assert detail.season_series.leader is None
    assert detail.videos is None


@pytest.mark.anyio
async def test_maps_a_neutral_site_venue_without_an_address_to_a_null_city(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-neutral-site.json"))

    assert (detail.venue.name, detail.venue.city) == ("Neutral Site Arena", None)
    assert detail.venue.photo_url is None


@pytest.mark.anyio
async def test_maps_a_venue_address_without_a_city_to_a_null_city(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-scheduled.json")
    payload["gameInfo"]["venue"]["address"] = {}

    detail = await sections_of(mock, settings, payload)

    assert (detail.venue.name, detail.venue.city) == ("Hilton Coliseum", None)


@pytest.mark.anyio
async def test_maps_a_recorded_final_game_to_its_detail_sections(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert (detail.venue.name, detail.venue.city) == ("TD Garden", "Boston")
    assert str(detail.venue.photo_url) == "https://example.com/61"
    assert detail.win_probability_periods is not None
    assert detail.win_probability_leader is not None
    assert detail.win_probability_leader.team_code == "BOS"
    assert detail.win_probability_leader.win_probability == 1.0
    assert detail.box_score is not None
    home, away = detail.box_score.home.totals, detail.box_score.away.totals
    assert (home.points, home.field_goals_made, home.field_goals_attempted) == (
        113,
        36,
        87,
    )
    assert away.points == 108
    assert detail.team_stats is not None
    assert detail.team_stats.home.free_throw_pct == 1.0
    assert (detail.team_stats.home.steals, detail.team_stats.home.blocks) == (10, 6)
    assert detail.injuries is not None
    assert detail.injuries.away is not None
    assert detail.injuries.home == []
    assert len(detail.injuries.away) == 5
    assert detail.season_series is not None
    assert detail.season_series.total_games == 4
    assert (detail.season_series.home_wins, detail.season_series.away_wins) == (3, 1)
    assert len(detail.season_series.games) == 4
    assert detail.season_series.games[-1].game_id == "401811041"
    assert detail.videos is None


@pytest.mark.anyio
async def test_maps_a_recorded_live_game_to_its_detail_sections(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-live.json"))

    assert detail.box_score is not None
    away, home = detail.box_score.away, detail.box_score.home
    assert (away.totals.points, home.totals.points) == (20, 17)
    assert len(away.players) > 0
    assert len(home.players) > 0
    assert detail.team_stats is not None
    leaders = detail.team_stats.leaders
    assert leaders.field_goal_pct == "IND"
    assert leaders.three_point_pct == "MIN"
    assert leaders.free_throw_pct == "IND"
    assert leaders.rebounds == "MIN"
    assert leaders.assists == "IND"
    assert leaders.turnovers == "IND"
    assert leaders.steals is None
    assert leaders.blocks == "IND"
    assert detail.win_probability is not None
    seconds = [p.elapsed_seconds for p in detail.win_probability]
    assert len(seconds) == 4
    assert seconds == sorted(seconds)
    assert seconds[0] == 0
    recorded_clock = 720 - (3 * 60 + 42)
    assert max(seconds) <= recorded_clock
    assert detail.season_series is not None
    assert detail.season_series.games == []


@pytest.mark.anyio
async def test_maps_recorded_videos_with_their_duration_as_text(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-preseason-final.json"))

    assert detail.videos is not None
    assert len(detail.videos) == 2
    first = detail.videos[0]
    assert first.title.endswith("Game Highlights")
    assert first.duration == "1:13"
    assert str(first.link_url) == "https://example.com/298"
    assert str(first.thumbnail_url) == "https://example.com/277"
    assert detail.videos[1].duration == "0:16"


@pytest.mark.anyio
async def test_keeps_the_series_empty_when_no_game_was_played(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-preseason-final.json"))

    assert detail.season_series is not None
    assert detail.season_series.total_games == 4
    assert detail.season_series.games == []
    assert detail.season_series.leader is None
    assert (detail.season_series.away_wins, detail.season_series.home_wins) == (0, 0)


@pytest.mark.anyio
async def test_places_each_win_probability_point_at_its_elapsed_game_seconds(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    matched = [
        w["playId"]
        for w in payload["winprobability"]
        if w["playId"] in {p["id"] for p in payload["plays"]}
    ]
    overtime = next(p for p in payload["plays"] if p["id"] == matched[1])
    overtime["period"]["number"] = 5
    overtime["clock"]["displayValue"] = "4:00"

    detail = await sections_of(mock, settings, payload)

    assert detail.win_probability is not None
    seconds = [p.elapsed_seconds for p in detail.win_probability]
    assert seconds[0] == 0
    assert seconds[-1] == 2880 + 60
    assert seconds[-2] == 2880
    assert detail.win_probability[0].home_win_probability == 0.671
    assert detail.win_probability[-1].home_win_probability == 0.688


@pytest.mark.anyio
async def test_orders_win_probability_points_by_elapsed_game_seconds(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(
        mock, settings, load("summary-out-of-order-win-probability.json")
    )

    assert detail.win_probability is not None
    assert [
        (p.elapsed_seconds, p.home_win_probability) for p in detail.win_probability
    ] == [
        (0, 0.5),
        (840, 0.6),
        (1080, 0.55),
        (1500, 0.42),
        (1500, 0.4),
        (1680, 0.45),
        (2880, 0.7),
    ]


@pytest.mark.anyio
async def test_keeps_the_source_order_of_win_probability_points_at_the_same_second(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(
        mock, settings, load("summary-out-of-order-win-probability.json")
    )

    assert detail.win_probability is not None
    assert [
        p.home_win_probability
        for p in detail.win_probability
        if p.elapsed_seconds == 1500
    ] == [0.42, 0.4]


RECORDED_POINT_SECONDS = [
    (
        "summary-final.json",
        [0, 8, 8, 720, 720, 737, 1440, 1440, 1461, 2160, 2176, 2177, 2880],
    ),
    (
        "summary-preseason-final.json",
        [0, 23, 23, 720, 720, 720, 1440, 1440, 1440, 2160, 2160, 2160, 2880],
    ),
]


@pytest.mark.anyio
@pytest.mark.parametrize(("name", "seconds"), RECORDED_POINT_SECONDS)
async def test_keeps_the_recorded_win_probability_points_unchanged(
    mock: respx.MockRouter, settings: Settings, name: str, seconds: list[int]
) -> None:
    detail = await sections_of(mock, settings, load(name))

    assert detail.win_probability is not None
    assert [p.elapsed_seconds for p in detail.win_probability] == seconds
    if name == "summary-preseason-final.json":
        assert [
            p.home_win_probability
            for p in detail.win_probability
            if p.elapsed_seconds == 23
        ] == [0.505, 0.51]


@pytest.mark.anyio
async def test_drops_a_win_probability_point_that_cannot_be_placed(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    placed = len(payload["winprobability"]) - 1
    payload["plays"][1]["clock"]["displayValue"] = "soon"
    payload["plays"][2]["clock"]["displayValue"] = "13:00"
    payload["plays"][3]["period"]["number"] = 0

    detail = await sections_of(mock, settings, payload)

    assert detail.win_probability is not None
    assert len(detail.win_probability) == placed - 3


@pytest.mark.anyio
async def test_returns_no_win_probability_when_no_point_can_be_placed(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    payload["plays"] = []

    detail = await sections_of(mock, settings, payload)

    assert detail.win_probability is None
    assert detail.win_probability_leader is None
    assert detail.win_probability_periods is None


def placed_entries(payload: Payload) -> list[Payload]:
    play_ids = {p["id"] for p in payload["plays"]}
    return [w for w in payload["winprobability"] if w["playId"] in play_ids]


@pytest.mark.anyio
async def test_takes_the_away_team_as_the_win_probability_leader_below_even(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    placed_entries(payload)[-1]["homeWinPercentage"] = 0.25

    detail = await sections_of(mock, settings, payload)

    assert detail.win_probability_leader is not None
    assert detail.win_probability_leader.team_code == "ORL"
    assert detail.win_probability_leader.win_probability == 0.75


@pytest.mark.anyio
async def test_gives_no_win_probability_leader_on_an_even_latest_point(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    placed_entries(payload)[-1]["homeWinPercentage"] = 0.5

    detail = await sections_of(mock, settings, payload)

    assert detail.win_probability_leader is None


@pytest.mark.anyio
async def test_takes_the_win_probability_leader_from_the_last_published_point(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    entries = placed_entries(payload)
    entries[-2]["homeWinPercentage"] = 0.25
    last_play = next(p for p in payload["plays"] if p["id"] == entries[-1]["playId"])
    last_play["clock"]["displayValue"] = "soon"

    detail = await sections_of(mock, settings, payload)

    assert detail.win_probability_leader is not None
    assert detail.win_probability_leader.team_code == "ORL"
    assert detail.win_probability_leader.win_probability == 0.75


def starts_of(detail: GameDetailSections) -> list[tuple[int, int]]:
    assert detail.win_probability_periods is not None
    return [
        (p.number, p.start_elapsed_seconds)
        for p in detail.win_probability_periods.periods
    ]


def play_overtimes(payload: Payload) -> None:
    matched = [
        w["playId"]
        for w in payload["winprobability"]
        if w["playId"] in {p["id"] for p in payload["plays"]}
    ]
    for play_id, period in ((matched[1], 5), (matched[2], 6)):
        play = next(p for p in payload["plays"] if p["id"] == play_id)
        play["period"]["number"] = period
        play["clock"]["displayValue"] = "4:00"


@pytest.mark.anyio
async def test_publishes_every_regulation_period_start_and_the_game_end_from_the_format(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert starts_of(detail) == [(1, 0), (2, 720), (3, 1440), (4, 2160)]
    assert detail.win_probability_periods is not None
    assert detail.win_probability_periods.end_elapsed_seconds == 2880

    payload = load("summary-final.json")
    payload["format"]["regulation"]["clock"] = 600
    mock.get(URL).respond(json=payload)
    shorter = await fetch_sections(settings)

    assert starts_of(shorter) == [(1, 0), (2, 600), (3, 1200), (4, 1800)]
    assert shorter.win_probability_periods is not None
    assert shorter.win_probability_periods.end_elapsed_seconds == 2400


@pytest.mark.anyio
async def test_adds_one_period_per_overtime_played_from_the_play_periods(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    play_overtimes(payload)

    detail = await sections_of(mock, settings, payload)

    assert starts_of(detail) == [
        (1, 0),
        (2, 720),
        (3, 1440),
        (4, 2160),
        (5, 2880),
        (6, 3180),
    ]
    assert detail.win_probability_periods is not None
    assert detail.win_probability_periods.end_elapsed_seconds == 3480

    payload["format"]["overtime"]["clock"] = 600
    mock.get(URL).respond(json=payload)
    longer = await fetch_sections(settings)

    assert starts_of(longer)[4:] == [(5, 2880), (6, 3480)]
    assert longer.win_probability_periods is not None
    assert longer.win_probability_periods.end_elapsed_seconds == 4080


@pytest.mark.anyio
async def test_keeps_regulation_periods_when_no_play_reached_the_last_quarter(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    for index, play in enumerate(payload["plays"]):
        play["period"]["number"] = 1 + index % 2

    detail = await sections_of(mock, settings, payload)

    assert starts_of(detail) == [(1, 0), (2, 720), (3, 1440), (4, 2160)]
    assert detail.win_probability is not None
    assert detail.win_probability_periods is not None
    end = detail.win_probability_periods.end_elapsed_seconds
    assert end == 2880
    assert all(p.elapsed_seconds <= end for p in detail.win_probability)


@pytest.mark.anyio
async def test_publishes_no_periods_without_win_probability(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    payload["plays"] = []
    detail = await sections_of(mock, settings, payload)

    assert detail.win_probability_periods is None

    scheduled = load("summary-scheduled.json")
    mock.get(URL).respond(json=scheduled)
    assert (await fetch_sections(settings)).win_probability_periods is None


@pytest.mark.anyio
async def test_marks_the_leading_side_of_each_team_stat_row(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert detail.team_stats is not None
    leaders = detail.team_stats.leaders
    assert leaders.field_goal_pct == "BOS"
    assert leaders.three_point_pct == "BOS"
    assert leaders.free_throw_pct == "BOS"
    assert leaders.rebounds == "ORL"
    assert leaders.assists == "BOS"
    assert leaders.steals == "BOS"
    assert leaders.blocks == "BOS"


@pytest.mark.anyio
async def test_leads_turnovers_with_the_lower_value(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert detail.team_stats is not None
    assert detail.team_stats.away.turnovers == 19
    assert detail.team_stats.home.turnovers == 17
    assert detail.team_stats.leaders.turnovers == "BOS"


@pytest.mark.anyio
async def test_marks_no_leader_on_a_tied_row(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    set_team_stat(payload, "home", "assists", "22")
    set_team_stat(payload, "home", "turnovers", "19")

    detail = await sections_of(mock, settings, payload)

    assert detail.team_stats is not None
    assert detail.team_stats.leaders.assists is None
    assert detail.team_stats.leaders.turnovers is None


@pytest.mark.anyio
async def test_drops_players_without_a_stat_line_from_the_box_score(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    kept = team_players(payload, "BOS")["athletes"]
    assert any(not a["stats"] for a in kept)

    detail = await sections_of(mock, settings, payload)

    assert detail.box_score is not None
    assert len(detail.box_score.home.players) == len(kept) - 1
    assert len(detail.box_score.away.players) == 7


@pytest.mark.anyio
async def test_splits_made_and_attempted_shots_and_reads_plus_minus_with_its_sign(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    group = team_players(payload, "ORL")
    banchero = athlete(payload, "ORL", "Paolo Banchero")
    set_stat(banchero, group, "fieldGoalsMade-fieldGoalsAttempted", "7-22")
    set_stat(banchero, group, "plusMinus", "+2")
    other = athlete(payload, "ORL", "Franz Wagner")
    set_stat(other, group, "plusMinus", "-9")

    detail = await sections_of(mock, settings, payload)

    assert detail.box_score is not None
    players = {p.display_name: p for p in detail.box_score.away.players}
    line = players["Paolo Banchero"]
    assert (line.field_goals_made, line.field_goals_attempted) == (7, 22)
    assert line.plus_minus == 2
    assert line.starter is True
    assert line.minutes == banchero["stats"][group["keys"].index("minutes")]
    assert players["Franz Wagner"].plus_minus == -9
    assert detail.box_score.away.totals.three_points_attempted == 43


@pytest.mark.anyio
async def test_builds_box_score_photo_urls_from_the_template(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert detail.box_score is not None
    banchero = next(
        p for p in detail.box_score.away.players if p.display_name == "Paolo Banchero"
    )
    assert str(banchero.photo_url) == "https://example.com/players/4432573.png"
    assert banchero.player_id == "4432573"


@pytest.mark.anyio
async def test_counts_series_wins_for_the_away_and_home_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    for event in payload["seasonseries"][0]["events"]:
        for competitor in event["competitors"]:
            competitor["winner"] = competitor["team"]["abbreviation"] == "ORL"

    detail = await sections_of(mock, settings, payload)

    assert detail.season_series is not None
    assert (detail.season_series.away_wins, detail.season_series.home_wins) == (4, 0)
    first = detail.season_series.games[0]
    assert (first.away, first.home) == ("BOS", "ORL")
    assert first.score is not None
    assert (first.score.away, first.score.home) == (110, 123)


@pytest.mark.anyio
async def test_marks_the_current_pre_game_in_the_series_without_score_or_winner(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(
        mock, settings, load("summary-scheduled.json"), PRE_GAME_SERIES_ID
    )

    assert detail.season_series is not None
    assert len(detail.season_series.games) == 1
    game = detail.season_series.games[0]
    assert game.game_id == PRE_GAME_SERIES_ID
    assert game.is_current is True
    assert game.score is None
    assert game.winner is None
    assert detail.season_series.leader is None
    assert (detail.season_series.away_wins, detail.season_series.home_wins) == (0, 0)


@pytest.mark.anyio
async def test_marks_the_current_final_game_in_the_series_with_its_winner(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(
        mock, settings, load("summary-final.json"), SERIES_GAME_ID
    )

    assert detail.season_series is not None
    games = detail.season_series.games
    assert len(games) == 4
    assert [g.is_current for g in games] == [False, False, False, True]
    assert games[-1].winner == "BOS"
    assert games[-1].score is not None
    assert (games[-1].score.away, games[-1].score.home) == (108, 113)


@pytest.mark.anyio
async def test_gives_each_completed_series_game_its_winner(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert detail.season_series is not None
    assert [g.winner for g in detail.season_series.games] == [
        "ORL",
        "BOS",
        "BOS",
        "BOS",
    ]


@pytest.mark.anyio
async def test_leads_the_series_with_the_home_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert detail.season_series is not None
    assert detail.season_series.leader == "BOS"


@pytest.mark.anyio
async def test_leads_the_series_with_the_away_team(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    for event in payload["seasonseries"][0]["events"]:
        for competitor in event["competitors"]:
            competitor["winner"] = competitor["team"]["abbreviation"] == "ORL"

    detail = await sections_of(mock, settings, payload)

    assert detail.season_series is not None
    assert detail.season_series.leader == "ORL"


@pytest.mark.anyio
async def test_leaves_a_tied_series_without_a_leader(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    for index, event in enumerate(payload["seasonseries"][0]["events"]):
        for competitor in event["competitors"]:
            leader = "ORL" if index < 2 else "BOS"
            competitor["winner"] = competitor["team"]["abbreviation"] == leader

    detail = await sections_of(mock, settings, payload)

    assert detail.season_series is not None
    assert (detail.season_series.away_wins, detail.season_series.home_wins) == (2, 2)
    assert detail.season_series.leader is None


@pytest.mark.anyio
@pytest.mark.parametrize("flagged", [[False, False], [True, True]])
async def test_raises_the_source_error_on_a_completed_series_game_without_one_winner(
    mock: respx.MockRouter, settings: Settings, flagged: list[bool]
) -> None:
    payload = load("summary-final.json")
    competitors = payload["seasonseries"][0]["events"][0]["competitors"]
    for competitor, flag in zip(competitors, flagged, strict=True):
        competitor["winner"] = flag

    error = await sections_error_of(mock, settings, payload)

    assert error.reason == f"game {GAME_ID} has a series game without one winner"


@pytest.mark.anyio
async def test_dates_series_games_on_the_us_eastern_day(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    assert payload["seasonseries"][0]["events"][0]["date"] == "2025-11-08T00:00:00Z"

    detail = await sections_of(mock, settings, payload)

    assert detail.season_series is not None
    assert [g.date.isoformat() for g in detail.season_series.games] == [
        "2025-11-07",
        "2025-11-09",
        "2025-11-23",
        "2026-04-12",
    ]


@pytest.mark.anyio
async def test_returns_no_injuries_when_the_summary_has_none(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    payload["injuries"] = []

    detail = await sections_of(mock, settings, payload)

    assert detail.injuries is None


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_injury_status(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    payload["injuries"][1]["injuries"][0]["status"] = "Vacation"

    error = await sections_error_of(mock, settings, payload)

    assert error.reason == f"game {GAME_ID} has an unknown injury status"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_series_game_of_other_teams(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    competitor = payload["seasonseries"][0]["events"][0]["competitors"][0]
    competitor["team"]["abbreviation"] = "MIA"

    error = await sections_error_of(mock, settings, payload)

    assert error.reason == f"game {GAME_ID} has a series game of other teams"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.clear(),
        lambda p: p.pop("gameInfo"),
        lambda p: p.update(boxscore=3),
    ],
    ids=["empty", "no game info", "box score that is not an object"],
)
async def test_raises_the_source_error_on_a_summary_missing_a_used_field(
    mock: respx.MockRouter, settings: Settings, change: Any
) -> None:
    payload = load("summary-final.json")
    change(payload)

    error = await sections_error_of(mock, settings, payload)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["freeThrowPct", "steals", "blocks"])
async def test_raises_the_source_error_on_a_missing_detail_team_stat(
    mock: respx.MockRouter, settings: Settings, name: str
) -> None:
    payload = load("summary-final.json")
    stats = box_team(payload, "away")["statistics"]
    stats[:] = [s for s in stats if s["name"] != name]

    error = await sections_error_of(mock, settings, payload)

    assert error.reason == f"game {GAME_ID} has no {name} stat"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_box_score_stat_that_is_not_a_number(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    group = team_players(payload, "BOS")
    first = group["athletes"][0]
    set_stat(first, group, "fieldGoalsMade-fieldGoalsAttempted", "many")

    error = await sections_error_of(mock, settings, payload)

    assert error.reason == f"game {GAME_ID} has a stat that is not a number"


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
async def test_raises_the_source_error_when_the_summary_request_times_out_or_fails(
    mock: respx.MockRouter, settings: Settings, fails: Any, reason: str
) -> None:
    fails(mock.get(URL))

    error = await sections_error(settings)

    assert error.reason == reason


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("detail_url", "photo_url", "reason"),
    [
        (None, SECTIONS_PHOTO, "game detail URL is not configured"),
        (TEMPLATE, None, "player photo URL is not configured"),
    ],
)
async def test_raises_the_source_error_when_a_summary_url_is_not_configured(
    detail_url: str | None, photo_url: str | None, reason: str
) -> None:
    unset = Settings(  # type: ignore[call-arg]
        _env_file=None, game_detail_url=detail_url, player_photo_url=photo_url
    )
    with respx.mock:
        error = await sections_error(unset)

    assert error.reason == reason


def test_series_meeting_fields_match_the_contract_series_game_except_arena() -> None:
    for name, field in SeriesMeeting.model_fields.items():
        if name == "game_id":
            continue
        assert name in SeriesGame.model_fields
        assert SeriesGame.model_fields[name].annotation == field.annotation
        assert field.metadata == SeriesGame.model_fields[name].metadata
    assert set(SeriesGame.model_fields) - set(SeriesMeeting.model_fields) == {"arena"}


def clocked(tmp_path: Path, clock: list[dt.datetime]) -> SourceClient:
    store = StateStore(tmp_path)
    store.migrate()
    return create_client(store, clock=lambda: clock[0])


FETCHED = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)


@pytest.mark.anyio
async def test_a_final_game_detail_attempt_fetches_again_when_the_stored_entry_is_older_than_its_due_time(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).mock(
        side_effect=[
            httpx.Response(200, json=load("live.json")),
            httpx.Response(200, json=load("final.json")),
        ]
    )
    async with clocked(tmp_path, [FETCHED]) as client:
        await fetch_game_detail(client, GAME_ID, settings, dt.timedelta(seconds=30))
        detail = await fetch_game_detail(
            client, GAME_ID, settings, FETCHED + dt.timedelta(seconds=1)
        )

    assert route.call_count == 2
    away, home = detail.leaders.away, detail.leaders.home
    assert (away.player_id, away.points) == ("4397886", 12)
    assert (home.player_id, home.points) == ("4066648", 21)


@pytest.mark.anyio
async def test_a_final_game_detail_attempt_reuses_an_entry_fetched_at_or_after_its_due_time(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).respond(json=load("final.json"))
    async with clocked(tmp_path, [FETCHED]) as client:
        await fetch_game_detail(client, GAME_ID, settings, FETCHED)
        await fetch_game_detail(client, GAME_ID, settings, FETCHED)
        await fetch_game_detail(
            client, GAME_ID, settings, FETCHED - dt.timedelta(hours=2)
        )

    assert route.call_count == 1


@pytest.mark.anyio
async def test_sections_and_detail_of_one_game_share_one_cached_response(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    route = mock.get(URL).respond(json=load("summary-final.json"))
    fresh = dt.timedelta(seconds=30)
    async with clocked(tmp_path, [FETCHED]) as client:
        await fetch_game_detail_sections(client, GAME_ID, settings, fresh)
        await fetch_game_detail(client, GAME_ID, settings, fresh)

    assert route.call_count == 1


# Guest games: the Harbor City Mariners replace one side of a recorded game.


@pytest.mark.anyio
async def test_maps_the_box_score_team_stats_and_quarters_of_both_sides_of_a_guest_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    rename_team(payload, "ORL")

    detail = await sections_of(mock, settings, payload, SERIES_GAME_ID)

    assert detail.box_score is not None and detail.team_stats is not None
    assert detail.box_score.away.players and detail.box_score.home.players
    assert detail.team_stats.away.rebounds > 0 and detail.team_stats.home.rebounds > 0
    leaders = detail.team_stats.leaders.model_dump().values()
    assert set(leaders) <= {"HCM", "BOS", None}
    assert detail.injuries is not None


@pytest.mark.anyio
async def test_a_guest_player_photo_is_the_headshot_and_null_without_one_while_a_league_player_keeps_the_template(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    rename_team(payload, "ORL")
    headshot(payload, "HCM", "Paolo Banchero", "https://example.com/headshots/pb.png")

    detail = await sections_of(mock, settings, payload, SERIES_GAME_ID)

    assert detail.box_score is not None
    guest = {p.display_name: p.photo_url for p in detail.box_score.away.players}
    league = detail.box_score.home.players
    assert str(guest["Paolo Banchero"]) == "https://example.com/headshots/pb.png"
    assert guest["Franz Wagner"] is None
    assert str(league[0].photo_url) == (
        f"https://example.com/players/{league[0].player_id}.png"
    )


@pytest.mark.anyio
async def test_a_guest_game_has_no_season_series(
    mock: respx.MockRouter, settings: Settings
) -> None:
    league = load("summary-final.json")
    guest = load("summary-final.json")
    rename_team(guest, "ORL")
    mock.get(TEMPLATE.format(game_id="guest")).respond(json=guest)

    with_series = await sections_of(mock, settings, league, SERIES_GAME_ID)
    without_series = await fetch_sections(settings, "guest")

    assert with_series.season_series is not None
    assert without_series.season_series is None


@pytest.mark.anyio
async def test_an_empty_win_probability_of_a_guest_game_is_null(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load("summary-final.json")
    rename_team(payload, "ORL")
    payload["winprobability"] = []

    detail = await sections_of(mock, settings, payload, SERIES_GAME_ID)

    assert detail.win_probability is None
    assert detail.win_probability_leader is None
    assert detail.win_probability_periods is None
