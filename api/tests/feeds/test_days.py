# api/tests/feeds/test_days.py
#
# Tests for the day feed models.
#
# Tested:
# - A past game with two league sides and null stars is accepted
# - A past game with a star is rejected; a highlight is accepted, because the stored one is added when served
# - The other Game rules still apply to a past game
# - A final All-Star past game without a lineScore is accepted (ADR 0051), and a final league past game without it is rejected
# - A day feed with an empty games list is accepted
# - A day feed carries its season and label with camelCase keys; a missing
#   season, a season before 1994 and a bad label are rejected
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
        "season": 1999,
        "seasonLabel": "1998-99",
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


def test_accepts_a_past_game_with_a_highlight_added_when_served() -> None:
    highlight = {
        "title": "Highlights",
        "channel": "Channel",
        "thumbnailUrl": "https://example.com/thumb.png",
        "embedUrl": "https://example.com/embed",
    }

    parsed = PastGame.model_validate(game(highlights=[highlight]))

    assert parsed.highlights is not None and len(parsed.highlights) == 1


def test_the_other_game_rules_still_apply() -> None:
    final = game("final")
    del final["lineScore"]

    with pytest.raises(ValidationError):
        PastGame.model_validate(final)
    with pytest.raises(ValidationError):
        PastGame.model_validate(game(winner="home"))
    with pytest.raises(ValidationError):
        PastGame.model_validate(game(home=team("AAA")))


def test_accepts_a_final_all_star_past_game_without_a_line_score() -> None:
    final = game(
        "final", allStar={"roundLabel": "All-Star Game", "championship": False}
    )
    del final["lineScore"]

    parsed = PastGame.model_validate(final)

    assert parsed.line_score is None
    assert parsed.score is not None


def test_accepts_a_day_with_no_games() -> None:
    assert DayFeed.model_validate(feed()).day.games == []


def test_accepts_a_day_with_a_past_game() -> None:
    assert len(DayFeed.model_validate(feed(game("final"))).day.games) == 1


def test_serializes_the_season_with_camel_case_keys() -> None:
    body = DayFeed.model_validate(feed()).model_dump(mode="json", by_alias=True)

    assert body["season"] == 1999
    assert body["seasonLabel"] == "1998-99"


def test_rejects_a_missing_season_a_season_before_1994_and_a_bad_label() -> None:
    missing = feed()
    del missing["season"]

    with pytest.raises(ValidationError):
        DayFeed.model_validate(missing)
    with pytest.raises(ValidationError):
        DayFeed.model_validate({**feed(), "season": 1993, "seasonLabel": "1992-93"})
    with pytest.raises(ValidationError):
        DayFeed.model_validate({**feed(), "seasonLabel": "1999"})


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
