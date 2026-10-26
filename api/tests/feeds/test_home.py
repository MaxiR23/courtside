# api/tests/feeds/test_home.py
#
# Tests for the home feed models.
#
# Tested:
# - A valid home feed with every part 1 field set is accepted, with leaders and finalsPath null
# - A non-null leaders or finalsPath is rejected
# - daysAgo requires days of 2 or more, and days on another title is rejected
# - A game number on a final, final overtime or play-in label is rejected, and one on a playoff label is accepted
# - An end date that is not after the start date is rejected
# - An empty comingUp list and an empty lastGames list are rejected
# - An unknown field and a tip-off not in UTC are rejected
#
# What is covered:
# - A valid feed is accepted and invalid ones are rejected
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_home.py
#
# SEE: api/app/feeds/home.py, api/schemas/home.schema.json, docs/api/home.md

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.home import HomeFeed, LastGamesTitle

Payload = dict[str, Any]


def side(code: str) -> Payload:
    return {"code": code, "name": "Name", "city": "City"}


def last_game(**overrides: object) -> Payload:
    payload: Payload = {
        "id": "g1",
        "away": side("RVR"),
        "home": side("PKS"),
        "score": {"away": 99, "home": 101},
        "winner": "home",
        "label": "final",
        "gameNumber": None,
    }
    payload.update(overrides)
    return payload


def feed(**overrides: object) -> Payload:
    payload: Payload = {
        "season": "2026-27",
        "date": "2027-02-10",
        "scenario": "offDay",
        "comingUp": [
            {
                "key": "allStar",
                "startDate": "2027-02-14",
                "endDate": None,
                "status": "upcoming",
            }
        ],
        "nextGame": {
            "date": "2027-02-11",
            "firstTipOff": "2027-02-12T00:00:00Z",
            "broadcast": "Channel Example",
            "gameCount": 3,
            "inGamesWindow": True,
        },
        "lastGames": {
            "date": "2027-02-09",
            "title": {"key": "lastNight", "days": None},
            "games": [last_game()],
        },
        "leaders": None,
        "finalsPath": None,
    }
    payload.update(overrides)
    return payload


def test_accepts_a_valid_home_feed() -> None:
    parsed = HomeFeed.model_validate(feed())

    assert parsed.leaders is None
    assert parsed.finals_path is None
    assert parsed.last_games is not None
    assert parsed.last_games.games[0].accent is None


def test_accepts_a_feed_with_every_nullable_part_null() -> None:
    parsed = HomeFeed.model_validate(feed(comingUp=None, nextGame=None, lastGames=None))

    assert parsed.coming_up is None


@pytest.mark.parametrize("name", ["leaders", "finalsPath"])
def test_rejects_a_non_null_leaders_or_finals_path(name: str) -> None:
    with pytest.raises(ValidationError):
        HomeFeed.model_validate(feed(**{name: {}}))


def test_rejects_days_ago_without_days_and_days_on_another_title() -> None:
    assert LastGamesTitle.model_validate({"key": "daysAgo", "days": 2}).days == 2
    for title in (
        {"key": "daysAgo", "days": None},
        {"key": "daysAgo", "days": 1},
        {"key": "lastNight", "days": 2},
    ):
        with pytest.raises(ValidationError):
            LastGamesTitle.model_validate(title)


@pytest.mark.parametrize("label", ["final", "finalOvertime", "playIn"])
def test_rejects_a_game_number_on_a_final_or_play_in_label(label: str) -> None:
    payload = feed()
    payload["lastGames"]["games"] = [last_game(label=label, gameNumber=2)]

    with pytest.raises(ValidationError):
        HomeFeed.model_validate(payload)


def test_accepts_a_game_number_on_a_playoff_label() -> None:
    payload = feed()
    payload["lastGames"]["games"] = [last_game(label="finals", gameNumber=7)]

    assert HomeFeed.model_validate(payload).last_games is not None


def test_rejects_an_end_date_not_after_the_start_date() -> None:
    for end in ("2027-02-14", "2027-02-13"):
        payload = feed()
        payload["comingUp"][0]["endDate"] = end
        with pytest.raises(ValidationError):
            HomeFeed.model_validate(payload)
    payload = feed()
    payload["comingUp"][0]["endDate"] = "2027-02-15"
    assert HomeFeed.model_validate(payload).coming_up is not None


def test_rejects_an_empty_coming_up_list_and_an_empty_last_games_list() -> None:
    with pytest.raises(ValidationError):
        HomeFeed.model_validate(feed(comingUp=[]))
    payload = feed()
    payload["lastGames"]["games"] = []
    with pytest.raises(ValidationError):
        HomeFeed.model_validate(payload)


def test_rejects_an_unknown_field_and_a_tip_off_not_in_utc() -> None:
    with pytest.raises(ValidationError):
        HomeFeed.model_validate(feed(extra=1))
    payload = copy.deepcopy(feed())
    payload["nextGame"]["firstTipOff"] = "2027-02-11T19:00:00-05:00"
    with pytest.raises(ValidationError):
        HomeFeed.model_validate(payload)
