# api/tests/feeds/test_search.py
#
# Tests for the search feed models.
#
# Tested:
# - A valid feed is accepted and serialized with camelCase keys
# - Colors, division rank, number, position, position abbreviation, photo URL,
#   injury and the team primary of a player may be null
# - Rejects 29 teams, a record that is not W-L, a color without "#", a division
#   rank of 0 or 6, a jersey that is not 1 or 2 digits, an unknown injury
#   status, a photo URL that is not a URL and an unknown field
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (null optionals) and error cases of each pattern
#   and limit
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_search.py
#
# SEE: api/app/feeds/search.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.search import SearchFeed

Payload = dict[str, Any]


def team(index: int = 0) -> Payload:
    return {
        "code": "OKC",
        "city": "Oklahoma City",
        "name": "Thunder",
        "colors": {"primary": "#007AC1", "secondary": "#EF3B24"},
        "record": "64-18",
        "division": "Northwest",
        "divisionRank": 1,
    }


def player() -> Payload:
    return {
        "id": "1001",
        "name": "Shai Gilgeous-Alexander",
        "shortName": "S. Gilgeous-Alexander",
        "number": "2",
        "position": "Point Guard",
        "positionAbbr": "PG",
        "photoUrl": "https://example.com/p.png",
        "injury": {"status": "out"},
        "team": {"code": "OKC", "primary": "#007AC1"},
    }


def feed() -> Payload:
    return {"teams": [team(i) for i in range(30)], "players": [player()]}


def with_team(change: Payload) -> Payload:
    payload = feed()
    payload["teams"][0].update(change)
    return payload


def with_player(change: Payload) -> Payload:
    payload = feed()
    payload["players"][0].update(change)
    return payload


def test_accepts_a_valid_feed_and_dumps_camel_case_keys() -> None:
    dumped = SearchFeed.model_validate(feed()).model_dump(mode="json", by_alias=True)

    assert dumped == feed()
    assert "divisionRank" in dumped["teams"][0]
    assert {"shortName", "positionAbbr", "photoUrl"} <= set(dumped["players"][0])


def test_accepts_null_colors_and_a_null_division_rank() -> None:
    payload = with_team(
        {"colors": {"primary": None, "secondary": None}, "divisionRank": None}
    )

    dumped = SearchFeed.model_validate(payload).model_dump(mode="json", by_alias=True)

    assert dumped["teams"][0]["divisionRank"] is None
    assert dumped["teams"][0]["colors"] == {"primary": None, "secondary": None}


def test_accepts_a_player_with_every_optional_field_null() -> None:
    payload = with_player(
        {
            "number": None,
            "position": None,
            "positionAbbr": None,
            "photoUrl": None,
            "injury": None,
            "team": {"code": "OKC", "primary": None},
        }
    )

    dumped = SearchFeed.model_validate(payload).model_dump(mode="json", by_alias=True)

    assert dumped["players"][0]["injury"] is None
    assert dumped["players"][0]["team"]["primary"] is None
    assert dumped["players"][0]["photoUrl"] is None


def test_accepts_no_players() -> None:
    payload = feed()
    payload["players"] = []

    assert SearchFeed.model_validate(payload).players == []


def test_rejects_29_teams() -> None:
    payload = feed()
    payload["teams"].pop()

    with pytest.raises(ValidationError):
        SearchFeed.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        with_team({"record": "64"}),
        with_team({"colors": {"primary": "007AC1", "secondary": None}}),
        with_team({"divisionRank": 0}),
        with_team({"divisionRank": 6}),
        with_team({"extra": 1}),
        with_player({"number": "123"}),
        with_player({"number": "A1"}),
        with_player({"injury": {"status": "broken"}}),
        with_player({"photoUrl": "not a url"}),
        with_player({"team": {"code": "OKC", "primary": "red"}}),
        with_player({"extra": 1}),
    ],
)
def test_rejects_an_invalid_value(payload: Payload) -> None:
    with pytest.raises(ValidationError):
        SearchFeed.model_validate(copy.deepcopy(payload))
