# api/tests/feeds/test_games.py
#
# Tests for the games feed models.
#
# Tested:
# - A feed with a game of each status is accepted
# - A game missing a field its status requires is rejected
# - Invalid times, codes, numbers and URLs are rejected
# - Unknown fields are rejected
# - Serialization uses camelCase keys and carries unknown values as null
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases and error cases of the UTC and status validators
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_games.py
#
# SEE: api/app/feeds/games.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.games import GamesFeed

Payload = dict[str, Any]

STATUSES = ["scheduled", "live", "final", "delayed", "postponed", "canceled"]


def team(code: str) -> Payload:
    return {"code": code, "name": "Name", "city": "City"}


def player(code: str) -> Payload:
    return {
        "playerId": "p1",
        "firstName": "First",
        "lastName": "Last",
        "teamCode": code,
        "photoUrl": "https://example.com/photo.png",
    }


def leader(code: str) -> Payload:
    return {**player(code), "points": 20, "rebounds": 5, "assists": 7}


def star(code: str) -> Payload:
    return {**player(code), "shortName": "F. Last"}


def stats() -> Payload:
    return {
        "fieldGoalPct": 0.45,
        "threePointPct": 0.35,
        "rebounds": 40,
        "assists": 20,
        "turnovers": 10,
    }


def pair(away: object, home: object) -> Payload:
    return {"away": copy.deepcopy(away), "home": copy.deepcopy(home)}


def valid_game(status: str, **overrides: object) -> Payload:
    game: Payload = {
        "id": "g1",
        "away": team("AAA"),
        "home": team("HHH"),
        "status": status,
        "startTime": "2026-01-15T00:30:00Z",
        "venue": "Arena",
        "stars": pair(star("AAA"), star("HHH")),
    }
    if status in ("live", "final"):
        game["lineScore"] = pair([20, 25, 30, 22], [22, 20, 28, 30])
        game["score"] = pair(97, 100)
        game["leaders"] = pair(leader("AAA"), leader("HHH"))
        game["teamStats"] = pair(stats(), stats())
    if status == "live":
        game["period"] = 4
        game["clock"] = "2:10"
    if status == "final":
        game["highlightsSearchUrl"] = "https://example.com/search"
    game.update(overrides)
    return game


def valid_feed(*games: Payload) -> Payload:
    return {
        "generatedAt": "2026-01-15T12:00:00Z",
        "days": [{"date": "2026-01-14", "games": list(games)}],
    }


@pytest.mark.parametrize("status", STATUSES)
def test_accepts_a_feed_with_a_game_of_each_status(status: str) -> None:
    feed = GamesFeed.model_validate(valid_feed(valid_game(status)))

    assert feed.days[0].games[0].status == status


def test_accepts_a_day_with_no_games() -> None:
    feed = GamesFeed.model_validate(valid_feed())

    assert feed.days[0].games == []


@pytest.mark.parametrize(
    "field", ["period", "clock", "lineScore", "score", "leaders", "teamStats"]
)
def test_rejects_a_live_game_without_a_required_field(field: str) -> None:
    game = valid_game("live")
    del game[field]

    with pytest.raises(ValidationError, match=field):
        GamesFeed.model_validate(valid_feed(game))


@pytest.mark.parametrize(
    "field",
    ["lineScore", "score", "leaders", "teamStats", "highlightsSearchUrl"],
)
def test_rejects_a_final_game_without_a_required_field(field: str) -> None:
    game = valid_game("final")
    del game[field]

    with pytest.raises(ValidationError, match=field):
        GamesFeed.model_validate(valid_feed(game))


def test_accepts_a_scheduled_game_without_scores_or_clock() -> None:
    game = valid_game("scheduled")

    assert "score" not in game
    assert "clock" not in game
    GamesFeed.model_validate(valid_feed(game))


def test_rejects_a_game_without_a_home_team() -> None:
    game = valid_game("scheduled")
    del game["home"]

    with pytest.raises(ValidationError, match="home"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_a_game_without_its_stars() -> None:
    game = valid_game("scheduled")
    del game["stars"]

    with pytest.raises(ValidationError, match="stars"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_an_unknown_status() -> None:
    game = valid_game("scheduled")
    game["status"] = "paused"

    with pytest.raises(ValidationError, match="status"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_a_start_time_without_a_timezone() -> None:
    game = valid_game("scheduled", startTime="2026-01-15T00:30:00")

    with pytest.raises(ValidationError, match="startTime"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_a_start_time_outside_utc() -> None:
    game = valid_game("scheduled", startTime="2026-01-14T19:30:00-05:00")

    with pytest.raises(ValidationError, match="must be in UTC"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_a_generated_time_outside_utc() -> None:
    feed = valid_feed()
    feed["generatedAt"] = "2026-01-15T07:00:00-05:00"

    with pytest.raises(ValidationError, match="must be in UTC"):
        GamesFeed.model_validate(feed)


@pytest.mark.parametrize("code", ["ab", "ABCD", "abc", "A1C"])
def test_rejects_a_team_code_that_is_not_three_capital_letters(code: str) -> None:
    game = valid_game("scheduled", away=team(code))

    with pytest.raises(ValidationError, match="code"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_a_percentage_above_one() -> None:
    bad = {**stats(), "fieldGoalPct": 1.2}
    game = valid_game("live", teamStats=pair(bad, stats()))

    with pytest.raises(ValidationError, match="fieldGoalPct"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_negative_points_in_a_period() -> None:
    game = valid_game("live", lineScore=pair([-1, 20], [20, 20]))

    with pytest.raises(ValidationError, match="lineScore"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_an_empty_line_score_for_a_team() -> None:
    game = valid_game("live", lineScore=pair([], [20, 20]))

    with pytest.raises(ValidationError, match="lineScore"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_a_photo_url_that_is_not_an_http_url() -> None:
    bad = {**star("AAA"), "photoUrl": "not a url"}
    game = valid_game("scheduled", stars=pair(bad, star("HHH")))

    with pytest.raises(ValidationError, match="photoUrl"):
        GamesFeed.model_validate(valid_feed(game))


def test_rejects_an_unknown_field() -> None:
    game = valid_game("scheduled", surprise=True)

    with pytest.raises(ValidationError, match="surprise"):
        GamesFeed.model_validate(valid_feed(game))


def test_serializes_with_camel_case_keys() -> None:
    feed = GamesFeed.model_validate(valid_feed(valid_game("live")))

    dumped = feed.model_dump(mode="json")

    assert "generatedAt" in dumped
    game = dumped["days"][0]["games"][0]
    assert "startTime" in game
    assert "lineScore" in game
    assert "start_time" not in game


def test_serializes_an_unknown_broadcast_as_null() -> None:
    feed = GamesFeed.model_validate(valid_feed(valid_game("scheduled")))

    game = feed.model_dump(mode="json")["days"][0]["games"][0]

    assert game["broadcast"] is None


def test_accepts_overtime_periods_in_the_line_score() -> None:
    game = valid_game(
        "final",
        lineScore=pair([20, 20, 20, 20, 10, 5], [20, 20, 20, 20, 10, 6]),
    )

    feed = GamesFeed.model_validate(valid_feed(game))

    away_line = feed.days[0].games[0].line_score
    assert away_line is not None
    assert len(away_line.away) == 6
