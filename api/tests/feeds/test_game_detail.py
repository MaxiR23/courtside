# api/tests/feeds/test_game_detail.py
#
# Tests for the game detail feed models.
#
# Tested:
# - A game of each status is accepted; a final game with every section is accepted
# - Any optional section being absent is accepted and serialized as null
# - A live or final game missing a field its status requires is rejected
# - A winner is a side (away or home) and only a final game has one
# - A stat leader is a side; a tie is a null leader
# - Series games: a score and a winner come together, the winner is one of the
#   game's teams, and at most one game is the current game; the current game
#   may have neither
# - Series leader: one of the teams with more wins, or null on equal wins
# - Last games: at most five, newest first, may be empty
# - Win probability periods: numbered from 1, start at 0, increase, and
#   bound every win probability point; they require win probability
# - Win probability leader: the side ahead at the last point and its probability,
#   null when even or without win probability
# - Win probability points: in non-decreasing elapsedSeconds order; equal consecutive seconds are accepted
# - Injury playerId: set, absent or null is accepted (null when absent); empty is rejected
# - Injury status, win probability, UTC time and unknown fields are validated
# - A guest side without a code keeps a null record, standing, injuries and last games, has no series, and may be the opponent of a last game
# - A guest game: a null record, standing, injuries and last games on the guest side, box score players without a photo, a guest stat leader and win probability leader, no win probability and no season series
# - A per-side section is null exactly on a guest side; a guest game has no season series; a league box score player has a photo; the two sides differ; a league side's last game may be against a guest
# - Serialization uses camelCase keys
# - Venue city: null or absent is accepted and serialized as null; an empty city is rejected
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases and error cases of the status and leader validators
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_game_detail.py
#
# SEE: api/app/feeds/game_detail.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.game_detail import GameDetailFeed

Payload = dict[str, Any]

STATUSES = ["scheduled", "live", "final", "delayed", "postponed", "canceled"]
OPTIONAL_SECTIONS = [
    "stars",
    "boxScore",
    "winProbability",
    "winProbabilityLeader",
    "winProbabilityPeriods",
    "injuries",
    "lastGames",
    "standings",
    "seasonSeries",
    "highlights",
    "highlightsSearchUrl",
    "videos",
    "broadcast",
]


def record() -> Payload:
    return {"wins": 30, "losses": 12}


def team(code: str) -> Payload:
    return {"code": code, "name": "Name", "city": "City", "record": record()}


def star(code: str) -> Payload:
    return {
        "playerId": "p1",
        "firstName": "First",
        "lastName": "Last",
        "teamCode": code,
        "photoUrl": "https://example.com/photo.png",
        "shortName": "F. Last",
    }


def pair(away: object, home: object) -> Payload:
    return {"away": copy.deepcopy(away), "home": copy.deepcopy(home)}


def stats() -> Payload:
    return {
        "fieldGoalPct": 0.45,
        "threePointPct": 0.35,
        "freeThrowPct": 0.8,
        "rebounds": 40,
        "assists": 20,
        "turnovers": 10,
        "steals": 7,
        "blocks": 4,
    }


def leaders() -> Payload:
    return {
        "fieldGoalPct": "away",
        "threePointPct": "home",
        "freeThrowPct": "away",
        "rebounds": "home",
        "assists": None,
        "turnovers": "away",
        "steals": "home",
        "blocks": "away",
    }


def line() -> Payload:
    return {
        "points": 20,
        "fieldGoalsMade": 8,
        "fieldGoalsAttempted": 15,
        "threePointsMade": 2,
        "threePointsAttempted": 6,
        "freeThrowsMade": 2,
        "freeThrowsAttempted": 3,
        "offensiveRebounds": 1,
        "defensiveRebounds": 5,
        "rebounds": 6,
        "assists": 4,
        "turnovers": 2,
        "steals": 1,
        "blocks": 0,
        "fouls": 3,
    }


def box_player() -> Payload:
    return {
        **line(),
        "playerId": "p1",
        "displayName": "First Last",
        "starter": True,
        "minutes": "32:10",
        "plusMinus": -3,
        "photoUrl": "https://example.com/photo.png",
    }


def box_team() -> Payload:
    totals = {
        **line(),
        "fieldGoalPct": 0.5,
        "threePointPct": 0.3,
        "freeThrowPct": 0.7,
    }
    return {"players": [box_player()], "totals": totals}


def opponent(code: str | None, **overrides: object) -> Payload:
    return {"code": code, "name": None, "city": None, "guest": False, **overrides}


def last_game(date: str) -> Payload:
    return {
        "date": date,
        "opponent": opponent("BBB"),
        "isHome": True,
        "result": "win",
        "teamScore": 100,
        "opponentScore": 90,
    }


def standing() -> Payload:
    return {
        "conference": "east",
        "conferenceRank": 3,
        "record": record(),
        "homeRecord": record(),
        "awayRecord": record(),
        "lastTen": record(),
    }


def series_game() -> Payload:
    return {
        "date": "2025-12-01",
        "away": "AAA",
        "home": "HHH",
        "isCurrent": False,
        "score": {"away": 99, "home": 101},
        "winner": "HHH",
        "arena": "Arena",
    }


def valid_game(status: str, **overrides: object) -> Payload:
    game: Payload = {
        "id": "g1",
        "status": status,
        "startTime": "2026-01-15T00:30:00Z",
        "venue": {"name": "Arena", "city": "City"},
        "away": team("AAA"),
        "home": team("HHH"),
    }
    if status in ("live", "final"):
        game["lineScore"] = pair([20, 25, 30, 22], [22, 20, 28, 30])
        game["score"] = pair(97, 100)
        game["teamStats"] = {**pair(stats(), stats()), "leaders": leaders()}
    if status == "live":
        game["period"] = 4
        game["clock"] = "2:10"
    if status == "final":
        game["winner"] = "home"
    game.update(overrides)
    return game


def full_game() -> Payload:
    return valid_game(
        "final",
        broadcast="Network",
        venue={
            "name": "Arena",
            "city": "City",
            "photoUrl": "https://example.com/arena.png",
        },
        stars=pair(star("AAA"), star("HHH")),
        boxScore=pair(box_team(), box_team()),
        winProbability=[{"elapsedSeconds": 0, "homeWinProbability": 0.5}],
        winProbabilityLeader=None,
        winProbabilityPeriods={
            "periods": [
                {"number": 1, "startElapsedSeconds": 0},
                {"number": 2, "startElapsedSeconds": 10},
            ],
            "endElapsedSeconds": 20,
        },
        injuries=pair(
            [{"displayName": "A B", "status": "out", "comment": "Knee"}],
            [],
        ),
        lastGames=pair([last_game("2026-01-10"), last_game("2026-01-08")], []),
        standings=pair(standing(), standing()),
        seasonSeries={
            "totalGames": 4,
            "awayWins": 1,
            "homeWins": 1,
            "leader": None,
            "games": [series_game()],
        },
        highlights=[
            {
                "title": "T",
                "channel": "C",
                "thumbnailUrl": "https://example.com/t.png",
                "embedUrl": "https://example.com/e",
            }
        ],
        highlightsSearchUrl="https://example.com/search",
        videos=[
            {
                "title": "V",
                "duration": "1:30",
                "thumbnailUrl": "https://example.com/v.png",
                "linkUrl": "https://example.com/v",
            }
        ],
    )


def without(payload: Payload, key: str) -> Payload:
    result = copy.deepcopy(payload)
    if key.startswith("venue."):
        del result["venue"][key.removeprefix("venue.")]
    else:
        del result[key]
    if key == "winProbability":
        del result["winProbabilityPeriods"]  # periods require the points
    return result


@pytest.mark.parametrize("status", STATUSES)
def test_accepts_a_game_of_each_status(status: str) -> None:
    feed = GameDetailFeed.model_validate(valid_game(status))

    assert feed.status == status


def test_accepts_a_final_game_with_every_section() -> None:
    feed = GameDetailFeed.model_validate(full_game())

    assert feed.box_score is not None
    assert feed.videos is not None
    assert feed.venue.photo_url is not None


@pytest.mark.parametrize("key", [*OPTIONAL_SECTIONS, "venue.photoUrl", "venue.city"])
def test_accepts_any_optional_section_being_absent(key: str) -> None:
    feed = GameDetailFeed.model_validate(without(full_game(), key))
    dumped = feed.model_dump(mode="json")

    if key.startswith("venue."):
        assert dumped["venue"][key.removeprefix("venue.")] is None
    else:
        assert dumped[key] is None


def test_accepts_a_venue_with_a_null_city() -> None:
    feed = GameDetailFeed.model_validate(
        valid_game("scheduled", venue={"name": "Arena", "city": None})
    )

    assert feed.venue.city is None
    assert feed.model_dump(mode="json", by_alias=True)["venue"]["city"] is None


def test_rejects_a_venue_with_an_empty_city() -> None:
    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(
            valid_game("scheduled", venue={"name": "Arena", "city": ""})
        )


@pytest.mark.parametrize(
    "field", ["period", "clock", "lineScore", "score", "teamStats"]
)
def test_rejects_a_live_game_without_a_required_field(field: str) -> None:
    game = valid_game("live")
    del game[field]

    with pytest.raises(ValidationError, match=field):
        GameDetailFeed.model_validate(game)


@pytest.mark.parametrize("field", ["lineScore", "score", "winner"])
def test_rejects_a_final_game_without_a_required_field(field: str) -> None:
    game = valid_game("final")
    del game[field]

    with pytest.raises(ValidationError, match=field):
        GameDetailFeed.model_validate(game)


def test_rejects_a_winner_that_is_not_a_side() -> None:
    with pytest.raises(ValidationError, match="winner"):
        GameDetailFeed.model_validate(valid_game("final", winner="HHH"))


def test_rejects_a_winner_on_a_game_that_is_not_final() -> None:
    with pytest.raises(ValidationError, match="has no winner"):
        GameDetailFeed.model_validate(valid_game("live", winner="home"))


def test_accepts_stat_leaders_as_sides() -> None:
    feed = GameDetailFeed.model_validate(valid_game("live"))

    assert feed.team_stats is not None
    assert feed.team_stats.leaders.rebounds == "home"


def test_rejects_a_stat_leader_that_is_not_a_side() -> None:
    game = valid_game("live")
    game["teamStats"]["leaders"]["blocks"] = "HHH"

    with pytest.raises(ValidationError, match="blocks"):
        GameDetailFeed.model_validate(game)


def test_accepts_a_tied_stat_row_with_no_leader() -> None:
    game = valid_game("live")
    game["teamStats"]["leaders"]["rebounds"] = None

    feed = GameDetailFeed.model_validate(game)

    assert feed.team_stats is not None
    assert feed.team_stats.leaders.rebounds is None


def test_rejects_a_missing_stat_leader_row() -> None:
    game = valid_game("live")
    del game["teamStats"]["leaders"]["rebounds"]

    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(game)


def series_feed(**series: Any) -> Payload:
    game = full_game()
    game["seasonSeries"].update(series)
    return game


def test_accepts_a_current_series_game_without_score_or_winner() -> None:
    current = {**series_game(), "isCurrent": True, "score": None, "winner": None}

    feed = GameDetailFeed.model_validate(series_feed(games=[series_game(), current]))

    assert feed.season_series is not None
    assert feed.season_series.games[1].score is None
    assert feed.season_series.games[1].winner is None


def test_rejects_a_series_game_with_a_score_and_no_winner() -> None:
    game = {**series_game(), "winner": None}

    with pytest.raises(ValidationError, match="a score and a winner"):
        GameDetailFeed.model_validate(series_feed(games=[game]))


def test_rejects_a_series_game_with_a_winner_and_no_score() -> None:
    game = {**series_game(), "score": None}

    with pytest.raises(ValidationError, match="a score and a winner"):
        GameDetailFeed.model_validate(series_feed(games=[game]))


def test_rejects_a_series_game_winner_that_is_not_one_of_its_teams() -> None:
    game = {**series_game(), "winner": "ZZZ"}

    with pytest.raises(ValidationError, match="series game winner"):
        GameDetailFeed.model_validate(series_feed(games=[game]))


def test_rejects_more_than_one_current_series_game() -> None:
    current = {**series_game(), "isCurrent": True}

    with pytest.raises(ValidationError, match="at most one"):
        GameDetailFeed.model_validate(series_feed(games=[current, current]))


def test_rejects_a_series_leader_that_is_not_one_of_the_teams() -> None:
    with pytest.raises(ValidationError, match="series leader must be the away"):
        GameDetailFeed.model_validate(series_feed(awayWins=2, homeWins=1, leader="ZZZ"))


@pytest.mark.parametrize(
    ("away_wins", "home_wins", "leader"),
    [(1, 1, "AAA"), (2, 1, "HHH"), (1, 2, "AAA")],
)
def test_rejects_a_series_leader_that_does_not_have_more_wins(
    away_wins: int, home_wins: int, leader: str
) -> None:
    with pytest.raises(ValidationError, match="more wins"):
        GameDetailFeed.model_validate(
            series_feed(awayWins=away_wins, homeWins=home_wins, leader=leader)
        )


def test_accepts_a_tied_series_with_no_leader() -> None:
    feed = GameDetailFeed.model_validate(series_feed())

    assert feed.season_series is not None
    assert feed.season_series.leader is None


def test_rejects_a_series_with_no_leader_and_unequal_wins() -> None:
    with pytest.raises(ValidationError, match="more wins"):
        GameDetailFeed.model_validate(series_feed(awayWins=2, homeWins=1))


def test_rejects_more_than_five_last_games() -> None:
    dates = [f"2026-01-{day:02d}" for day in range(10, 3, -1)]
    games = [last_game(date) for date in dates[:6]]

    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(valid_game("final", lastGames=pair(games, [])))


def test_rejects_last_games_that_are_not_newest_first() -> None:
    games = [last_game("2026-01-08"), last_game("2026-01-10")]

    with pytest.raises(ValidationError, match="newest first"):
        GameDetailFeed.model_validate(valid_game("final", lastGames=pair([], games)))


def test_accepts_a_team_with_no_last_games() -> None:
    feed = GameDetailFeed.model_validate(valid_game("final", lastGames=pair([], [])))

    assert feed.last_games is not None
    assert feed.last_games.away == []


def test_rejects_an_unknown_injury_status() -> None:
    injury = {"displayName": "A B", "status": "sidelined"}

    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(valid_game("final", injuries=pair([injury], [])))


def test_accepts_an_injury_with_a_player_id_and_serializes_it() -> None:
    injury = {"playerId": "4397183", "displayName": "A B", "status": "out"}

    feed = GameDetailFeed.model_validate(
        valid_game("final", injuries=pair([injury], []))
    )

    dumped = feed.model_dump(mode="json", by_alias=True)
    assert dumped["injuries"]["away"][0]["playerId"] == "4397183"


def test_accepts_an_injury_without_a_player_id_as_null() -> None:
    injury = {"displayName": "A B", "status": "out"}

    feed = GameDetailFeed.model_validate(
        valid_game("final", injuries=pair([injury], []))
    )

    dumped = feed.model_dump(mode="json", by_alias=True)
    assert dumped["injuries"]["away"][0]["playerId"] is None


def test_rejects_an_empty_player_id() -> None:
    injury = {"playerId": "", "displayName": "A B", "status": "out"}

    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(valid_game("final", injuries=pair([injury], [])))


def test_accepts_day_to_day_injury_status() -> None:
    injury = {"displayName": "A B", "status": "day-to-day"}

    feed = GameDetailFeed.model_validate(
        valid_game("final", injuries=pair([injury], []))
    )

    assert feed.injuries is not None
    assert feed.injuries.away is not None
    assert feed.injuries.away[0].comment is None


def test_rejects_an_empty_win_probability() -> None:
    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(valid_game("final", winProbability=[]))


def test_rejects_a_win_probability_above_one() -> None:
    point = {"elapsedSeconds": 10, "homeWinProbability": 1.2}

    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(valid_game("final", winProbability=[point]))


def periods_game(**periods: Any) -> Payload:
    game = full_game()
    game["winProbabilityPeriods"].update(periods)
    return game


def test_accepts_win_probability_periods_with_points_inside_the_game() -> None:
    game = full_game()
    game["winProbability"].append({"elapsedSeconds": 20, "homeWinProbability": 0.6})
    game["winProbabilityLeader"] = {"side": "home", "winProbability": 0.6}

    feed = GameDetailFeed.model_validate(game)

    assert feed.win_probability_periods is not None
    assert [p.number for p in feed.win_probability_periods.periods] == [1, 2]
    assert feed.win_probability_periods.end_elapsed_seconds == 20


def test_rejects_periods_not_numbered_one_by_one_from_one() -> None:
    for numbers in ([2, 3], [1, 3], [2, 1]):
        periods = [
            {"number": n, "startElapsedSeconds": i * 10} for i, n in enumerate(numbers)
        ]
        with pytest.raises(ValidationError, match="numbered"):
            GameDetailFeed.model_validate(periods_game(periods=periods))


def test_rejects_a_first_period_that_does_not_start_at_zero() -> None:
    periods = [
        {"number": 1, "startElapsedSeconds": 5},
        {"number": 2, "startElapsedSeconds": 10},
    ]

    with pytest.raises(ValidationError, match="start at 0"):
        GameDetailFeed.model_validate(periods_game(periods=periods))


def test_rejects_period_starts_that_do_not_increase() -> None:
    periods = [
        {"number": 1, "startElapsedSeconds": 0},
        {"number": 2, "startElapsedSeconds": 10},
        {"number": 3, "startElapsedSeconds": 10},
    ]

    with pytest.raises(ValidationError, match="increase"):
        GameDetailFeed.model_validate(periods_game(periods=periods))


def test_rejects_a_game_end_not_after_the_last_period_start() -> None:
    with pytest.raises(ValidationError, match="after the last period start"):
        GameDetailFeed.model_validate(periods_game(endElapsedSeconds=10))


def test_rejects_win_probability_periods_without_win_probability() -> None:
    game = full_game()
    del game["winProbability"]

    with pytest.raises(ValidationError, match="require win probability"):
        GameDetailFeed.model_validate(game)


def test_rejects_a_win_probability_point_after_the_game_end() -> None:
    game = full_game()
    game["winProbability"].append({"elapsedSeconds": 21, "homeWinProbability": 0.6})

    with pytest.raises(ValidationError, match="after the game end"):
        GameDetailFeed.model_validate(game)


def test_serializes_win_probability_periods_with_camel_case_keys() -> None:
    dumped = GameDetailFeed.model_validate(full_game()).model_dump(mode="json")

    assert dumped["winProbabilityPeriods"] == {
        "periods": [
            {"number": 1, "startElapsedSeconds": 0},
            {"number": 2, "startElapsedSeconds": 10},
        ],
        "endElapsedSeconds": 20,
    }


def leader_game(points: list[float], leader: Payload | None) -> Payload:
    game = full_game()
    game["winProbability"] = [
        {"elapsedSeconds": i * 10, "homeWinProbability": p}
        for i, p in enumerate(points)
    ]
    game["winProbabilityLeader"] = leader
    game["winProbabilityPeriods"]["endElapsedSeconds"] = 10 * len(points) + 10
    return game


def test_accepts_the_home_team_as_the_leader_of_a_latest_point_above_even() -> None:
    leader = {"side": "home", "winProbability": 0.68}

    feed = GameDetailFeed.model_validate(leader_game([0.68], leader))

    assert feed.win_probability_leader is not None
    assert feed.win_probability_leader.side == "home"


def test_accepts_the_away_team_as_the_leader_of_a_latest_point_below_even() -> None:
    leader = {"side": "away", "winProbability": 1 - 0.25}

    feed = GameDetailFeed.model_validate(leader_game([0.25], leader))

    assert feed.win_probability_leader is not None
    assert feed.win_probability_leader.side == "away"
    assert feed.win_probability_leader.win_probability == 0.75


def test_accepts_no_leader_on_an_exactly_even_latest_point() -> None:
    feed = GameDetailFeed.model_validate(leader_game([0.7, 0.5], None))

    assert feed.win_probability_leader is None


def test_reads_the_leader_off_the_last_point_in_feed_order() -> None:
    leader = {"side": "home", "winProbability": 0.7}
    game = leader_game([0.3, 0.7], leader)
    game["winProbability"][0]["elapsedSeconds"] = 10
    game["winProbability"][1]["elapsedSeconds"] = 10

    feed = GameDetailFeed.model_validate(game)

    assert feed.win_probability_leader is not None
    assert feed.win_probability_leader.side == "home"


def test_rejects_win_probability_points_that_go_back_in_game_time() -> None:
    game = full_game()
    game["winProbability"] = [
        {"elapsedSeconds": 10, "homeWinProbability": 0.6},
        {"elapsedSeconds": 5, "homeWinProbability": 0.6},
    ]
    game["winProbabilityLeader"] = {"side": "home", "winProbability": 0.6}

    with pytest.raises(ValidationError, match="game time order"):
        GameDetailFeed.model_validate(game)


def test_accepts_win_probability_points_at_the_same_second() -> None:
    game = leader_game([0.4, 0.6], {"side": "home", "winProbability": 0.6})
    game["winProbability"][0]["elapsedSeconds"] = 10
    game["winProbability"][1]["elapsedSeconds"] = 10

    feed = GameDetailFeed.model_validate(game)

    assert feed.win_probability is not None
    assert [p.elapsed_seconds for p in feed.win_probability] == [10, 10]


def test_rejects_a_leader_on_an_exactly_even_latest_point() -> None:
    leader = {"side": "home", "winProbability": 0.5}

    with pytest.raises(ValidationError, match="win probability leader"):
        GameDetailFeed.model_validate(leader_game([0.5], leader))


def test_rejects_no_leader_when_the_latest_point_is_not_even() -> None:
    with pytest.raises(ValidationError, match="win probability leader"):
        GameDetailFeed.model_validate(leader_game([0.68], None))


def test_rejects_a_leader_that_is_not_the_side_ahead() -> None:
    leader = {"side": "away", "winProbability": 0.68}

    with pytest.raises(ValidationError, match="win probability leader"):
        GameDetailFeed.model_validate(leader_game([0.68], leader))


def test_rejects_a_leader_probability_that_does_not_match_the_latest_point() -> None:
    leader = {"side": "home", "winProbability": 0.7}

    with pytest.raises(ValidationError, match="win probability leader"):
        GameDetailFeed.model_validate(leader_game([0.68], leader))


def test_rejects_a_leader_without_win_probability() -> None:
    game = without(full_game(), "winProbability")
    game["winProbabilityLeader"] = {"side": "home", "winProbability": 0.6}

    with pytest.raises(ValidationError, match="win probability leader"):
        GameDetailFeed.model_validate(game)


def test_serializes_the_win_probability_leader_with_camel_case_keys() -> None:
    leader = {"side": "home", "winProbability": 0.68}

    dumped = GameDetailFeed.model_validate(leader_game([0.68], leader)).model_dump(
        mode="json", by_alias=True
    )

    assert dumped["winProbabilityLeader"] == leader


def test_rejects_a_start_time_not_in_utc() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        GameDetailFeed.model_validate(
            valid_game("scheduled", startTime="2026-01-15T00:30:00-05:00")
        )


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(valid_game("scheduled", extra=1))

    game = full_game()
    game["boxScore"]["away"]["players"][0]["extra"] = 1
    with pytest.raises(ValidationError):
        GameDetailFeed.model_validate(game)


def test_serializes_camel_case_keys_and_absent_sections_as_null() -> None:
    dumped = GameDetailFeed.model_validate(valid_game("scheduled")).model_dump(
        mode="json"
    )

    assert dumped["startTime"] == "2026-01-15T00:30:00Z"
    assert dumped["boxScore"] is None
    assert dumped["venue"]["photoUrl"] is None
    assert "start_time" not in dumped


def guest_detail() -> Payload:
    """A final game whose away side is the invented Harbor City Mariners."""
    game = full_game()
    box = game["boxScore"]
    box["away"]["players"][0]["photoUrl"] = None
    game.update(
        away={**team("HCM"), "guest": True, "record": None},
        winner="away",
        winProbability=None,
        winProbabilityPeriods=None,
        winProbabilityLeader=None,
        injuries=pair(None, []),
        lastGames=pair(
            None,
            [
                {
                    **last_game("2026-01-10"),
                    "opponent": opponent(
                        "HCM", guest=True, name="Mariners", city="Harbor City"
                    ),
                }
            ],
        ),
        standings=pair(None, standing()),
        seasonSeries=None,
        stars=pair(None, star("HHH")),
    )
    return game


def test_accepts_a_guest_game_without_league_data_for_the_guest_side() -> None:
    feed = GameDetailFeed.model_validate(guest_detail())

    assert feed.away.guest and feed.away.record is None
    assert feed.standings is not None and feed.standings.away is None
    assert feed.injuries is not None and feed.injuries.away is None
    assert feed.last_games is not None and feed.last_games.away is None
    assert feed.season_series is None and feed.win_probability is None
    assert feed.box_score is not None
    assert feed.box_score.away.players[0].photo_url is None
    assert feed.team_stats is not None
    assert feed.team_stats.leaders.field_goal_pct == "away"


def test_accepts_a_guest_win_probability_leader() -> None:
    game = guest_detail()
    game["winProbability"] = [{"elapsedSeconds": 0, "homeWinProbability": 0.2}]
    game["winProbabilityLeader"] = {"side": "away", "winProbability": 0.8}
    game["winProbabilityPeriods"] = {
        "periods": [{"number": 1, "startElapsedSeconds": 0}],
        "endElapsedSeconds": 20,
    }

    feed = GameDetailFeed.model_validate(game)

    assert feed.win_probability_leader is not None
    assert feed.win_probability_leader.side == "away"


def test_accepts_the_last_game_of_a_league_side_against_a_guest_opponent() -> None:
    feed = GameDetailFeed.model_validate(guest_detail())

    assert feed.last_games is not None and feed.last_games.home is not None
    assert feed.last_games.home[0].opponent.code == "HCM"


@pytest.mark.parametrize("section", ["standings", "injuries", "lastGames"])
def test_rejects_a_section_set_on_a_guest_side(section: str) -> None:
    game = guest_detail()
    game[section] = full_game()[section]

    with pytest.raises(ValidationError, match=section):
        GameDetailFeed.model_validate(game)


@pytest.mark.parametrize("section", ["standings", "injuries", "lastGames"])
def test_rejects_a_section_null_on_a_league_side(section: str) -> None:
    game = full_game()
    game[section] = pair(None, game[section]["home"])

    with pytest.raises(ValidationError, match=section):
        GameDetailFeed.model_validate(game)


def test_rejects_a_record_on_a_guest_side_and_none_on_a_league_side() -> None:
    guest = guest_detail()
    guest["away"]["record"] = record()
    league = full_game()
    league["away"]["record"] = None

    for game in (guest, league):
        with pytest.raises(ValidationError, match="record"):
            GameDetailFeed.model_validate(game)


def test_rejects_a_star_on_a_guest_side() -> None:
    game = guest_detail()
    game["stars"] = pair(star("HCM"), star("HHH"))

    with pytest.raises(ValidationError, match="a guest side has no star"):
        GameDetailFeed.model_validate(game)


def test_rejects_a_season_series_on_a_guest_game() -> None:
    game = guest_detail()
    game["seasonSeries"] = full_game()["seasonSeries"]

    with pytest.raises(ValidationError, match="a guest game has no season series"):
        GameDetailFeed.model_validate(game)


def test_rejects_a_null_photo_on_a_league_box_score_player() -> None:
    game = full_game()
    game["boxScore"]["home"]["players"][0]["photoUrl"] = None

    with pytest.raises(ValidationError, match="a league box score player has a photo"):
        GameDetailFeed.model_validate(game)


def test_rejects_two_sides_with_the_same_code() -> None:
    game = valid_game("scheduled", home=team("AAA"))

    with pytest.raises(ValidationError, match="two different teams"):
        GameDetailFeed.model_validate(game)


def codeless_guest_detail() -> Payload:
    game = guest_detail()
    game["away"] = {**game["away"], "code": None, "name": "Mariners"}
    return game


def test_accepts_a_guest_without_a_code_with_no_league_data() -> None:
    feed = GameDetailFeed.model_validate(codeless_guest_detail())

    assert feed.away.code is None and feed.away.guest
    assert feed.away.record is None
    assert feed.standings is not None and feed.standings.away is None
    assert feed.injuries is not None and feed.injuries.away is None
    assert feed.last_games is not None and feed.last_games.away is None
    assert feed.season_series is None


def test_accepts_a_last_game_whose_opponent_is_a_guest_without_a_code() -> None:
    game = guest_detail()
    guest = opponent(None, guest=True, name="Mariners", city="Harbor City")
    game["lastGames"] = pair(None, [{**last_game("2026-01-10"), "opponent": guest}])

    feed = GameDetailFeed.model_validate(game)

    assert feed.last_games is not None and feed.last_games.home is not None
    assert feed.last_games.home[0].opponent.code is None


def test_rejects_a_last_game_whose_opponent_is_a_guest_with_neither_code_nor_name() -> (
    None
):
    game = guest_detail()
    nobody = opponent(None, guest=True)
    game["lastGames"] = pair(None, [{**last_game("2026-01-10"), "opponent": nobody}])

    with pytest.raises(ValidationError, match="a code or a name"):
        GameDetailFeed.model_validate(game)


def test_rejects_a_win_probability_leader_that_is_a_team_code() -> None:
    leader = {"side": "HHH", "winProbability": 0.68}

    with pytest.raises(ValidationError, match="side"):
        GameDetailFeed.model_validate(leader_game([0.68], leader))
