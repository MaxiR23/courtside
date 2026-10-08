# api/tests/feeds/test_player.py
#
# Tests for the player feed models.
#
# Tested:
# - A player with every section is accepted; every nullable field may be null
#   and is serialized as null
# - A game tag keeps its kind with null conference, round and game; its round
#   is 1 to 4 and its kind is known
# - The live block: the line may be null, and is the line of the player
# - Percentages are 0 to 1, counting stats are not negative, made is within
#   attempted
# - Last games: at most five, newest first, no All-Star game
# - Season rows: newest first, one per season, minutes only in per game rows
# - Game log: newest first, only an All-Star entry has a null opponent
# - Profile: seasons and debutSeason agree with the regular season rows
# - Averages rows have at least one game; season labels look like 2025-26
# - Injury status, UTC time and unknown fields are validated
# - Serialization uses camelCase keys
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (equal dates, null optionals) and error cases of
#   each validator
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_player.py
#
# SEE: api/app/feeds/player.py

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.player import GameTag, PlayerFeed

Payload = dict[str, Any]

NULLABLE_SECTIONS = [
    "number",
    "photoUrl",
    "injury",
    "summary",
    "nextGame",
    "live",
    "milestones",
    "gameLog",
]


def game_tag() -> Payload:
    return {"kind": "playoffs", "conference": "east", "round": 2, "game": 3}


def next_game() -> Payload:
    return {
        "gameId": "g9",
        "startTime": "2026-01-15T00:30:00Z",
        "opponent": "BBB",
        "isHome": True,
        "tag": game_tag(),
        "arena": "Arena",
        "city": "City",
        "broadcast": "TV",
        "detailAvailable": False,
    }


def box_player() -> Payload:
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
        "playerId": "p1",
        "displayName": "First Last",
        "starter": True,
        "minutes": "32:10",
        "plusMinus": -3,
        "photoUrl": "https://example.com/photo.png",
    }


def live() -> Payload:
    return {
        "gameId": "g10",
        "opponent": "BBB",
        "isHome": False,
        "period": 2,
        "clock": "5:30",
        "teamScore": 50,
        "opponentScore": 48,
        "line": box_player(),
    }


def log_entry(date: str, kind: str = "regular") -> Payload:
    return {
        "gameId": f"g{date}",
        "date": date,
        "opponent": "BBB",
        "isHome": True,
        "kind": kind,
        "tag": None,
        "result": "win",
        "teamScore": 100,
        "opponentScore": 90,
        "minutes": 32,
        "fieldGoalsMade": 8,
        "fieldGoalsAttempted": 15,
        "fieldGoalPct": 0.533,
        "threePointsMade": 2,
        "threePointsAttempted": 6,
        "threePointPct": 0.333,
        "freeThrowsMade": 2,
        "freeThrowsAttempted": 3,
        "freeThrowPct": 0.667,
        "rebounds": 6,
        "assists": 4,
        "blocks": 0,
        "steals": 1,
        "fouls": 3,
        "turnovers": 2,
        "points": 20,
        "detailAvailable": True,
    }


def stat_row(per_game: bool = True) -> Payload:
    return {
        "gamesPlayed": 70,
        "gamesStarted": 60,
        "minutes": 33.5 if per_game else None,
        "fieldGoalsMade": 8.1,
        "fieldGoalsAttempted": 16.2,
        "fieldGoalPct": 0.5,
        "threePointsMade": 2.1,
        "threePointsAttempted": 6.2,
        "threePointPct": 0.34,
        "freeThrowsMade": 3.1,
        "freeThrowsAttempted": 4.2,
        "freeThrowPct": 0.74,
        "offensiveRebounds": 1.1,
        "defensiveRebounds": 4.2,
        "rebounds": 5.3,
        "assists": 4.4,
        "blocks": 0.5,
        "steals": 1.2,
        "fouls": 2.1,
        "turnovers": 2.3,
        "points": 21.4,
    }


def season_row(season: str, per_game: bool = True) -> Payload:
    return {**stat_row(per_game), "season": season, "teams": ["AAA"]}


def split(seasons: list[str]) -> Payload:
    return {
        "perGame": [season_row(s) for s in seasons],
        "totals": [season_row(s, per_game=False) for s in seasons],
        "career": {"perGame": stat_row(), "totals": stat_row(per_game=False)},
    }


def average_row() -> Payload:
    return {
        "gamesPlayed": 10,
        "minutes": 30.5,
        "fieldGoalPct": 0.5,
        "threePointPct": 0.35,
        "freeThrowPct": 0.8,
        "rebounds": 5.5,
        "assists": 4.5,
        "blocks": 0.5,
        "steals": 1.5,
        "fouls": 2.5,
        "turnovers": 2.0,
        "points": 20.5,
    }


def milestone_counts() -> Payload:
    return {
        "doubleDoubles": 5,
        "tripleDoubles": 1,
        "disqualifications": 0,
        "ejections": 0,
        "technicals": 2,
        "flagrants": 0,
        "assistTurnoverRatio": 2.1,
        "stealTurnoverRatio": 0.6,
    }


def valid_player() -> Payload:
    return {
        "id": "p1",
        "firstName": "First",
        "lastName": "Last",
        "number": "00",
        "position": "Guard",
        "team": {"code": "AAA", "name": "Name", "city": "City"},
        "photoUrl": "https://example.com/photo.png",
        "injury": {
            "status": "out",
            "comment": "Knee",
            "updatedAt": "2026-01-14T10:00:00Z",
        },
        "profile": {
            "height": {"display": "6-5", "cm": 196},
            "weight": {"lb": 210, "kg": 95},
            "birthDate": "2000-02-03",
            "age": 25,
            "birthplace": {"place": "Town", "country": "USA"},
            "college": "College",
            "draft": {"year": 2020, "round": 1, "pick": 5, "teamName": "Team"},
            "seasons": 2,
            "debutSeason": "2024-25",
        },
        "summary": {
            "season": "2025-26",
            "points": {"value": 21.4, "rank": 12},
            "rebounds": {"value": 5.3, "rank": None},
            "assists": {"value": 4.4, "rank": 30},
            "fieldGoalPct": {"value": 0.5, "rank": 40},
        },
        "nextGame": next_game(),
        "live": live(),
        "lastGames": [log_entry("2026-01-12"), log_entry("2026-01-10")],
        "averages": {
            "regular": {**average_row(), "season": "2025-26"},
            "playoffs": None,
            "career": average_row(),
        },
        "seasons": {
            "regular": split(["2025-26", "2024-25"]),
            "playoffs": {"perGame": [], "totals": [], "career": None},
        },
        "milestones": {
            "season": "2025-26",
            "current": milestone_counts(),
            "career": milestone_counts(),
        },
        "gameLog": {
            "season": "2025-26",
            "entries": [log_entry("2026-01-12"), log_entry("2026-01-10")],
        },
        "awards": [{"name": "All-Star", "count": 2, "seasons": ["2025-26", "2024-25"]}],
    }


def rejects(player: Payload, match: str | None = None) -> None:
    with pytest.raises(ValidationError, match=match):
        PlayerFeed.model_validate(player)


def test_accepts_a_player_with_every_section() -> None:
    PlayerFeed.model_validate(valid_player())


def test_accepts_a_player_with_every_nullable_field_null() -> None:
    player = valid_player()
    for name in NULLABLE_SECTIONS:
        player[name] = None
    player["profile"] = {}
    player["lastGames"] = []
    player["awards"] = []
    player["averages"] = {}
    player["seasons"]["regular"] = {"perGame": [], "totals": [], "career": None}

    PlayerFeed.model_validate(player)


@pytest.mark.parametrize("name", NULLABLE_SECTIONS)
def test_serializes_absent_nullable_fields_as_null(name: str) -> None:
    player = valid_player()
    del player[name]

    dumped = PlayerFeed.model_validate(player).model_dump(mode="json")

    assert dumped[name] is None


def test_serializes_camel_case_keys() -> None:
    dumped = PlayerFeed.model_validate(valid_player()).model_dump(mode="json")

    assert dumped["profile"]["debutSeason"] == "2024-25"
    assert dumped["lastGames"][0]["fieldGoalPct"] == 0.533
    assert dumped["lastGames"][0]["detailAvailable"] is True
    assert dumped["nextGame"]["startTime"] == "2026-01-15T00:30:00Z"


@pytest.mark.parametrize("kind", ["cup", "playoffs", "allstar"])
def test_accepts_a_game_tag_with_an_unrecognized_note_as_its_kind_alone(
    kind: str,
) -> None:
    tag = GameTag.model_validate({"kind": kind})

    assert tag.kind == kind
    assert (tag.conference, tag.round, tag.game) == (None, None, None)
    assert tag.model_dump(mode="json") == {
        "kind": kind,
        "conference": None,
        "round": None,
        "game": None,
    }


@pytest.mark.parametrize("round_", [0, 5])
def test_rejects_a_game_tag_round_outside_one_to_four(round_: int) -> None:
    player = valid_player()
    player["nextGame"]["tag"]["round"] = round_

    rejects(player)


def test_rejects_an_unknown_game_tag_kind() -> None:
    player = valid_player()
    player["nextGame"]["tag"]["kind"] = "finals"

    rejects(player)


def test_accepts_a_live_block_without_a_box_score_line() -> None:
    player = valid_player()
    player["live"]["line"] = None

    PlayerFeed.model_validate(player)


def test_rejects_a_live_line_of_another_player() -> None:
    player = valid_player()
    player["live"]["line"]["playerId"] = "p2"

    rejects(player, "live line")


@pytest.mark.parametrize("value", [-0.1, 1.1])
@pytest.mark.parametrize(
    "path",
    [
        ("summary", "fieldGoalPct", "value"),
        ("averages", "career", "fieldGoalPct"),
        ("seasons", "regular", "perGame", 0, "freeThrowPct"),
        ("lastGames", 0, "threePointPct"),
    ],
)
def test_rejects_a_percentage_outside_zero_to_one(
    path: tuple[str | int, ...], value: float
) -> None:
    player = valid_player()
    target: Any = player
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    rejects(player)


@pytest.mark.parametrize(
    "path",
    [
        ("lastGames", 0, "points"),
        ("seasons", "regular", "perGame", 0, "assists"),
        ("milestones", "current", "technicals"),
        ("live", "teamScore"),
    ],
)
def test_rejects_a_negative_stat(path: tuple[str | int, ...]) -> None:
    player = valid_player()
    target: Any = player
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = -1

    rejects(player)


def test_rejects_more_than_five_last_games() -> None:
    player = valid_player()
    player["lastGames"] = [log_entry(f"2026-01-{20 - i:02d}") for i in range(6)]

    rejects(player)


def test_accepts_five_last_games_on_the_same_date() -> None:
    player = valid_player()
    player["lastGames"] = [log_entry("2026-01-12") for _ in range(5)]

    PlayerFeed.model_validate(player)


def test_rejects_last_games_not_newest_first() -> None:
    player = valid_player()
    player["lastGames"] = [log_entry("2026-01-10"), log_entry("2026-01-12")]

    rejects(player, "newest first")


def test_rejects_an_all_star_game_in_last_games() -> None:
    player = valid_player()
    player["lastGames"] = [log_entry("2026-01-12", kind="allstar")]

    rejects(player, "All-Star")


@pytest.mark.parametrize("list_name", ["perGame", "totals"])
def test_rejects_season_rows_not_newest_first(list_name: str) -> None:
    player = valid_player()
    player["seasons"]["regular"][list_name].reverse()

    rejects(player, "newest first")


def test_rejects_a_repeated_season_row() -> None:
    player = valid_player()
    player["seasons"]["regular"]["perGame"][1]["season"] = "2025-26"
    player["profile"]["debutSeason"] = "2025-26"

    rejects(player, "newest first")


def test_rejects_game_log_entries_not_newest_first() -> None:
    player = valid_player()
    player["gameLog"]["entries"].reverse()

    rejects(player, "newest first")


def test_accepts_game_log_entries_on_the_same_date() -> None:
    player = valid_player()
    player["gameLog"]["entries"] = [log_entry("2026-01-12"), log_entry("2026-01-12")]

    PlayerFeed.model_validate(player)


def test_rejects_a_null_opponent_outside_an_all_star_game() -> None:
    player = valid_player()
    player["gameLog"]["entries"][0]["opponent"] = None

    rejects(player, "null opponent")


def test_accepts_an_all_star_entry_with_a_null_opponent() -> None:
    player = valid_player()
    entry = log_entry("2026-01-12", kind="allstar")
    entry["opponent"] = None
    player["gameLog"]["entries"] = [entry]

    PlayerFeed.model_validate(player)


def test_rejects_a_totals_row_with_minutes() -> None:
    player = valid_player()
    player["seasons"]["regular"]["totals"][0]["minutes"] = 100.0
    rejects(player, "minutes")

    player = valid_player()
    player["seasons"]["regular"]["career"]["totals"]["minutes"] = 100.0
    rejects(player, "minutes")


def test_rejects_a_per_game_row_without_minutes() -> None:
    player = valid_player()
    player["seasons"]["regular"]["perGame"][0]["minutes"] = None
    rejects(player, "minutes")

    player = valid_player()
    player["seasons"]["regular"]["career"]["perGame"]["minutes"] = None
    rejects(player, "minutes")


@pytest.mark.parametrize("kind", ["fieldGoals", "threePoints", "freeThrows"])
def test_rejects_made_above_attempted(kind: str) -> None:
    player = valid_player()
    row = player["seasons"]["regular"]["perGame"][0]
    row[f"{kind}Made"] = row[f"{kind}Attempted"] + 1
    rejects(player, "attempted")

    player = valid_player()
    entry = player["gameLog"]["entries"][0]
    entry[f"{kind}Made"] = entry[f"{kind}Attempted"] + 1
    rejects(player, "attempted")


def test_rejects_a_debut_season_that_is_not_the_oldest_regular_season() -> None:
    player = valid_player()
    player["profile"]["debutSeason"] = "2025-26"

    rejects(player, "debutSeason")


def test_rejects_a_debut_season_without_regular_seasons() -> None:
    player = valid_player()
    player["seasons"]["regular"] = {"perGame": [], "totals": [], "career": None}
    player["profile"]["seasons"] = None

    rejects(player, "debutSeason")


def test_rejects_a_season_count_unlike_the_regular_seasons() -> None:
    player = valid_player()
    player["profile"]["seasons"] = 3

    rejects(player, "profile.seasons")


def test_accepts_an_unknown_season_count_and_debut() -> None:
    player = valid_player()
    player["profile"]["seasons"] = None
    player["profile"]["debutSeason"] = None

    PlayerFeed.model_validate(player)


def test_rejects_an_averages_row_with_no_games() -> None:
    player = valid_player()
    player["averages"]["career"]["gamesPlayed"] = 0

    rejects(player)


def test_rejects_a_season_label_not_like_2025_26() -> None:
    player = valid_player()
    player["summary"]["season"] = "2025-2026"

    rejects(player)


def test_rejects_an_injury_update_not_in_utc() -> None:
    player = valid_player()
    player["injury"]["updatedAt"] = "2026-01-14T10:00:00+02:00"

    rejects(player, "UTC")


def test_rejects_an_unknown_injury_status() -> None:
    player = valid_player()
    player["injury"]["status"] = "sidelined"

    rejects(player)


def test_rejects_unknown_fields() -> None:
    player = valid_player()
    player["extra"] = 1
    rejects(player)

    player = valid_player()
    player["profile"]["extra"] = 1
    rejects(player)

    player = copy.deepcopy(valid_player())
    player["lastGames"][0]["extra"] = 1
    rejects(player)
