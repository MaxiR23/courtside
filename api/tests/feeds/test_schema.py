# api/tests/feeds/test_schema.py
#
# Tests for the JSON Schema export of the feed models.
#
# Tested:
# - The committed schema of each feed matches its models
# - One schema file is written per feed
# - The schema forbids unknown fields and lists nullable fields as required
# - Fields carry no title
# - Every team object of every feed carries a logo, and one with a code and a logo carries colors (ADR 0068)
#
# What is covered:
# - Happy path, edge case (no field titles) and error case (stale file)
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_schema.py
#
# SEE: api/app/feeds/schema.py, api/schemas/games.schema.json,
# api/schemas/game-detail.schema.json, api/schemas/player.schema.json,
# api/schemas/team.schema.json, api/schemas/standings.schema.json,
# api/schemas/search.schema.json, api/schemas/cup.schema.json,
# api/schemas/cup-matchup.schema.json, api/schemas/playoffs.schema.json,
# api/schemas/playoffs-finals.schema.json, api/schemas/all-star.schema.json,
# api/schemas/calendar.schema.json, api/schemas/days.schema.json

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.feeds.all_star import AllStarFeed
from app.feeds.calendar import CalendarFeed
from app.feeds.cup import CupFeed
from app.feeds.cup_matchup import CupMatchupFeed
from app.feeds.days import DayFeed
from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GamesFeed
from app.feeds.player import PlayerFeed
from app.feeds.playoffs import PlayoffsFeed
from app.feeds.playoffs_finals import PlayoffsFinalsFeed
from app.feeds.schema import FEEDS, SCHEMA_DIR, render_schema, write_schemas
from app.feeds.search import SearchFeed
from app.feeds.standings import StandingsFeed
from app.feeds.team import TeamFeed


def games_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(render_schema(GamesFeed))
    return schema


@pytest.mark.parametrize(("name", "model"), FEEDS.items(), ids=list(FEEDS))
def test_committed_schema_matches_the_models(name: str, model: type[BaseModel]) -> None:
    committed = (SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8")

    assert committed == render_schema(model), (
        f"api/schemas/{name}.schema.json is out of date: run scripts/contract.sh"
    )


def test_writes_one_schema_file_per_feed(tmp_path: Path) -> None:
    written = write_schemas(tmp_path)

    assert written == [
        tmp_path / "games.schema.json",
        tmp_path / "game-detail.schema.json",
        tmp_path / "player.schema.json",
        tmp_path / "team.schema.json",
        tmp_path / "standings.schema.json",
        tmp_path / "search.schema.json",
        tmp_path / "cup.schema.json",
        tmp_path / "cup-matchup.schema.json",
        tmp_path / "playoffs.schema.json",
        tmp_path / "playoffs-finals.schema.json",
        tmp_path / "all-star.schema.json",
        tmp_path / "calendar.schema.json",
        tmp_path / "days.schema.json",
    ]
    assert written[0].read_text(encoding="utf-8") == render_schema(GamesFeed)
    assert written[1].read_text(encoding="utf-8") == render_schema(GameDetailFeed)
    assert written[2].read_text(encoding="utf-8") == render_schema(PlayerFeed)
    assert written[3].read_text(encoding="utf-8") == render_schema(TeamFeed)
    assert written[4].read_text(encoding="utf-8") == render_schema(StandingsFeed)
    assert written[5].read_text(encoding="utf-8") == render_schema(SearchFeed)
    assert written[6].read_text(encoding="utf-8") == render_schema(CupFeed)
    assert written[7].read_text(encoding="utf-8") == render_schema(CupMatchupFeed)
    assert written[8].read_text(encoding="utf-8") == render_schema(PlayoffsFeed)
    assert written[9].read_text(encoding="utf-8") == render_schema(PlayoffsFinalsFeed)
    assert written[10].read_text(encoding="utf-8") == render_schema(AllStarFeed)
    assert written[11].read_text(encoding="utf-8") == render_schema(CalendarFeed)
    assert written[12].read_text(encoding="utf-8") == render_schema(DayFeed)


def test_schema_forbids_unknown_fields() -> None:
    schema = games_schema()

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["Game"]["additionalProperties"] is False


def test_schema_lists_nullable_fields_as_required() -> None:
    assert "broadcast" in games_schema()["$defs"]["Game"]["required"]


def test_schema_gives_no_title_to_fields() -> None:
    schema = games_schema()
    definitions = [schema, *schema["$defs"].values()]

    for definition in definitions:
        for name, prop in definition.get("properties", {}).items():
            assert "title" not in prop, name


def test_detail_schema_lists_optional_sections_as_required() -> None:
    schema: dict[str, Any] = json.loads(render_schema(GameDetailFeed))

    assert "boxScore" in schema["required"]


def test_player_schema_lists_nullable_sections_as_required() -> None:
    schema: dict[str, Any] = json.loads(render_schema(PlayerFeed))

    assert "live" in schema["required"]


def test_team_schema_lists_nullable_sections_as_required() -> None:
    schema: dict[str, Any] = json.loads(render_schema(TeamFeed))

    assert "schedule" in schema["required"]


def test_cup_schema_lists_nullable_fields_as_required() -> None:
    schema: dict[str, Any] = json.loads(render_schema(CupFeed))

    assert "champion" in schema["required"]


def test_cup_matchup_schema_lists_nullable_fields_as_required() -> None:
    schema: dict[str, Any] = json.loads(render_schema(CupMatchupFeed))

    assert "game" in schema["required"]


def test_playoffs_schema_lists_nullable_fields_as_required() -> None:
    schema: dict[str, Any] = json.loads(render_schema(PlayoffsFeed))

    assert "champion" in schema["required"]


def test_all_star_schema_lists_nullable_fields_as_required() -> None:
    schema: dict[str, Any] = json.loads(render_schema(AllStarFeed))

    assert "previous" in schema["required"]


def _team_definitions(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    definitions = {"(root)": schema, **schema.get("$defs", {})}
    return {
        name: definition
        for name, definition in definitions.items()
        if {"code", "logo"} <= set(definition.get("properties", {}))
    }


@pytest.mark.parametrize(("name", "model"), FEEDS.items(), ids=list(FEEDS))
def test_every_team_object_with_a_logo_also_has_colors(
    name: str, model: type[BaseModel]
) -> None:
    schema: dict[str, Any] = json.loads(render_schema(model))

    for definition_name, definition in _team_definitions(schema).items():
        assert "colors" in definition["properties"], definition_name
        assert "logo" in definition["required"], definition_name


@pytest.mark.parametrize(("name", "model"), FEEDS.items(), ids=list(FEEDS))
def test_every_opponent_side_carries_a_logo_and_colors(
    name: str, model: type[BaseModel]
) -> None:
    schema: dict[str, Any] = json.loads(render_schema(model))
    sides = [
        definition
        for definition in schema.get("$defs", {}).values()
        if "guest" in definition.get("properties", {})
    ]

    for side in sides:
        assert {"logo", "colors"} <= set(side["properties"])


def test_the_team_objects_outside_opponent_carry_a_logo() -> None:
    expected = {
        "standings": "StandingsRow",
        "search": "SearchTeam",
        "all-star": "LeagueTeam",
        "player": "Team",
    }
    for feed_name, definition in expected.items():
        schema: dict[str, Any] = json.loads(render_schema(FEEDS[feed_name]))
        assert "logo" in schema["$defs"][definition]["properties"], definition
    search: dict[str, Any] = json.loads(render_schema(SearchFeed))
    assert {"logo", "colors"} <= set(search["$defs"]["SearchPlayerTeam"]["properties"])
    team: dict[str, Any] = json.loads(render_schema(TeamFeed))
    assert "logo" in team["properties"]
