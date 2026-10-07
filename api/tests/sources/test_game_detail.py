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
# - Raises the source error on an invalid payload, an unknown team, a missing home or away team, a team without player stats, a missing team stat, a stat that is not a number, an empty display name, a timeout, an error status and a missing URL
# - GameDetail uses the same field types as the contract Game
# - Maps a recorded scheduled game and a recorded final game to their detail sections: venue, box score, team stats, win probability, injuries, season series and videos
# - Maps recorded videos with their duration as text
# - Places each win probability point at its elapsed game seconds, in regulation and overtime, and drops a point that cannot be placed
# - Marks the leading side of each team stat row: the lower value leads turnovers and a tie has no leader
# - Drops players without a stat line, splits made and attempted shots, reads plus-minus with its sign and builds photo URLs from the template
# - Counts the series wins of the away and home team and dates series games on the US Eastern day
# - Raises the source error on an unknown injury status, a series game of other teams, a summary missing a used field, a missing detail team stat, a box score stat that is not a number, a timeout, an error status and a missing URL
# - SeriesMeeting uses the same field types as the contract SeriesGame, except the arena
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
# No live summary was recorded yet, so there is no live summary fixture. One
# win probability entry of summary-final.json was given a play id that matches
# no play, to cover the dropped point.
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


# Game detail sections

SECTIONS_PHOTO = "https://example.com/players/{player_id}.png"


async def fetch_sections(settings: Settings) -> GameDetailSections:
    async with create_client() as client:
        return await fetch_game_detail_sections(client, GAME_ID, settings)


async def sections_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch_sections(settings)
    return raised.value


async def sections_of(
    mock: respx.MockRouter, settings: Settings, payload: Payload
) -> GameDetailSections:
    mock.get(URL).respond(json=payload)
    return await fetch_sections(settings)


async def sections_error_of(
    mock: respx.MockRouter, settings: Settings, payload: Payload
) -> SourceError:
    mock.get(URL).respond(json=payload)
    return await sections_error(settings)


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
    assert detail.injuries is not None
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
    assert detail.videos is None


@pytest.mark.anyio
async def test_maps_a_recorded_final_game_to_its_detail_sections(
    mock: respx.MockRouter, settings: Settings
) -> None:
    detail = await sections_of(mock, settings, load("summary-final.json"))

    assert (detail.venue.name, detail.venue.city) == ("TD Garden", "Boston")
    assert str(detail.venue.photo_url) == "https://example.com/61"
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
    assert detail.injuries.home == []
    assert len(detail.injuries.away) == 5
    assert detail.season_series is not None
    assert detail.season_series.total_games == 4
    assert (detail.season_series.home_wins, detail.season_series.away_wins) == (3, 1)
    assert len(detail.season_series.games) == 4
    assert detail.season_series.games[-1].game_id == "401811041"
    assert detail.videos is None


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
    assert seconds[1] == 2880 + 60
    assert seconds[-1] == 2880
    assert detail.win_probability[0].home_win_probability == 0.671


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
    assert (first.score.away, first.score.home) == (110, 123)


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
