# api/tests/feeds/test_schema.py
#
# Tests for the JSON Schema export of the feed models.
#
# Tested:
# - The committed games schema matches the models
# - One schema file is written per feed
# - The schema forbids unknown fields and lists nullable fields as required
# - Fields carry no title
#
# What is covered:
# - Happy path, edge case (no field titles) and error case (stale file)
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_schema.py
#
# SEE: api/app/feeds/schema.py, api/schemas/games.schema.json

import json
from pathlib import Path
from typing import Any

from app.feeds.games import GamesFeed
from app.feeds.schema import SCHEMA_DIR, render_schema, write_schemas


def games_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(render_schema(GamesFeed))
    return schema


def test_committed_games_schema_matches_the_models() -> None:
    committed = (SCHEMA_DIR / "games.schema.json").read_text(encoding="utf-8")

    assert committed == render_schema(GamesFeed), (
        "api/schemas/games.schema.json is out of date: run scripts/contract.sh"
    )


def test_writes_one_schema_file_per_feed(tmp_path: Path) -> None:
    written = write_schemas(tmp_path)

    assert written == [tmp_path / "games.schema.json"]
    assert written[0].read_text(encoding="utf-8") == render_schema(GamesFeed)


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
