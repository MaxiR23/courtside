# api/tests/feeds/test_days.py
#
# Tests for the day feed models.
#
# Tested:
# - A past game with two league sides and null stars is accepted
# - A past game with a star, or with a highlight, is rejected
# - The other Game rules still apply to a past game
# - A day feed with an empty games list is accepted
# - Game still rejects null stars on a league side (the override is local)
# - The committed days schema holds PastGame and PastDay equal to Game and Day
#   of the games schema, apart from their names
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - The mechanical proof that a past game is valid against the games feed's Game schema
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_days.py
#
# SEE: api/app/feeds/days.py, api/schemas/days.schema.json, api/schemas/games.schema.json

import copy
import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.days import DayFeed, PastGame
from app.feeds.games import Game
from app.feeds.schema import SCHEMA_DIR

Payload = dict[str, Any]


def team(code: str) -> Payload:
    return {"code": code, "name": "Name", "city": "City"}


def game(status: str = "scheduled", **overrides: object) -> Payload:
    payload: Payload = {
        "id": "g1",
        "away": team("AAA"),
        "home": team("HHH"),
        "status": status,
        "startTime": "1999-02-06T00:30:00Z",
        "venue": "Arena",
        "stars": {"away": None, "home": None},
    }
    if status == "final":
        payload["lineScore"] = {"away": [20, 25], "home": [22, 30]}
        payload["score"] = {"away": 45, "home": 52}
        payload["winner"] = "home"
        payload["statsAvailability"] = "unavailable"
        payload["highlightsSearchUrl"] = "https://example.com/search"
    payload.update(overrides)
    return payload


def feed(*games: Payload) -> Payload:
    return {
        "generatedAt": "2026-01-15T12:00:00Z",
        "day": {"date": "1999-02-05", "games": list(games)},
    }


def schema(name: str) -> Payload:
    text = (SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8")
    parsed: Payload = json.loads(text)
    return parsed


def test_accepts_a_past_game_with_league_sides_and_null_stars() -> None:
    parsed = PastGame.model_validate(game("final"))

    assert parsed.stars.away is None and parsed.stars.home is None


def test_rejects_a_past_game_with_a_star() -> None:
    star = {
        "playerId": "p1",
        "firstName": "First",
        "lastName": "Last",
        "teamCode": "AAA",
        "photoUrl": "https://example.com/photo.png",
        "shortName": "F. Last",
    }

    with pytest.raises(ValidationError):
        PastGame.model_validate(game(stars={"away": star, "home": None}))


def test_rejects_a_past_game_with_a_highlight() -> None:
    highlight = {
        "title": "Highlights",
        "channel": "Channel",
        "thumbnailUrl": "https://example.com/thumb.png",
        "embedUrl": "https://example.com/embed",
    }

    with pytest.raises(ValidationError):
        PastGame.model_validate(game(highlights=[highlight]))


def test_the_other_game_rules_still_apply() -> None:
    final = game("final")
    del final["lineScore"]

    with pytest.raises(ValidationError):
        PastGame.model_validate(final)
    with pytest.raises(ValidationError):
        PastGame.model_validate(game(winner="home"))
    with pytest.raises(ValidationError):
        PastGame.model_validate(game(home=team("AAA")))


def test_accepts_a_day_with_no_games() -> None:
    assert DayFeed.model_validate(feed()).day.games == []


def test_accepts_a_day_with_a_past_game() -> None:
    assert len(DayFeed.model_validate(feed(game("final"))).day.games) == 1


def test_game_still_rejects_null_stars_on_a_league_side() -> None:
    with pytest.raises(ValidationError):
        Game.model_validate(game())


def test_the_days_schema_equals_the_games_schema_apart_from_the_names() -> None:
    days = schema("days")["$defs"]
    games = schema("games")["$defs"]

    past_game = copy.deepcopy(days["PastGame"])
    base_game = copy.deepcopy(games["Game"])
    del past_game["title"]
    del base_game["title"]
    assert past_game == base_game

    past_day = copy.deepcopy(days["PastDay"])
    base_day = copy.deepcopy(games["Day"])
    del past_day["title"]
    del base_day["title"]
    assert past_day["properties"]["games"]["items"] == {"$ref": "#/$defs/PastGame"}
    past_day["properties"]["games"]["items"] = {"$ref": "#/$defs/Game"}
    assert past_day == base_day
