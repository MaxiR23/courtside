# api/tests/feeds/test_team.py
#
# Tests for the team feed models.
#
# Tested:
# - A team with every section is accepted; nullable sections and fields may be
#   null and are serialized as null
# - A record carries a season label and may have null games behind
# - A coach without seasons is accepted and serialized with null seasons
# - Roster status is active or an injury status
# - Win percentages are 0 to 1 and counts are not negative
# - The playoff seed matches its status
# - The roster is ordered by number, unnumbered players last, 00 after 0
# - The schedule: the default group is a group, at most one game is next, and
#   the next game agrees with nextGame
# - Hex colors, group keys, UTC time and unknown fields are validated
# - A schedule game or the next game may be against a guest opponent, with or without a code
# - Serialization uses camelCase keys
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (null optionals, equal numbers) and error cases of
#   each validator
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_team.py
#
# SEE: api/app/feeds/team.py

from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.team import TeamFeed

Payload = dict[str, Any]

NULLABLE_PATHS = [
    ("coach",),
    ("coach", "seasons"),
    ("nextGame",),
    ("schedule",),
    ("record", "streak"),
    ("record", "playoff"),
    ("record", "gamesBehind"),
    ("leaders", "points"),
]


def opponent(code: str | None, **overrides: object) -> Payload:
    return {"code": code, "name": None, "city": None, "guest": False, **overrides}


def split(wins: int, losses: int) -> Payload:
    return {"wins": wins, "losses": losses, "winPct": 0.6}


def record() -> Payload:
    return {
        **split(30, 20),
        "season": "2025-26",
        "home": split(18, 7),
        "away": split(12, 13),
        "lastTen": split(6, 4),
        "streak": {"kind": "win", "count": 2},
        "gamesBehind": 1.5,
        "conferenceRank": 4,
        "divisionRank": 2,
        "playoff": {"status": "seed", "seed": 4},
        "pointsFor": {"perGame": 112.5, "total": 5625},
        "pointsAgainst": {"perGame": 108.1, "total": 5405},
        "differential": {"perGame": 4.4, "total": 220},
    }


def next_game(game_id: str) -> Payload:
    return {
        "gameId": game_id,
        "startTime": "2026-01-15T00:30:00Z",
        "opponent": opponent("BBB"),
        "isHome": True,
        "tag": None,
        "arena": "Arena",
        "city": None,
        "broadcast": None,
        "detailAvailable": False,
    }


def schedule_game(game_id: str, start: str, is_next: bool = False) -> Payload:
    return {
        "gameId": game_id,
        "startTime": start,
        "opponent": opponent("BBB"),
        "isHome": True,
        "kind": "regular",
        "tag": {"kind": "cup"},
        "result": None if is_next else "win",
        "teamScore": None if is_next else 100,
        "opponentScore": None if is_next else 90,
        "broadcast": None,
        "isNext": is_next,
        "detailAvailable": not is_next,
    }


def roster_player(player_id: str, number: str | None) -> Payload:
    return {
        "id": player_id,
        "name": "First Last",
        "number": number,
        "position": "G",
        "height": "6-5",
        "weight": 210,
        "age": 25,
        "birthDate": "2000-02-03",
        "birthplace": "Town",
        "college": "College",
        "experience": 0,
        "photoUrl": "https://example.com/photo.png",
        "status": "active",
    }


def leader() -> Payload:
    return {
        "playerId": "p1",
        "name": "First Last",
        "number": "7",
        "position": "G",
        "photoUrl": None,
        "value": 25.5,
    }


def valid_team() -> Payload:
    return {
        "code": "AAA",
        "city": "City",
        "name": "Name",
        "conference": "east",
        "division": "Atlantic",
        "colors": {"primary": "#112233", "secondary": "#aabbcc"},
        "arena": {"name": "Arena", "city": None, "photoUrl": None},
        "coach": {"name": "Coach", "seasons": 3},
        "season": "2026-27",
        "record": record(),
        "leaders": {
            "season": "2026-27",
            "points": leader(),
            "rebounds": None,
            "assists": leader(),
        },
        "roster": [
            roster_player("p1", "0"),
            roster_player("p2", "00"),
            roster_player("p3", "7"),
            roster_player("p4", None),
        ],
        "injuries": [
            {
                "playerId": "p1",
                "name": "First Last",
                "number": None,
                "position": None,
                "status": "out",
                "comment": None,
                "updatedAt": "2026-01-14T10:00:00Z",
            }
        ],
        "nextGame": next_game("g2"),
        "schedule": {
            "groups": [
                {
                    "key": "2025-12",
                    "games": [schedule_game("g1", "2025-12-30T00:30:00Z")],
                },
                {
                    "key": "2026-01",
                    "games": [schedule_game("g2", "2026-01-15T00:30:00Z", True)],
                },
                {
                    "key": "playoffs",
                    "games": [schedule_game("g3", "2026-04-20T00:30:00Z")],
                },
            ],
            "defaultGroup": "2026-01",
        },
    }


def rejects(team: Payload, match: str | None = None) -> None:
    with pytest.raises(ValidationError, match=match):
        TeamFeed.model_validate(team)


def test_accepts_a_team_with_every_section() -> None:
    TeamFeed.model_validate(valid_team())


@pytest.mark.parametrize("season", ["2025", "2025-2026", ""])
def test_rejects_a_record_season_that_is_not_a_label(season: str) -> None:
    team = valid_team()
    team["record"]["season"] = season

    rejects(team)


def test_rejects_a_record_without_a_season() -> None:
    team = valid_team()
    del team["record"]["season"]

    rejects(team, "season")


@pytest.mark.parametrize("path", NULLABLE_PATHS, ids=lambda p: ".".join(p))
def test_serializes_absent_nullable_fields_as_null(path: tuple[str, ...]) -> None:
    team = valid_team()
    if path == ("schedule",):
        team["nextGame"] = None
    target = team
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]
    if path == ("nextGame",):
        for group in team["schedule"]["groups"]:
            for game in group["games"]:
                game["isNext"] = False

    dumped = TeamFeed.model_validate(team).model_dump(mode="json")

    for key in path:
        dumped = dumped[key]
    assert dumped is None


def test_serializes_camel_case_keys() -> None:
    dumped = TeamFeed.model_validate(valid_team()).model_dump(mode="json")

    assert dumped["record"]["winPct"] == 0.6
    assert dumped["record"]["lastTen"]["winPct"] == 0.6
    assert dumped["schedule"]["defaultGroup"] == "2026-01"
    assert dumped["schedule"]["groups"][1]["games"][0]["isNext"] is True


@pytest.mark.parametrize(
    "status", ["active", "out", "doubtful", "questionable", "probable", "day-to-day"]
)
def test_accepts_an_active_or_injury_roster_status(status: str) -> None:
    team = valid_team()
    team["roster"][0]["status"] = status

    TeamFeed.model_validate(team)


def test_rejects_an_unknown_roster_status() -> None:
    team = valid_team()
    team["roster"][0]["status"] = "retired"

    rejects(team)


@pytest.mark.parametrize("value", [-0.1, 1.1])
@pytest.mark.parametrize("path", [("record",), ("record", "home")])
def test_rejects_a_win_pct_outside_zero_to_one(
    path: tuple[str, ...], value: float
) -> None:
    team = valid_team()
    target = team
    for key in path:
        target = target[key]
    target["winPct"] = value

    rejects(team)


@pytest.mark.parametrize(
    "path",
    [
        ("record", "wins"),
        ("record", "pointsFor", "total"),
        ("coach", "seasons"),
    ],
)
def test_rejects_a_negative_count(path: tuple[str, ...]) -> None:
    team = valid_team()
    target = team
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = -1

    rejects(team)


@pytest.mark.parametrize(
    ("status", "seed"),
    [("seed", 1), ("seed", 6), ("playin", 7), ("playin", 10), ("out", 11), ("out", 15)],
)
def test_accepts_a_seed_of_each_status(status: str, seed: int) -> None:
    team = valid_team()
    team["record"]["playoff"] = {"status": status, "seed": seed}

    TeamFeed.model_validate(team)


@pytest.mark.parametrize(
    ("status", "seed"),
    [("seed", 7), ("playin", 6), ("playin", 11), ("out", 10), ("seed", 0), ("out", 16)],
)
def test_rejects_a_seed_unlike_its_status(status: str, seed: int) -> None:
    team = valid_team()
    team["record"]["playoff"] = {"status": status, "seed": seed}

    rejects(team)


def test_rejects_a_roster_not_ordered_by_number() -> None:
    team = valid_team()
    team["roster"] = [roster_player("p1", "10"), roster_player("p2", "9")]

    rejects(team, "ordered by number")


def test_accepts_a_roster_with_unnumbered_players_last() -> None:
    team = valid_team()
    team["roster"] = [
        roster_player("p1", "3"),
        roster_player("p2", "3"),
        roster_player("p3", None),
        roster_player("p4", None),
    ]

    TeamFeed.model_validate(team)


def test_rejects_an_unnumbered_player_before_a_numbered_one() -> None:
    team = valid_team()
    team["roster"] = [roster_player("p1", None), roster_player("p2", "3")]

    rejects(team, "ordered by number")


def test_accepts_number_00_after_0() -> None:
    team = valid_team()
    team["roster"] = [roster_player("p1", "0"), roster_player("p2", "00")]

    TeamFeed.model_validate(team)


def test_rejects_a_default_group_that_is_not_a_group() -> None:
    team = valid_team()
    team["schedule"]["defaultGroup"] = "2027-01"

    rejects(team, "default group")


def test_rejects_more_than_one_next_game() -> None:
    team = valid_team()
    team["schedule"]["groups"][2]["games"][0]["isNext"] = True

    rejects(team, "at most one")


def test_rejects_a_next_game_unlike_the_is_next_game() -> None:
    team = valid_team()
    team["nextGame"] = next_game("g9")

    rejects(team, "next game")


def test_rejects_an_is_next_game_without_a_next_game() -> None:
    team = valid_team()
    team["nextGame"] = None

    rejects(team, "next game")


def test_rejects_a_next_game_without_an_is_next_game() -> None:
    team = valid_team()
    team["schedule"]["groups"][1]["games"][0]["isNext"] = False

    rejects(team, "next game")


def test_accepts_a_next_game_without_a_schedule() -> None:
    team = valid_team()
    team["schedule"] = None

    TeamFeed.model_validate(team)


def test_rejects_a_bad_hex_color() -> None:
    team = valid_team()
    team["colors"]["primary"] = "#12345"

    rejects(team)


def test_rejects_a_group_key_that_is_not_a_month_or_playoffs() -> None:
    team = valid_team()
    team["schedule"]["groups"][0]["key"] = "december"

    rejects(team)


def test_rejects_a_start_time_not_in_utc() -> None:
    team = valid_team()
    team["schedule"]["groups"][0]["games"][0]["startTime"] = "2025-12-30T00:30:00+01:00"

    rejects(team, "UTC")


def test_rejects_unknown_fields() -> None:
    team = valid_team()
    team["extra"] = 1
    rejects(team)

    team = valid_team()
    team["roster"][0]["extra"] = 1
    rejects(team)


def test_accepts_a_coach_with_null_seasons() -> None:
    team = valid_team()
    team["coach"]["seasons"] = None

    dumped = TeamFeed.model_validate(team).model_dump(mode="json", by_alias=True)

    assert dumped["coach"]["seasons"] is None


GUEST = {"code": None, "name": "Mariners", "city": "Harbor City", "guest": True}


def test_accepts_a_schedule_game_against_a_guest_opponent_without_a_code() -> None:
    team = valid_team()
    team["schedule"]["groups"][0]["games"][0]["opponent"] = GUEST

    feed = TeamFeed.model_validate(team)

    assert feed.schedule is not None
    assert feed.schedule.groups[0].games[0].opponent.code is None


def test_accepts_a_next_game_against_a_guest_opponent_with_a_code() -> None:
    team = valid_team()
    team["nextGame"]["opponent"] = {**GUEST, "code": "HCM"}

    feed = TeamFeed.model_validate(team)

    assert feed.next_game is not None and feed.next_game.opponent.code == "HCM"


def test_rejects_a_schedule_opponent_that_is_a_bare_code() -> None:
    team = valid_team()
    team["schedule"]["groups"][0]["games"][0]["opponent"] = "BBB"

    rejects(team, "opponent")
