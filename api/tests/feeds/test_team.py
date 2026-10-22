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
# - The stored names carry a build version, zero is rejected and a list without it reads as null (ADR 0055)
# - Accepts titles in kind order, rejects an empty list, a repeated kind, a conference title without a conference or with a year and a championship title without a year, and reads a stored feed without the key as null titles
# - Accepts a Cup mark with the group, wins and losses and a null or absent one, and rejects an unknown group letter, a missing record and a negative count
# - Accepts names runs and rejects runs not oldest first, an open run before the last and an end before its start; serializes from as the key; reads a stored feed without names as empty
# - Accepts a division rank of 8 and rejects 9
# - TeamFeed rejects null injuries and accepts a null arena, a null secondary color, and a null home, away, points or differential in the record; the stored names read as complete without the flag
# - TeamFeed rejects null colors and null injuries; PastTeamFeed accepts every past block null, rejects each one when set, and has the team schema apart from its title
# - A feed with a build version is accepted, one with zero is rejected, and a stored feed without the field reads with a null version
# - A team feed accepts a logo and a historical team feed with a logo is rejected (ADR 0068)
# - A past team feed carries a season code and the historical flag; historical without a season code is rejected; a stored feed without the fields reads as not historical (ADR 0054)
# - A past team feed accepts null colors, leaders and roster (ADR 0059); the current feed rejects each one null
# - A leader with a null position is accepted
#
# What is covered:
# - A valid feed is accepted and an invalid one is rejected
# - Happy path, edge cases (null optionals, equal numbers) and error cases of
#   each validator
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_team.py
#
# SEE: api/app/feeds/team.py

import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.schema import SCHEMA_DIR, render_schema
from app.feeds.team import NameRun, PastTeamFeed, TeamFeed, TeamNames

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


CUP = {"group": {"conference": "west", "letter": "B"}, "wins": 3, "losses": 1}


def test_accepts_a_team_with_a_cup_mark() -> None:
    feed = TeamFeed.model_validate({**valid_team(), "cup": CUP})

    assert feed.cup is not None
    assert (feed.cup.group.letter, feed.cup.wins, feed.cup.losses) == ("B", 3, 1)
    assert feed.model_dump(mode="json")["cup"] == CUP


def test_reads_a_team_without_a_cup_mark_as_null() -> None:
    absent = TeamFeed.model_validate(valid_team())
    explicit = TeamFeed.model_validate({**valid_team(), "cup": None})

    assert absent.cup is None and explicit.cup is None
    assert absent.model_dump(mode="json")["cup"] is None


@pytest.mark.parametrize(
    "cup",
    [
        {**CUP, "group": {"conference": "west", "letter": "D"}},
        {**CUP, "group": {"conference": "north", "letter": "A"}},
        {"group": CUP["group"], "wins": 3},
        {**CUP, "losses": -1},
    ],
    ids=["letter", "conference", "missing losses", "negative"],
)
def test_rejects_an_invalid_cup_mark(cup: Payload) -> None:
    rejects({**valid_team(), "cup": cup})


CHAMPIONS = {"kind": "nba_champions", "year": 2027, "conference": None}
CUP_CHAMPIONS = {"kind": "nba_cup_champions", "year": 2026, "conference": None}
CONFERENCE = {"kind": "conference_champions", "year": None, "conference": "west"}


def test_accepts_titles_in_kind_order() -> None:
    titles = [CHAMPIONS, CUP_CHAMPIONS, CONFERENCE]

    feed = TeamFeed.model_validate({**valid_team(), "titles": titles})

    assert feed.titles is not None and len(feed.titles) == 3
    assert feed.model_dump(mode="json")["titles"] == titles
    single = TeamFeed.model_validate({**valid_team(), "titles": [CONFERENCE]})
    assert single.titles is not None and len(single.titles) == 1


def test_rejects_an_empty_title_list() -> None:
    rejects({**valid_team(), "titles": []}, "titles")


def test_rejects_a_repeated_title_kind() -> None:
    rejects({**valid_team(), "titles": [CHAMPIONS, CHAMPIONS]}, "titles")
    rejects({**valid_team(), "titles": [CONFERENCE, CHAMPIONS]}, "titles")


@pytest.mark.parametrize(
    "title",
    [
        {**CONFERENCE, "conference": None},
        {**CONFERENCE, "year": 2027},
        {**CHAMPIONS, "conference": "east"},
    ],
)
def test_rejects_a_conference_title_without_a_conference_or_with_a_year(
    title: dict[str, Any],
) -> None:
    rejects({**valid_team(), "titles": [title]}, "titles")


def test_rejects_a_championship_title_without_a_year() -> None:
    rejects({**valid_team(), "titles": [{**CUP_CHAMPIONS, "year": None}]}, "titles")


def test_reads_a_stored_team_feed_without_the_key_as_titles_null() -> None:
    absent = TeamFeed.model_validate(valid_team())
    explicit = TeamFeed.model_validate({**valid_team(), "titles": None})

    assert absent.titles is None and explicit.titles is None
    assert absent.model_dump(mode="json")["titles"] is None


def run(start: int, end: int | None, code: str = "AAA") -> Payload:
    return {
        "from": start,
        "to": end,
        "name": "Name",
        "location": "City",
        "code": code,
    }


def test_accepts_names_runs_oldest_first_with_the_last_open() -> None:
    team = TeamFeed.model_validate(
        {**valid_team(), "names": [run(1994, 2000, "OLD"), run(2002, None)]}
    )

    assert [(r.from_, r.to) for r in team.names] == [(1994, 2000), (2002, None)]


@pytest.mark.parametrize(
    "names",
    [
        [run(2002, 2004), run(1994, 2000)],
        [run(1994, None), run(2002, None)],
        [run(1994, 2002), run(2002, None)],
        [run(1994, 2003), run(2000, None)],
    ],
    ids=["not oldest first", "open before the last", "touching", "overlapping"],
)
def test_rejects_names_runs_out_of_order_or_open_before_the_last(
    names: list[Payload],
) -> None:
    rejects({**valid_team(), "names": names})


def test_rejects_a_run_that_ends_before_it_starts_or_starts_before_1994() -> None:
    with pytest.raises(ValidationError):
        NameRun.model_validate(run(2005, 2004))
    with pytest.raises(ValidationError):
        NameRun.model_validate(run(1993, None))


def test_serializes_a_name_run_start_as_the_from_key() -> None:
    dumped = TeamNames.model_validate({"runs": [run(1994, None)]}).model_dump(
        mode="json"
    )

    assert dumped == {
        "runs": [run(1994, None)],
        "buildVersion": None,
        "complete": True,
        "missing": [],
    }


def test_the_stored_names_carry_a_build_version_and_reject_zero() -> None:
    versioned = TeamNames.model_validate({"runs": [run(1994, None)], "buildVersion": 3})

    assert versioned.build_version == 3
    with pytest.raises(ValidationError):
        TeamNames.model_validate({"runs": [run(1994, None)], "buildVersion": 0})


def test_reads_a_stored_team_feed_without_names_as_empty() -> None:
    absent = TeamFeed.model_validate(valid_team())

    assert absent.names == []
    assert absent.model_dump(mode="json")["names"] == []


@pytest.mark.parametrize(("rank", "valid"), [(8, True), (9, False), (0, False)])
def test_accepts_a_division_rank_of_8_and_rejects_9(rank: int, valid: bool) -> None:
    team = valid_team()
    team["record"]["divisionRank"] = rank

    if valid:
        TeamFeed.model_validate(team)
    else:
        rejects(team)


def test_rejects_null_injuries_on_the_current_feed() -> None:
    rejects({**valid_team(), "injuries": None}, "current season")


def test_accepts_a_null_arena_on_the_current_feed() -> None:
    assert TeamFeed.model_validate({**valid_team(), "arena": None}).arena is None


def test_accepts_a_null_secondary_color_but_rejects_null_colors_on_the_current_feed() -> (
    None
):
    team = valid_team()
    team["colors"]["secondary"] = None

    assert TeamFeed.model_validate(team).colors is not None
    rejects({**valid_team(), "colors": None}, "current season")


@pytest.mark.parametrize(
    "field", ["home", "away", "pointsFor", "pointsAgainst", "differential"]
)
def test_accepts_a_record_with_a_null_split_points_or_differential(field: str) -> None:
    team = valid_team()
    team["record"][field] = None

    assert TeamFeed.model_validate(team).record is not None


def test_the_stored_names_without_a_complete_flag_read_as_complete() -> None:
    names = TeamNames.model_validate({"runs": [run(1994, None)]})

    assert names.complete is True
    assert (
        TeamNames.model_validate(
            {"runs": [run(1994, None)], "complete": False}
        ).complete
        is False
    )


def past_team() -> Payload:
    team = valid_team()
    for name in PAST_NULL_BLOCKS:
        team[name] = None
    team["record"]["playoff"] = None
    return team


PAST_NULL_BLOCKS = ["arena", "coach", "injuries", "nextGame", "cup", "titles"]


def test_accepts_a_past_team_with_every_past_block_null() -> None:
    team = past_team()
    team["schedule"]["groups"][1]["games"][0] = schedule_game(
        "g2", "2026-01-15T00:30:00Z"
    )
    team["schedule"]["groups"][1]["games"][0]["isNext"] = False

    PastTeamFeed.model_validate(team)


def test_a_past_feed_accepts_null_colors_leaders_and_roster() -> None:
    team = past_team()
    team["schedule"]["groups"][1]["games"][0] = schedule_game(
        "g2", "2026-01-15T00:30:00Z"
    )
    team["schedule"]["groups"][1]["games"][0]["isNext"] = False
    team.update({"colors": None, "leaders": None, "roster": None})

    feed = PastTeamFeed.model_validate(team)

    assert (feed.colors, feed.leaders, feed.roster) == (None, None, None)


@pytest.mark.parametrize("name", ["colors", "leaders", "roster"])
def test_a_current_feed_rejects_null_colors_leaders_or_roster(name: str) -> None:
    rejects({**valid_team(), name: None}, "colors, leaders and a roster")


@pytest.mark.parametrize("name", PAST_NULL_BLOCKS)
def test_rejects_a_past_team_with_a_current_season_block(name: str) -> None:
    team = past_team()
    team[name] = {**valid_team(), "cup": CUP, "titles": [CUP_CHAMPIONS]}[name]

    with pytest.raises(ValidationError, match=f"a past season has no {name}"):
        PastTeamFeed.model_validate(team)


def test_the_past_team_schema_equals_the_team_schema_apart_from_its_title() -> None:
    past = json.loads(render_schema(PastTeamFeed))
    committed = json.loads(
        (SCHEMA_DIR / "team.schema.json").read_text(encoding="utf-8")
    )

    del past["title"]
    del committed["title"]
    assert past == committed


def test_accepts_a_build_version_and_rejects_zero_and_reads_none_as_null() -> None:
    stored = valid_team()
    assert TeamFeed.model_validate(stored).build_version is None

    assert TeamFeed.model_validate({**stored, "buildVersion": 1}).build_version == 1
    with pytest.raises(ValidationError):
        TeamFeed.model_validate({**stored, "buildVersion": 0})


def test_accepts_a_leader_with_a_null_position() -> None:
    team = valid_team()
    team["leaders"]["points"]["position"] = None

    leaders = TeamFeed.model_validate(team).leaders
    assert leaders is not None
    assert leaders.points is not None
    assert leaders.points.position is None


def test_accepts_a_team_feed_with_a_season_code_and_the_historical_flag() -> None:
    team = valid_team()
    team.update({"seasonCode": "SEA", "historical": True})

    parsed = TeamFeed.model_validate(team)

    assert (parsed.season_code, parsed.historical) == ("SEA", True)


def test_rejects_a_historical_team_feed_without_a_season_code() -> None:
    team = valid_team()
    team["historical"] = True

    rejects(team, "season code")


def test_a_stored_team_feed_without_the_fields_still_validates() -> None:
    parsed = TeamFeed.model_validate(valid_team())

    assert (parsed.season_code, parsed.historical) == (None, False)


def test_accepts_a_team_feed_with_a_logo_and_rejects_a_historical_one() -> None:
    team = valid_team()
    team["logo"] = {"light": "https://example.com/a.svg", "dark": None}

    assert TeamFeed.model_validate(team).logo is not None

    team.update({"seasonCode": "SEA", "historical": True})
    rejects(team, "no logo")
