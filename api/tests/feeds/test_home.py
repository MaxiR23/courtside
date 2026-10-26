# api/tests/feeds/test_home.py
#
# Tests for the home feed models.
#
# Tested:
# - A valid home feed is accepted, with leaders and finalsPath null or set
# - A season label on a season or playoffs title, and none on previousSeason, are rejected
# - Leader categories out of order, repeated, empty or more than four are rejected
# - A Finals path without two finalists, or without three series in round order, is rejected
# - A series result that is not wins, an en dash, then losses is rejected
# - An unknown field in a leader is rejected
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

from app.feeds.home import FinalsPath, HomeFeed, HomeLeaders, LastGamesTitle, PathSeries

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


def leader(category: str, **overrides: object) -> Payload:
    payload: Payload = {
        "category": category,
        "playerId": f"p-{category}",
        "name": "Player Name",
        "photoUrl": "https://example.com/p.png",
        "team": {"code": "PKS"},
        "value": "27.1",
    }
    payload.update(overrides)
    return payload


def leaders(**overrides: object) -> Payload:
    payload: Payload = {
        "title": "season",
        "seasonLabel": None,
        "categories": [leader(c) for c in ("points", "rebounds", "assists", "blocks")],
    }
    payload.update(overrides)
    return payload


def path_series(round_: str, result: str = "4\u20132") -> Payload:
    return {"round": round_, "opponent": side("RVR"), "result": result, "won": True}


ROUNDS = ("firstRound", "conferenceSemifinals", "conferenceFinals")


def finalist(**overrides: object) -> Payload:
    payload: Payload = {"team": side("PKS"), "series": [path_series(r) for r in ROUNDS]}
    payload.update(overrides)
    return payload


def finals_path(**overrides: object) -> Payload:
    payload: Payload = {"finalists": [finalist(), finalist()]}
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


def test_accepts_a_feed_with_leaders_and_a_finals_path() -> None:
    parsed = HomeFeed.model_validate(feed(leaders=leaders(), finalsPath=finals_path()))

    assert parsed.leaders is not None
    assert len(parsed.leaders.categories) == 4
    assert parsed.leaders.categories[0].team is not None
    assert parsed.leaders.categories[0].team.accent is None
    assert parsed.finals_path is not None
    assert len(parsed.finals_path.finalists) == 2
    assert parsed.finals_path.finalists[0].accent is None
    assert parsed.finals_path.finalists[0].series[0].accent is None


def test_rejects_a_season_label_on_season_or_playoffs_and_none_on_previous_season() -> (
    None
):
    assert HomeLeaders.model_validate(
        leaders(title="previousSeason", seasonLabel="2025-26")
    )
    for title, label in (
        ("season", "2026-27"),
        ("playoffs", "2026-27"),
        ("previousSeason", None),
    ):
        with pytest.raises(ValidationError):
            HomeLeaders.model_validate(leaders(title=title, seasonLabel=label))


def test_rejects_leader_categories_out_of_order_repeated_empty_or_more_than_four() -> (
    None
):
    points, rebounds = leader("points"), leader("rebounds")
    for categories in (
        [rebounds, points],
        [points, points],
        [],
        [leader(c) for c in ("points", "rebounds", "assists", "blocks", "blocks")],
        [leader("steals")],
    ):
        with pytest.raises(ValidationError):
            HomeLeaders.model_validate(leaders(categories=categories))
    assert HomeLeaders.model_validate(leaders(categories=[rebounds]))


def test_rejects_a_finals_path_without_two_finalists_or_three_series_in_round_order() -> (
    None
):
    rounds = [path_series(r) for r in ROUNDS]
    bad_series = (rounds[:2], list(reversed(rounds)), [*rounds, rounds[0]])
    for series in bad_series:
        with pytest.raises(ValidationError):
            FinalsPath.model_validate(
                finals_path(finalists=[finalist(series=series), finalist()])
            )
    for finalists in ([finalist()], [finalist(), finalist(), finalist()]):
        with pytest.raises(ValidationError):
            FinalsPath.model_validate(finals_path(finalists=finalists))


def test_rejects_a_series_result_that_is_not_wins_dash_losses() -> None:
    assert (
        PathSeries.model_validate(path_series("firstRound", "4\u20132")).result
        == "4\u20132"
    )
    for result in ("4-2", "5\u20132", "4\u2013", "42"):
        with pytest.raises(ValidationError):
            PathSeries.model_validate(path_series("firstRound", result))


def test_rejects_an_unknown_field_in_a_leader() -> None:
    with pytest.raises(ValidationError):
        HomeLeaders.model_validate(leaders(categories=[leader("points", extra=1)]))


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
