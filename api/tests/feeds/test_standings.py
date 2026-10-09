# api/tests/feeds/test_standings.py
#
# Tests for the standings feed models.
#
# Tested:
# - A valid feed is accepted and serialized with camelCase keys
# - Colors, seed, clinch, pct, games behind and streak may be null
# - Rejects a pct with a leading zero, games behind without one decimal, a
#   signed per game with an ASCII minus or a signed zero, a total with a
#   decimal, a color without "#", an unknown clinch, a record that is not
#   W-L, a seed of 0 or 16, a team count that differs from its teams,
#   conferences out of order and an unknown field
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (null optionals) and error cases of each pattern
#   and validator
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_standings.py
#
# SEE: api/app/feeds/standings.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.standings import StandingsFeed

Payload = dict[str, Any]


def row() -> Payload:
    return {
        "code": "OKC",
        "city": "Oklahoma City",
        "name": "Thunder",
        "colors": {"primary": "#007AC1", "secondary": "#EF3B24"},
        "seed": 1,
        "clinch": "z",
        "wins": 64,
        "losses": 18,
        "pct": ".780",
        "gamesBehind": "2.0",
        "streak": {"kind": "loss", "count": 2},
        "home": "34-7",
        "away": "30-10",
        "lastTen": "7-3",
        "division": "12-4",
        "conference": "40-12",
        "pointsFor": "119.0",
        "pointsAgainst": "107.8",
        "differential": {"value": "+11.2", "nonNegative": True},
        "total": {"value": "+914", "nonNegative": True},
    }


def feed() -> Payload:
    return {
        "season": "2025-26",
        "state": "final",
        "gamesPlayed": 64,
        "conferences": [
            {
                "key": "east",
                "name": "Eastern Conference",
                "teamCount": 1,
                "teams": [row()],
            },
            {
                "key": "west",
                "name": "Western Conference",
                "teamCount": 1,
                "teams": [row()],
            },
        ],
        "divisions": [{"name": "Northwest", "conference": "west", "teams": [row()]}],
    }


def with_row(change: Payload) -> Payload:
    payload = feed()
    payload["divisions"][0]["teams"][0].update(change)
    return payload


def test_accepts_a_valid_feed_and_dumps_camel_case_keys() -> None:
    dumped = StandingsFeed.model_validate(feed()).model_dump(mode="json", by_alias=True)

    assert dumped == feed()
    team = dumped["divisions"][0]["teams"][0]
    assert {"gamesBehind", "lastTen", "pointsFor"} <= set(team)
    assert "nonNegative" in team["differential"]
    assert "teamCount" in dumped["conferences"][0]
    assert dumped["gamesPlayed"] == 64


def test_accepts_null_colors_seed_clinch_pct_games_behind_and_streak() -> None:
    payload = with_row(
        {
            "colors": {"primary": None, "secondary": None},
            "seed": None,
            "clinch": None,
            "pct": None,
            "gamesBehind": None,
            "streak": None,
        }
    )

    dumped = StandingsFeed.model_validate(payload).model_dump(
        mode="json", by_alias=True
    )

    team = dumped["divisions"][0]["teams"][0]
    assert team["seed"] is None
    assert team["pct"] is None
    assert team["colors"] == {"primary": None, "secondary": None}


@pytest.mark.parametrize(
    "change",
    [
        {"pct": "0.659"},
        {"pct": "1.5"},
        {"gamesBehind": "2"},
        {"pointsFor": "119"},
        {"differential": {"value": "-4.4", "nonNegative": False}},
        {"differential": {"value": "+0.0", "nonNegative": True}},
        {"total": {"value": "+12.5", "nonNegative": True}},
        {"total": {"value": "+0", "nonNegative": True}},
        {"colors": {"primary": "007AC1", "secondary": "#EF3B24"}},
        {"clinch": "q"},
        {"home": "34 - 7"},
        {"conference": "40–12"},
        {"seed": 0},
        {"seed": 16},
        {"extra": 1},
    ],
    ids=lambda change: next(iter(change)) + str(change),
)
def test_rejects_an_invalid_row(change: Payload) -> None:
    with pytest.raises(ValidationError):
        StandingsFeed.model_validate(with_row(change))


def test_accepts_the_signed_values_with_the_minus_sign() -> None:
    payload = with_row(
        {
            "differential": {"value": "−4.4", "nonNegative": False},
            "total": {"value": "−312", "nonNegative": False},
        }
    )

    StandingsFeed.model_validate(payload)


def test_rejects_a_team_count_that_differs_from_its_teams() -> None:
    payload = feed()
    payload["conferences"][0]["teamCount"] = 2

    with pytest.raises(ValidationError, match="team count"):
        StandingsFeed.model_validate(payload)


def test_rejects_conferences_out_of_order() -> None:
    payload = feed()
    payload["conferences"] = list(reversed(copy.deepcopy(payload["conferences"])))

    with pytest.raises(ValidationError, match="east then west"):
        StandingsFeed.model_validate(payload)


def test_rejects_an_unknown_field() -> None:
    payload = feed()
    payload["extra"] = 1

    with pytest.raises(ValidationError):
        StandingsFeed.model_validate(payload)
