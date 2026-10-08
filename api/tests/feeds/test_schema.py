# api/tests/feeds/test_schema.py
#
# Tests for the JSON Schema export of the feed models.
#
# Tested:
# - The committed schema of each feed matches its models
# - One schema file is written per feed
# - The schema forbids unknown fields and lists nullable fields as required
# - Fields carry no title
#
# What is covered:
# - Happy path, edge case (no field titles) and error case (stale file)
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_schema.py
#
# SEE: api/app/feeds/schema.py, api/schemas/games.schema.json,
# api/schemas/game-detail.schema.json, api/schemas/player.schema.json,
# api/schemas/team.schema.json

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GamesFeed
from app.feeds.player import PlayerFeed
from app.feeds.schema import FEEDS, SCHEMA_DIR, render_schema, write_schemas
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
    ]
    assert written[0].read_text(encoding="utf-8") == render_schema(GamesFeed)
    assert written[1].read_text(encoding="utf-8") == render_schema(GameDetailFeed)
    assert written[2].read_text(encoding="utf-8") == render_schema(PlayerFeed)
    assert written[3].read_text(encoding="utf-8") == render_schema(TeamFeed)


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
