# api/tests/feeds/test_power_ranking.py
#
# Tests for the power ranking feed models.
#
# Tested:
# - An available feed of 30 teams and an unavailable feed with no teams are accepted
# - A team name, city, logo, colors and accent may be null
# - Rejects an available feed with fewer than 30 teams and an unavailable feed with teams
# - Rejects ranks out of order, a rank of 0 or 31 and repeated codes
# - Rejects a title share over 1 or under 0, a record that is not wins-losses, an
#   unknown field and an unknown state
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_power_ranking.py
#
# SEE: api/app/feeds/power_ranking.py

import copy
import string
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.power_ranking import PowerRankingFeed

Payload = dict[str, Any]
LETTERS = string.ascii_uppercase


def team(rank: int) -> Payload:
    return {
        "rank": rank,
        "tied": False,
        "team": {
            "code": f"A{LETTERS[(rank - 1) // 26]}{LETTERS[(rank - 1) % 26]}",
            "name": "Thunder",
            "city": "Oklahoma City",
            "logo": None,
            "colors": None,
            "accent": None,
        },
        "record": "60-22",
        "rating": "+7.3",
        "ratingNegative": False,
        "offense": "+4.0",
        "defense": "−2.1",
        "projected": "58-24",
        "playoffs": ">99.9%",
        "title": "12.5%",
        "playoffsLow": False,
        "titleShare": 0.5,
    }


def available() -> Payload:
    return {
        "season": "2026-27",
        "state": "available",
        "teams": [team(rank) for rank in range(1, 31)],
    }


def unavailable() -> Payload:
    return {"season": "2026-27", "state": "unavailable", "teams": []}


def test_accepts_an_available_feed_of_30_teams() -> None:
    feed = PowerRankingFeed.model_validate(available())

    assert len(feed.teams) == 30
    assert feed.model_dump(by_alias=True) == available()


def test_accepts_an_unavailable_feed_with_no_teams() -> None:
    assert PowerRankingFeed.model_validate(unavailable()).teams == []


def test_accepts_a_null_name_and_city() -> None:
    payload = available()
    payload["teams"][0]["team"].update(name=None, city=None)

    assert PowerRankingFeed.model_validate(payload).teams[0].team.name is None


def test_accepts_a_tie_in_rank_order() -> None:
    payload = available()
    payload["teams"][1]["rank"] = 1
    payload["teams"][0]["tied"] = payload["teams"][1]["tied"] = True

    assert PowerRankingFeed.model_validate(payload).teams[1].rank == 1


def mutated(change: Any) -> Payload:
    payload = copy.deepcopy(available())
    change(payload)
    return payload


def swap(payload: Payload) -> None:
    payload["teams"][0], payload["teams"][1] = payload["teams"][1], payload["teams"][0]


def repeat_code(payload: Payload) -> None:
    payload["teams"][1]["team"]["code"] = payload["teams"][0]["team"]["code"]


@pytest.mark.parametrize(
    "payload",
    [
        mutated(lambda p: p["teams"].pop()),
        {**unavailable(), "teams": [team(1)]},
        mutated(swap),
        mutated(lambda p: p["teams"][0].update(rank=0)),
        mutated(lambda p: p["teams"][29].update(rank=31)),
        mutated(repeat_code),
        mutated(lambda p: p["teams"][0].update(titleShare=1.1)),
        mutated(lambda p: p["teams"][0].update(titleShare=-0.1)),
        mutated(lambda p: p["teams"][0].update(record="60 22")),
        mutated(lambda p: p["teams"][0].update(projected="58")),
        mutated(lambda p: p["teams"][0].update(extra=1)),
        mutated(lambda p: p.update(state="hidden")),
        mutated(lambda p: p.update(season="2026")),
    ],
    ids=[
        "29 teams",
        "unavailable with teams",
        "ranks out of order",
        "rank 0",
        "rank 31",
        "repeated code",
        "share over 1",
        "share under 0",
        "bad record",
        "bad projected",
        "unknown field",
        "unknown state",
        "bad season",
    ],
)
def test_rejects_an_invalid_feed(payload: Payload) -> None:
    with pytest.raises(ValidationError):
        PowerRankingFeed.model_validate(payload)
