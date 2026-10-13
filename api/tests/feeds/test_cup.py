# api/tests/feeds/test_cup.py
#
# Tests for the Cup feed models.
#
# Tested:
# - A valid feed is accepted and serialized with camelCase keys
# - A not drawn feed, a feed with a champion and a feed with scheduled bracket games are accepted
# - Rejects a champion before the Cup is complete, no champion when complete, 5 groups, groups out of order, stages out of order, the wrong slot order, a winner on a game that is not final, a final game without a score, a championship that counts in the standings, a semifinal not on a neutral court, a side with both a team and a projection, stage dates with only one end set, a group that is final without its 10 games, stage counts that do not add up, a final slot with a conference, a record that is not W-L, a group letter outside A to C and an unknown field
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (null optionals) and error cases of each validator
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_cup.py
#
# SEE: api/app/feeds/cup.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.cup import CupFeed

Payload = dict[str, Any]

SLOTS = [
    "east-qf-1",
    "east-qf-2",
    "east-sf",
    "final",
    "west-sf",
    "west-qf-1",
    "west-qf-2",
]
ROUNDS = ["group", "quarterfinals", "semifinals", "championship"]


def team(code: str = "ATL") -> Payload:
    return {"code": code, "name": "Hawks", "city": "Atlanta", "guest": False}


def game(stage: str = "group", **changes: object) -> Payload:
    data: Payload = {
        "id": "g1",
        "stage": stage,
        "date": "2026-11-03",
        "startTime": "2026-11-04T00:00:00Z",
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


def side(**changes: object) -> Payload:
    data: Payload = {
        "label": {
            "key": "seed",
            "conference": "east",
            "seed": 1,
            "quarterfinal": None,
        },
        "rule": "best_group_winner",
        "known": False,
        "team": None,
        "projected": {"team": team(), "wins": 2, "losses": 0},
    }
    data.update(changes)
    return data


def slot(slot_id: str, round_: str) -> Payload:
    return {
        "id": slot_id,
        "round": round_,
        "conference": None if slot_id == "final" else slot_id.split("-")[0],
        "top": side(),
        "bottom": side(),
        "game": None,
    }


def group(conference: str, letter: str) -> Payload:
    return {
        "name": {"conference": conference, "letter": letter},
        "teams": [team()],
        "rows": [
            {
                "position": 1,
                "team": team(),
                "wins": 2,
                "losses": 0,
                "gamesBehind": None,
                "differential": {"value": "+2.5", "nonNegative": True},
                "total": {"value": "−5", "nonNegative": False},
                "streak": {"kind": "win", "count": 2},
                "pointsFor": 210,
                "pointsAgainst": 200,
                "home": "1-0",
                "away": "1-0",
                "overtime": "0-0",
                "tag": "won_group",
            }
        ],
        "gamesFinal": 2,
        "final": False,
    }


def valid_feed() -> Payload:
    return {
        "season": "2026-27",
        "drawn": True,
        "stage": "group",
        "firstGameDate": "2026-11-03",
        "groupGamesPlayed": 12,
        "groupGamesTotal": 60,
        "champion": None,
        "stages": [
            {
                "stage": stage,
                "status": status,
                "firstDate": "2026-11-03" if stage == "group" else None,
                "lastDate": "2026-11-28" if stage == "group" else None,
            }
            for stage, status in zip(
                ROUNDS, ["in_progress", "next", "upcoming", "upcoming"], strict=True
            )
        ],
        "groups": [group(c, letter) for c in ("east", "west") for letter in "ABC"],
        "wildCard": [
            {
                "conference": conference,
                "rows": [
                    {
                        "rank": 1,
                        "team": team(),
                        "group": {"conference": conference, "letter": "A"},
                        "wins": 3,
                        "losses": 1,
                        "total": {"value": "+8", "nonNegative": True},
                        "pointsFor": 400,
                        "tag": "wild_card",
                    }
                ],
            }
            for conference in ("east", "west")
        ],
        "bracket": [
            slot(slot_id, "quarterfinals" if "qf" in slot_id else "semifinals")
            for slot_id in SLOTS
        ],
        "games": {
            "days": [{"date": "2026-11-03", "games": [game()]}],
            "counts": {
                "all": 1,
                "group": 1,
                "quarterfinals": 0,
                "semifinals": 0,
                "championship": 0,
            },
        },
    }


def rejects(feed: Payload, match: str | None = None) -> None:
    with pytest.raises(ValidationError, match=match):
        CupFeed.model_validate(feed)


def test_accepts_a_valid_feed_and_serializes_camel_case_keys() -> None:
    feed = CupFeed.model_validate(valid_feed())

    dumped = feed.model_dump(mode="json")
    assert dumped["groupGamesTotal"] == 60 and dumped["champion"] is None
    assert dumped["groups"][0]["gamesFinal"] == 2
    assert dumped["games"]["days"][0]["games"][0]["countsInStandings"] is True


def test_accepts_a_feed_that_is_not_drawn() -> None:
    feed = valid_feed()
    feed["drawn"] = False
    feed["stage"] = "draw"
    feed["firstGameDate"] = None
    feed["groupGamesPlayed"] = 0
    for entry in feed["groups"]:
        entry.update(teams=[], rows=[], gamesFinal=0)
    for table in feed["wildCard"]:
        table["rows"] = []
    feed["games"] = {
        "days": [],
        "counts": {
            "all": 0,
            "group": 0,
            "quarterfinals": 0,
            "semifinals": 0,
            "championship": 0,
        },
    }

    assert CupFeed.model_validate(feed).stage == "draw"


def test_accepts_a_complete_feed_with_its_champion_and_scheduled_final() -> None:
    feed = valid_feed()
    feed["stage"] = "complete"
    feed["champion"] = team()
    final = feed["bracket"][3]
    final["game"] = game(
        "championship",
        status="final",
        score={"away": 90, "home": 100},
        winner="home",
    )
    final["top"] = side(
        known=True,
        team=team(),
        projected=None,
        label={
            "key": "semifinal_winner",
            "conference": "east",
            "seed": None,
            "quarterfinal": None,
        },
    )

    parsed = CupFeed.model_validate(feed)

    assert parsed.champion is not None and parsed.champion.code == "ATL"
    assert parsed.bracket[3].game is not None


def test_rejects_a_champion_before_the_cup_is_complete() -> None:
    feed = valid_feed()
    feed["champion"] = team()

    rejects(feed, "champion")


def test_rejects_no_champion_when_the_cup_is_complete() -> None:
    feed = valid_feed()
    feed["stage"] = "complete"

    rejects(feed, "champion")


def test_rejects_five_groups() -> None:
    feed = valid_feed()
    del feed["groups"][5]

    rejects(feed)


def test_rejects_groups_out_of_order() -> None:
    feed = valid_feed()
    feed["groups"][0], feed["groups"][1] = feed["groups"][1], feed["groups"][0]

    rejects(feed, "groups must be")


def test_rejects_stages_out_of_order() -> None:
    feed = valid_feed()
    feed["stages"][0], feed["stages"][1] = feed["stages"][1], feed["stages"][0]

    rejects(feed, "stages must follow")


def test_rejects_wild_card_tables_out_of_order() -> None:
    feed = valid_feed()
    feed["wildCard"].reverse()

    rejects(feed, "east then west")


def test_rejects_the_wrong_slot_order() -> None:
    feed = valid_feed()
    feed["bracket"][0], feed["bracket"][1] = feed["bracket"][1], feed["bracket"][0]

    rejects(feed, "bracket slots")


def test_rejects_a_winner_on_a_game_that_is_not_final() -> None:
    feed = valid_feed()
    feed["games"]["days"][0]["games"][0]["winner"] = "home"

    rejects(feed, "no winner")


def test_rejects_a_final_game_without_a_score() -> None:
    feed = valid_feed()
    feed["games"]["days"][0]["games"][0]["status"] = "final"

    rejects(feed, "requires score")


def test_rejects_a_championship_that_counts_in_the_standings() -> None:
    feed = valid_feed()
    feed["games"]["days"][0]["games"][0] = game("championship", countsInStandings=True)

    rejects(feed, "outside the standings")


def test_rejects_a_group_game_that_does_not_count_in_the_standings() -> None:
    feed = valid_feed()
    feed["games"]["days"][0]["games"][0]["countsInStandings"] = False

    rejects(feed, "outside the standings")


def test_rejects_a_semifinal_that_is_not_on_a_neutral_court() -> None:
    feed = valid_feed()
    feed["games"]["days"][0]["games"][0] = game("semifinals", neutralSite=False)

    rejects(feed, "neutral")


def test_rejects_a_side_with_both_a_team_and_a_projection() -> None:
    feed = valid_feed()
    feed["bracket"][0]["top"]["team"] = team()

    rejects(feed, "not both")


@pytest.mark.parametrize("missing", ["firstDate", "lastDate"])
def test_rejects_stage_dates_with_only_one_end_set(missing: str) -> None:
    feed = valid_feed()
    feed["stages"][0][missing] = None

    rejects(feed, "both dates or none")


def test_rejects_a_group_that_is_final_without_its_10_games() -> None:
    feed = valid_feed()
    feed["groups"][0]["final"] = True

    rejects(feed, "10 games")


def test_rejects_stage_counts_that_do_not_add_up() -> None:
    feed = valid_feed()
    feed["games"]["counts"]["all"] = 5

    rejects(feed, "sum")


def test_rejects_a_final_slot_with_a_conference() -> None:
    feed = valid_feed()
    feed["bracket"][3]["conference"] = "east"

    rejects(feed, "only the final")


def test_rejects_a_conference_slot_without_a_conference() -> None:
    feed = valid_feed()
    feed["bracket"][0]["conference"] = None

    rejects(feed, "only the final")


@pytest.mark.parametrize("record", ["2-", "two", "2 - 1", "-1-2"])
def test_rejects_a_record_that_is_not_wins_dash_losses(record: str) -> None:
    feed = valid_feed()
    feed["groups"][0]["rows"][0]["home"] = record

    rejects(feed)


def test_rejects_a_group_letter_outside_a_to_c() -> None:
    feed = valid_feed()
    feed["groups"][0]["name"]["letter"] = "D"

    rejects(feed)


def test_rejects_a_group_total_other_than_60() -> None:
    feed = valid_feed()
    feed["groupGamesTotal"] = 59

    rejects(feed)


def test_rejects_an_unknown_field() -> None:
    feed = copy.deepcopy(valid_feed())
    feed["extra"] = 1

    rejects(feed)
