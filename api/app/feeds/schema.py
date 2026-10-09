# api/app/feeds/schema.py
#
# Exports the JSON Schema of every feed model to api/schemas/.
# Run with: cd api && .venv/bin/python -m app.feeds.schema
#
# SEE: docs/adr/0008-contract-generation.md

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema

from app.feeds.game_detail import GameDetailFeed
from app.feeds.games import GamesFeed
from app.feeds.player import PlayerFeed
from app.feeds.standings import StandingsFeed
from app.feeds.team import TeamFeed

SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"

FEEDS: dict[str, type[BaseModel]] = {
    "games": GamesFeed,
    "game-detail": GameDetailFeed,
    "player": PlayerFeed,
    "team": TeamFeed,
    "standings": StandingsFeed,
}


class ContractJsonSchema(GenerateJsonSchema):
    """Drops per-field titles so the generated types get no alias per field."""

    def field_title_should_be_set(self, schema: Any) -> bool:
        return False


def render_schema(model: type[BaseModel]) -> str:
    schema = model.model_json_schema(
        mode="serialization", schema_generator=ContractJsonSchema
    )
    return json.dumps(schema, indent=2) + "\n"


def write_schemas(directory: Path = SCHEMA_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in FEEDS.items():
        path = directory / f"{name}.schema.json"
        path.write_text(render_schema(model), encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    write_schemas()
