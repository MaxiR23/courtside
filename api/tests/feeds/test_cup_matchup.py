# api/tests/feeds/test_cup_matchup.py
#
# Tests for the Cup matchup feed models.
#
# Tested:
# - A valid feed is accepted and serialized with camelCase keys
# - A slot with no game and a side with no team are accepted, and so are a projected side and a player with no averages or card fields
# - Rejects a side with a team and no details, a side with details and no team, a projected side without a team, more than five starters, a leader without averages, a path game with a result or scores before it is final, a final path game without its result and scores, a path out of start order, a final slot with a conference, a conference slot without a conference, a championship that counts in the standings and an unknown field
# - A feed with a build version is accepted, one with zero is rejected, and a stored feed without the field reads with a null version
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (null optionals) and error cases of each validator
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_cup_matchup.py
#
# SEE: api/app/feeds/cup_matchup.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.cup_matchup import CupMatchupFeed

Payload = dict[str, Any]


def team(code: str = "ATL") -> Payload:
    return {"code": code, "name": "Hawks", "city": "Atlanta", "guest": False}


def cup_game(stage: str = "quarterfinals", **changes: object) -> Payload:
    data: Payload = {
        "id": "g1",
        "stage": stage,
        "date": "2026-12-02",
        "startTime": "2026-12-03T00:00:00Z",
        "away": team("BOS"),
        "home": team("ATL"),
        "status": "scheduled",
        "score": None,
        "winner": None,
        "broadcast": None,
        "venue": "Arena",
        "city": "Atlanta",
        "neutralSite": stage in ("semifinals", "championship"),
        "countsInStandings": stage != "championship",
        "detailAvailable": False,
    }
    data.update(changes)
    return data


def path_game(day: int = 1, **changes: object) -> Payload:
    data: Payload = {
        "gameId": f"p{day}",
        "stage": "group",
        "startTime": f"2026-11-{day:02d}T00:00:00Z",
        "opponent": team("BOS"),
        "isHome": True,
        "status": "final",
        "result": "win",
        "teamScore": 100,
        "opponentScore": 90,
        "detailAvailable": False,
    }
    data.update(changes)
    return data


def player(index: int = 1, **changes: object) -> Payload:
    data: Payload = {
        "id": f"a{index}",
        "name": f"Player {index}",
        "number": str(index),
        "position": "G",
        "height": "6 ft 5 in",
        "weight": 200,
        "age": 25,
        "birthDate": "2001-01-01",
        "birthplace": "Town, ST",
        "college": "State",
        "experience": 3,
        "photoUrl": "https://example.com/a.png",
        "status": "active",
        "averages": {"points": 20.1, "rebounds": 5.0, "assists": 4.2},
        "starter": True,
        "leader": {"points": True, "rebounds": False, "assists": False},
    }
    data.update(changes)
    return data


def details() -> Payload:
    return {
        "path": [path_game(1), path_game(2)],
        "injuries": [],
        "roster": [player(1), player(2, starter=False)],
    }


def side(**changes: object) -> Payload:
    data: Payload = {
        "label": {
            "key": "seed",
            "conference": "east",
            "seed": 1,
            "quarterfinal": None,
        },
        "rule": "best_group_winner",
        "known": True,
        "projected": False,
        "team": team(),
        "details": details(),
    }
    data.update(changes)
    return data


def valid_feed() -> Payload:
    return {
        "season": "2026-27",
        "id": "east-qf-1",
        "round": "quarterfinals",
        "conference": "east",
        "game": cup_game(),
        "top": side(),
        "bottom": side(team=team("BOS")),
    }


def rejects(feed: Payload, match: str | None = None) -> None:
    with pytest.raises(ValidationError, match=match):
        CupMatchupFeed.model_validate(feed)


def test_accepts_a_valid_feed_and_serializes_camel_case_keys() -> None:
    feed = CupMatchupFeed.model_validate(valid_feed())

    dumped = feed.model_dump(mode="json")
    assert dumped["game"]["countsInStandings"] is True
    assert dumped["game"]["detailAvailable"] is False
    path = dumped["top"]["details"]["path"][0]
    assert (path["isHome"], path["teamScore"]) == (True, 100)
    assert (
        dumped["top"]["details"]["roster"][0]["photoUrl"] == "https://example.com/a.png"
    )


def test_accepts_a_slot_with_no_game_and_a_side_with_no_team() -> None:
    feed = valid_feed()
    feed["game"] = None
    feed["bottom"] = side(known=False, team=None, details=None)

    CupMatchupFeed.model_validate(feed)


def test_accepts_a_projected_side_during_group_play() -> None:
    feed = valid_feed()
    feed["game"] = None
    feed["top"] = side(known=False, projected=True)

    parsed = CupMatchupFeed.model_validate(feed)

    assert parsed.top.projected is True


def test_accepts_a_player_with_no_averages_and_no_card_fields() -> None:
    feed = valid_feed()
    feed["top"]["details"]["roster"][0] = player(
        1,
        averages=None,
        leader={"points": False, "rebounds": False, "assists": False},
        number=None,
        height=None,
        weight=None,
        age=None,
        birthDate=None,
        birthplace=None,
        college=None,
        experience=None,
        photoUrl=None,
    )

    CupMatchupFeed.model_validate(feed)


def test_rejects_a_side_with_a_team_and_no_details() -> None:
    feed = valid_feed()
    feed["top"]["details"] = None

    rejects(feed, "details are set exactly when the team is set")


def test_rejects_a_side_with_details_and_no_team() -> None:
    feed = valid_feed()
    feed["top"]["team"] = None

    rejects(feed, "details are set exactly when the team is set")


def test_rejects_a_projected_side_without_a_team() -> None:
    feed = valid_feed()
    feed["top"] = side(known=False, projected=True, team=None, details=None)

    rejects(feed, "a projected side has a team")


def test_rejects_more_than_five_starters() -> None:
    feed = valid_feed()
    feed["top"]["details"]["roster"] = [player(n) for n in range(1, 7)]

    rejects(feed, "at most 5 starters")


def test_rejects_a_leader_without_averages() -> None:
    feed = valid_feed()
    feed["top"]["details"]["roster"][0]["averages"] = None

    rejects(feed, "leads no stat")


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "scheduled"},
        {"status": "scheduled", "result": None},
        {"status": "scheduled", "result": None, "teamScore": None},
    ],
)
def test_rejects_a_path_game_with_a_result_or_scores_before_it_is_final(
    changes: Payload,
) -> None:
    feed = valid_feed()
    feed["top"]["details"]["path"][0] = path_game(1, **changes)

    rejects(feed, "exactly when final")


@pytest.mark.parametrize(
    "changes",
    [
        {"result": None},
        {"teamScore": None},
        {"opponentScore": None},
    ],
)
def test_rejects_a_final_path_game_without_its_result_and_scores(
    changes: Payload,
) -> None:
    feed = valid_feed()
    feed["top"]["details"]["path"][0] = path_game(1, **changes)

    rejects(feed, "exactly when final")


def test_rejects_a_path_out_of_start_order() -> None:
    feed = valid_feed()
    feed["top"]["details"]["path"] = [path_game(2), path_game(1)]

    rejects(feed, "start order")


def test_rejects_a_final_slot_with_a_conference() -> None:
    feed = valid_feed()
    feed["id"] = "final"
    feed["round"] = "championship"
    feed["game"] = None

    rejects(feed, "only the final")


def test_rejects_a_conference_slot_without_a_conference() -> None:
    feed = valid_feed()
    feed["conference"] = None

    rejects(feed, "only the final")


def test_rejects_a_championship_game_that_counts_in_the_standings() -> None:
    feed = valid_feed()
    feed["id"] = "final"
    feed["round"] = "championship"
    feed["conference"] = None
    feed["game"] = cup_game("championship", countsInStandings=True)

    rejects(feed, "only the championship is outside the standings")


def test_rejects_an_unknown_field() -> None:
    feed = copy.deepcopy(valid_feed())
    feed["extra"] = 1

    rejects(feed)


def test_accepts_a_build_version_and_rejects_zero_and_reads_none_as_null() -> None:
    stored = valid_feed()
    assert CupMatchupFeed.model_validate(stored).build_version is None

    assert (
        CupMatchupFeed.model_validate({**stored, "buildVersion": 1}).build_version == 1
    )
    with pytest.raises(ValidationError):
        CupMatchupFeed.model_validate({**stored, "buildVersion": 0})
