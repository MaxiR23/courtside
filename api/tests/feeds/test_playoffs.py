# api/tests/feeds/test_playoffs.py
#
# Tests for the playoffs feed models.
#
# Tested:
# - A valid picture feed and a valid complete feed are accepted and serialized with camelCase keys
# - Rejects a champion outside complete, no champion when complete, a current round outside the playoffs, a finals game or summary before the finals, stages, picture, play-in, bracket or leaders out of order or of the wrong count, a line on a row other than 6 and 10, a series winner that is not a side, a winner of a series that is not complete, a conference on the finals or none on another series, a round that does not match the id, a side with both a team and currently, wins without a team, an outcome on a game that is not final, a game without an outcome that is final, a team award without its team number, a player award with one, a guest playoff team, a winner on a game that is not final, more than five leaders, ranks that do not increase, a stage status outside the four, stage dates with only one end set, a date span that runs backwards, series games out of start order and an unknown field
# - A null play-in (a season before 2021) is accepted, while a play-in of one table or in the wrong order is still rejected
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (null optionals) and error cases of each validator
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_playoffs.py
#
# SEE: api/app/feeds/playoffs.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.playoffs import PlayoffsFeed

Payload = dict[str, Any]

STAGES = ["playin", "round_1", "round_2", "round_3", "finals"]
SERIES = [
    "east-r1-1",
    "east-r1-2",
    "east-r1-3",
    "east-r1-4",
    "east-r2-1",
    "east-r2-2",
    "east-r3",
    "finals",
    "west-r3",
    "west-r2-1",
    "west-r2-2",
    "west-r1-1",
    "west-r1-2",
    "west-r1-3",
    "west-r1-4",
]
CATEGORIES = [
    "points",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "field_goal_pct",
    "threes_made",
    "double_doubles",
    "minutes",
]


def team(code: str = "ATL") -> Payload:
    return {
        "code": code,
        "name": "Hawks",
        "city": "Atlanta",
        "guest": False,
        "colors": {"primary": "#112233", "secondary": None},
    }


def label(key: str = "seed", conference: str = "east", **parts: Any) -> Payload:
    return {"key": key, "conference": conference, "seed": None, "series": None, **parts}


def side(**changes: Any) -> Payload:
    data: Payload = {
        "label": label(seed=1),
        "team": None,
        "seed": None,
        "wins": None,
        "currently": None,
    }
    return {**data, **changes}


def game(**changes: Any) -> Payload:
    data: Payload = {
        "id": "g1",
        "date": "2027-04-20",
        "startTime": "2027-04-21T00:00:00Z",
        "away": {"code": "BOS", "name": "Celtics", "city": "Boston", "guest": False},
        "home": {"code": "ATL", "name": "Hawks", "city": "Atlanta", "guest": False},
        "status": "scheduled",
        "score": None,
        "winner": None,
        "overtime": False,
        "venue": "Example Arena",
        "broadcast": None,
        "detailAvailable": False,
    }
    return {**data, **changes}


def final_game(**changes: Any) -> Payload:
    return game(
        status="final", score={"away": 90, "home": 100}, winner="home", **changes
    )


def series(series_id: str, **changes: Any) -> Payload:
    data: Payload = {
        "id": series_id,
        "round": 4 if series_id == "finals" else int(series_id.split("-")[1][1]),
        "conference": None if series_id == "finals" else series_id.split("-")[0],
        "top": side(),
        "bottom": side(label=label(seed=8)),
        "status": "upcoming",
        "summary": None,
        "winner": None,
        "games": [],
    }
    return {**data, **changes}


def play_in(conference: str) -> Payload:
    def slot(key: str, **parts: Any) -> Payload:
        return {
            "label": {"key": key, "place": None, "game": None, **parts},
            "team": None,
            "currently": None,
        }

    return {
        "conference": conference,
        "games": [
            {
                "kind": "seven_eight",
                "top": slot("place", place=7),
                "bottom": slot("place", place=8),
                "game": None,
                "outcome": None,
            },
            {
                "kind": "nine_ten",
                "top": slot("place", place=9),
                "bottom": slot("place", place=10),
                "game": None,
                "outcome": None,
            },
            {
                "kind": "eighth_seed",
                "top": slot("loser_of", game="seven_eight"),
                "bottom": slot("winner_of", game="nine_ten"),
                "game": None,
                "outcome": None,
            },
        ],
    }


def row(number: int) -> Payload:
    line = {6: "playoffs", 10: "playin"}.get(number)
    return {
        "seed": number,
        "team": team(),
        "wins": 40,
        "losses": 42,
        "gamesBehind": "3.0",
        "clinch": None,
        "line": line,
    }


def table(conference: str) -> Payload:
    return {"conference": conference, "rows": [row(n) for n in range(1, 11)]}


def stages() -> list[Payload]:
    return [
        {
            "stage": stage,
            "status": "next" if stage == "playin" else "upcoming",
            "firstDate": None,
            "lastDate": None,
        }
        for stage in STAGES
    ]


def picture_feed() -> Payload:
    return {
        "season": "2026-27",
        "state": "picture",
        "postseasonDates": {"firstDate": "2027-04-14", "lastDate": "2027-06-20"},
        "currentRound": None,
        "finalsGame": None,
        "finalsSummary": None,
        "stages": stages(),
        "picture": [table("east"), table("west")],
        "playIn": [play_in("east"), play_in("west")],
        "bracket": [series(series_id) for series_id in SERIES],
        "champion": None,
        "leaders": None,
        "awards": None,
    }


def complete_feed() -> Payload:
    feed = picture_feed()
    feed["state"] = "complete"
    feed["finalsGame"] = 6
    feed["finalsSummary"] = "ATL wins series 4-2"
    feed["champion"] = {
        "team": team(),
        "wins": 4,
        "losses": 2,
        "firstDate": "2027-06-04",
        "lastDate": "2027-06-20",
        "record": "16-6",
        "home": None,
        "road": None,
        "pointDifferential": {"value": "−12", "nonNegative": False},
    }
    feed["leaders"] = [
        {
            "category": category,
            "leaders": [
                {
                    "rank": 1,
                    "playerId": "1",
                    "name": "Example Player",
                    "photoUrl": None,
                    "teamCode": "ATL",
                    "value": "30.1",
                }
            ],
        }
        for category in CATEGORIES
    ]
    feed["awards"] = [
        {
            "code": "mvp",
            "team": None,
            "winners": [
                {
                    "playerId": "1",
                    "name": "Example Player",
                    "photoUrl": None,
                    "teamCode": "ATL",
                }
            ],
        }
    ]
    return feed


def rejected(feed: Payload) -> None:
    with pytest.raises(ValidationError):
        PlayoffsFeed.model_validate(feed)


def test_accepts_a_picture_feed_and_serializes_camel_case_keys() -> None:
    parsed = PlayoffsFeed.model_validate(picture_feed())

    dumped = parsed.model_dump(mode="json")
    assert dumped["postseasonDates"]["firstDate"] == "2027-04-14"
    assert dumped["playIn"][0]["games"][2]["top"]["label"]["key"] == "loser_of"


def test_accepts_a_complete_feed_with_a_champion_leaders_and_awards() -> None:
    parsed = PlayoffsFeed.model_validate(complete_feed())

    assert parsed.champion is not None
    assert parsed.champion.wins == 4


def test_accepts_a_playoffs_feed_with_a_current_round() -> None:
    feed = picture_feed()
    feed["state"] = "playoffs"
    feed["currentRound"] = 2

    assert PlayoffsFeed.model_validate(feed).current_round == 2


def test_accepts_a_complete_series_with_a_final_game() -> None:
    feed = picture_feed()
    top = side(team=team("ATL"), seed=1, wins=4)
    bottom = side(team=team("BOS"), seed=8, wins=0)
    feed["bracket"][0] = series(
        "east-r1-1",
        top=top,
        bottom=bottom,
        status="complete",
        winner="ATL",
        games=[{**final_game(), "number": 1}],
    )

    PlayoffsFeed.model_validate(feed)


def test_rejects_a_champion_outside_complete() -> None:
    feed = complete_feed()
    feed["state"] = "finals"

    rejected(feed)


def test_rejects_no_champion_when_complete() -> None:
    feed = complete_feed()
    feed["champion"] = None

    rejected(feed)


@pytest.mark.parametrize(
    ("state", "current_round"), [("playoffs", None), ("picture", 1), ("finals", 1)]
)
def test_rejects_a_current_round_outside_the_playoffs(
    state: str, current_round: int | None
) -> None:
    feed = picture_feed()
    feed["state"] = state
    feed["currentRound"] = current_round

    rejected(feed)


@pytest.mark.parametrize("field", ["finalsGame", "finalsSummary"])
def test_rejects_a_finals_game_or_summary_before_the_finals(field: str) -> None:
    feed = picture_feed()
    feed[field] = 1 if field == "finalsGame" else "Series tied 1-1"

    rejected(feed)


def test_rejects_stages_out_of_order() -> None:
    feed = picture_feed()
    feed["stages"].reverse()

    rejected(feed)


def test_rejects_four_stages() -> None:
    feed = picture_feed()
    feed["stages"].pop()

    rejected(feed)


def test_rejects_a_stage_status_outside_the_four() -> None:
    feed = picture_feed()
    feed["stages"][0]["status"] = "done"

    rejected(feed)


def test_rejects_stage_dates_with_only_one_end_set() -> None:
    feed = picture_feed()
    feed["stages"][0]["firstDate"] = "2027-04-14"

    rejected(feed)


def test_rejects_a_date_span_that_runs_backwards() -> None:
    feed = picture_feed()
    feed["postseasonDates"] = {"firstDate": "2027-06-20", "lastDate": "2027-04-14"}

    rejected(feed)


def test_rejects_picture_tables_out_of_order() -> None:
    feed = picture_feed()
    feed["picture"].reverse()

    rejected(feed)


def test_rejects_play_in_out_of_order() -> None:
    feed = picture_feed()
    feed["playIn"].reverse()

    rejected(feed)


def test_accepts_a_null_play_in() -> None:
    feed = picture_feed()
    feed["playIn"] = None

    parsed = PlayoffsFeed.model_validate(feed)

    assert parsed.play_in is None
    assert parsed.model_dump(mode="json")["playIn"] is None


def test_rejects_a_play_in_of_one_table() -> None:
    feed = picture_feed()
    feed["playIn"] = feed["playIn"][:1]

    rejected(feed)


def test_rejects_play_in_games_out_of_order() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"].reverse()

    rejected(feed)


def test_rejects_a_bracket_out_of_order() -> None:
    feed = picture_feed()
    feed["bracket"].reverse()

    rejected(feed)


def test_rejects_a_bracket_of_14_series() -> None:
    feed = picture_feed()
    feed["bracket"].pop()

    rejected(feed)


def test_rejects_leaders_out_of_order() -> None:
    feed = complete_feed()
    feed["leaders"].reverse()

    rejected(feed)


def test_rejects_leaders_of_eight_categories() -> None:
    feed = complete_feed()
    feed["leaders"].pop()

    rejected(feed)


@pytest.mark.parametrize("number", [1, 5, 7, 9])
def test_rejects_a_line_on_a_row_other_than_6_and_10(number: int) -> None:
    feed = picture_feed()
    feed["picture"][0]["rows"][number - 1]["line"] = "playoffs"

    rejected(feed)


@pytest.mark.parametrize("number", [6, 10])
def test_rejects_rows_6_and_10_without_their_line(number: int) -> None:
    feed = picture_feed()
    feed["picture"][0]["rows"][number - 1]["line"] = None

    rejected(feed)


def test_accepts_a_picture_table_shorter_than_the_lines() -> None:
    feed = picture_feed()
    feed["picture"][0]["rows"] = [row(n) for n in range(1, 4)]

    PlayoffsFeed.model_validate(feed)


def test_rejects_a_series_winner_that_is_not_a_side() -> None:
    feed = picture_feed()
    feed["bracket"][0] = series(
        "east-r1-1",
        top=side(team=team("ATL"), seed=1, wins=4),
        bottom=side(team=team("BOS"), seed=8, wins=0),
        status="complete",
        winner="MIA",
    )

    rejected(feed)


def test_rejects_a_winner_of_a_series_that_is_not_complete() -> None:
    feed = picture_feed()
    feed["bracket"][0] = series(
        "east-r1-1",
        top=side(team=team("ATL"), seed=1, wins=1),
        status="in_progress",
        winner="ATL",
    )

    rejected(feed)


def test_rejects_a_complete_series_without_a_winner() -> None:
    feed = picture_feed()
    feed["bracket"][0] = series("east-r1-1", status="complete")

    rejected(feed)


def test_rejects_a_conference_on_the_finals() -> None:
    feed = picture_feed()
    feed["bracket"][7]["conference"] = "east"

    rejected(feed)


def test_rejects_no_conference_on_another_series() -> None:
    feed = picture_feed()
    feed["bracket"][0]["conference"] = None

    rejected(feed)


def test_rejects_a_round_that_does_not_match_the_id() -> None:
    feed = picture_feed()
    feed["bracket"][0]["round"] = 2

    rejected(feed)


def test_rejects_series_games_out_of_start_order() -> None:
    feed = picture_feed()
    later = {**game(id="g2", startTime="2027-04-23T00:00:00Z"), "number": 2}
    earlier = {**game(), "number": 1}
    feed["bracket"][0]["games"] = [later, earlier]

    rejected(feed)


def test_rejects_a_side_with_both_a_team_and_currently() -> None:
    feed = picture_feed()
    feed["bracket"][0]["top"] = side(team=team(), currently=team("BOS"))

    rejected(feed)


def test_rejects_wins_without_a_team() -> None:
    feed = picture_feed()
    feed["bracket"][0]["top"] = side(wins=1)

    rejected(feed)


def test_rejects_a_seed_label_without_its_seed() -> None:
    feed = picture_feed()
    feed["bracket"][0]["top"] = side(label=label(seed=None))

    rejected(feed)


def test_rejects_a_play_in_slot_with_both_a_team_and_currently() -> None:
    feed = picture_feed()
    slot = feed["playIn"][0]["games"][0]["top"]
    slot["team"] = team()
    slot["currently"] = team("BOS")

    rejected(feed)


def test_rejects_a_place_label_without_its_place() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["top"]["label"]["place"] = None

    rejected(feed)


def test_rejects_an_outcome_on_a_game_that_is_not_final() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["game"] = game()
    feed["playIn"][0]["games"][0]["outcome"] = {"seed": 7, "loserOut": False}

    rejected(feed)


def test_rejects_a_final_play_in_game_without_an_outcome() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["game"] = final_game()

    rejected(feed)


def test_accepts_a_final_play_in_game_with_its_outcome() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["game"] = final_game()
    feed["playIn"][0]["games"][0]["outcome"] = {"seed": 7, "loserOut": False}

    PlayoffsFeed.model_validate(feed)


def test_rejects_a_winner_on_a_game_that_is_not_final() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["game"] = game(winner="home")

    rejected(feed)


def test_rejects_a_final_game_without_a_score() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["game"] = game(status="final")

    rejected(feed)


def test_rejects_overtime_on_a_scheduled_game() -> None:
    feed = picture_feed()
    feed["playIn"][0]["games"][0]["game"] = game(overtime=True)

    rejected(feed)


def test_rejects_a_guest_playoff_team() -> None:
    feed = picture_feed()
    feed["picture"][0]["rows"][0]["team"] = {**team(), "guest": True}

    rejected(feed)


def test_rejects_a_team_award_without_its_team_number() -> None:
    feed = complete_feed()
    feed["awards"][0] = {**feed["awards"][0], "code": "all_nba"}

    rejected(feed)


def test_rejects_a_player_award_with_a_team_number() -> None:
    feed = complete_feed()
    feed["awards"][0]["team"] = 1

    rejected(feed)


def test_rejects_an_all_rookie_team_number_of_3() -> None:
    feed = complete_feed()
    feed["awards"][0] = {**feed["awards"][0], "code": "all_rookie", "team": 3}

    rejected(feed)


def test_accepts_a_team_award_with_its_team_number() -> None:
    feed = complete_feed()
    feed["awards"][0] = {**feed["awards"][0], "code": "all_nba", "team": 3}

    PlayoffsFeed.model_validate(feed)


def test_rejects_more_than_five_leaders() -> None:
    feed = complete_feed()
    leader = feed["leaders"][0]["leaders"][0]
    feed["leaders"][0]["leaders"] = [{**leader, "rank": n} for n in range(1, 7)]

    rejected(feed)


def test_rejects_ranks_that_do_not_increase() -> None:
    feed = complete_feed()
    leader = feed["leaders"][0]["leaders"][0]
    feed["leaders"][0]["leaders"] = [leader, copy.deepcopy(leader)]

    rejected(feed)


def test_rejects_an_award_without_winners() -> None:
    feed = complete_feed()
    feed["awards"][0]["winners"] = []

    rejected(feed)


def test_rejects_an_unknown_field() -> None:
    feed = picture_feed()
    feed["extra"] = 1

    rejected(feed)
