# api/tests/feeds/test_playoffs_finals.py
#
# Tests for the playoffs finals feed models.
#
# Tested:
# - A complete feed and an in-progress feed with no champion, no MVP, null curves, null deficits, null highlights and players with null values are accepted
# - A feed with no game is accepted
# - A champion while the series is not complete, and none when it is complete, are rejected
# - A curve team or a champion outside the two finalists is rejected
# - A game that is not final, game numbers out of order, and more than 7 games are rejected
# - Lists whose codes differ in order (road, records, bar values, averages) are rejected
# - Bars not exactly 8 or out of order are rejected
# - A better team outside the two codes, or set with a null value, is rejected
# - Curve points past the periods' end or out of order are rejected
# - A non-positive deficit is rejected
# - Road series whose rounds do not increase, or more than 4, are rejected
# - An unknown field is rejected
# - The dump has camelCase keys
# - A feed with a build version is accepted, one with zero is rejected, and a stored feed without the field reads with a null version
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
#
# The valid feeds are built by the finals builder from made-up data.
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_playoffs_finals.py
#
# SEE: api/app/feeds/playoffs_finals.py

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.playoffs_finals import PlayoffsFinalsFeed
from tests.jobs.test_playoffs_finals_feed import (
    BOTTOM,
    TOP,
    built,
    playoffs_of,
    plays,
)

Data = dict[str, Any]


def valid() -> Data:
    return built(plays={"finals-1": plays((30, 0, 2))}).model_dump(
        by_alias=True, mode="json"
    )


def check(data: Data) -> PlayoffsFinalsFeed:
    return PlayoffsFinalsFeed.model_validate(data)


def test_accepts_a_complete_feed_with_a_champion() -> None:
    feed = check(valid())

    assert feed.champion == TOP
    assert feed.games[0].largest_deficit is not None


def test_accepts_an_in_progress_feed_with_nothing_optional() -> None:
    data = built(playoffs_of("TBT", scheduled=2, mvp=False)).model_dump(
        by_alias=True, mode="json"
    )
    for game in data["games"]:
        game["winProbability"] = None
        game["largestDeficit"] = None
        game["leaders"] = None
    for roster in data["averages"]:
        for item in roster["players"]:
            item.update(points=None, rebounds=None, assists=None, blocks=None)
            item["fieldGoalPct"] = None

    feed = check(data)

    assert feed.champion is None and feed.finals_mvp is None
    assert feed.games[0].highlights is None


def test_accepts_a_feed_with_no_game() -> None:
    data = valid()
    data["games"] = []

    assert check(data).games == []


def test_the_dump_has_camel_case_keys() -> None:
    data = valid()

    assert {"curveTeam", "finalsMvp", "headToHead"} <= set(data)
    assert "winProbability" in data["games"][0]


def set_status(data: Data) -> None:
    data["status"] = "in_progress"


def drop_champion(data: Data) -> None:
    data["champion"] = None


def champion_outside(data: Data) -> None:
    data["champion"] = "ZZZ"
    data["curveTeam"] = "ZZZ"


def curve_outside(data: Data) -> None:
    data["status"] = "in_progress"
    data["champion"] = None
    data["curveTeam"] = "ZZZ"


def curve_not_champion(data: Data) -> None:
    data["curveTeam"] = BOTTOM


def scheduled_game(data: Data) -> None:
    data["games"][0]["game"]["status"] = "scheduled"
    data["games"][0]["game"]["score"] = None
    data["games"][0]["game"]["winner"] = None


def games_out_of_order(data: Data) -> None:
    data["games"].reverse()


def too_many_games(data: Data) -> None:
    data["games"] = data["games"] * 2


def road_order(data: Data) -> None:
    data["road"].reverse()


def records_order(data: Data) -> None:
    data["headToHead"]["records"].reverse()


def values_order(data: Data) -> None:
    data["headToHead"]["bars"][0]["values"].reverse()


def averages_order(data: Data) -> None:
    data["averages"].reverse()


def seven_bars(data: Data) -> None:
    data["headToHead"]["bars"].pop()


def bars_out_of_order(data: Data) -> None:
    data["headToHead"]["bars"].reverse()


def better_outside(data: Data) -> None:
    data["headToHead"]["bars"][0]["better"] = "ZZZ"


def better_with_null(data: Data) -> None:
    bar = data["headToHead"]["bars"][0]
    bar["values"][0]["value"] = None
    bar["better"] = TOP


def points_past_end(data: Data) -> None:
    data["games"][0]["winProbability"]["points"][-1]["elapsedSeconds"] = 5000


def points_out_of_order(data: Data) -> None:
    data["games"][0]["winProbability"]["points"].reverse()


def zero_deficit(data: Data) -> None:
    data["games"][0]["largestDeficit"]["points"] = 0


def rounds_flat(data: Data) -> None:
    series = data["road"][0]["series"]
    series[1]["round"] = series[0]["round"]


def five_series(data: Data) -> None:
    series = data["road"][0]["series"]
    data["road"][0]["series"] = [*series, series[-1]]


def unknown_field(data: Data) -> None:
    data["extra"] = 1


@pytest.mark.parametrize(
    "change",
    [
        set_status,
        drop_champion,
        champion_outside,
        curve_outside,
        curve_not_champion,
        scheduled_game,
        games_out_of_order,
        too_many_games,
        road_order,
        records_order,
        values_order,
        averages_order,
        seven_bars,
        bars_out_of_order,
        better_outside,
        better_with_null,
        points_past_end,
        points_out_of_order,
        zero_deficit,
        rounds_flat,
        five_series,
        unknown_field,
    ],
)
def test_rejects_an_invalid_feed(change: Callable[[Data], None]) -> None:
    data = valid()
    change(data)

    with pytest.raises(ValidationError):
        check(data)


def test_accepts_a_build_version_and_rejects_zero_and_reads_none_as_null() -> None:
    stored = valid()
    assert PlayoffsFinalsFeed.model_validate(stored).build_version is None

    assert (
        PlayoffsFinalsFeed.model_validate({**stored, "buildVersion": 1}).build_version
        == 1
    )
    with pytest.raises(ValidationError):
        PlayoffsFinalsFeed.model_validate({**stored, "buildVersion": 0})
