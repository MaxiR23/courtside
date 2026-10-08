# api/tests/jobs/test_team_feed.py
#
# Tests for the team feed builder and the conversions the player feed builder
# shares.
#
# Tested:
# - Labels a season from its end year
# - Computes win percentages and gives 0 without games
# - Parses home, road and last ten records
# - Reads a win and a loss streak and gives none for a dash
# - Rejects a streak it cannot read
# - Maps seeds 1-6, 7-10 and 11-15 to their status and gives none before the first game
# - Ranks the conference by seed, and by entry order before the first game
# - Ranks the division by entry order
# - Tags every playoff round format, the NBA Finals, the cup and All-Star
# - Keeps the playoffs kind with null fields for an unrecognized playoff note
# - Gives a regular game with an unknown note no tag
# - Computes the age on the US Eastern date, with a birthday on the build day and the day after
# - Converts the roster details to text and numbers
# - Builds the roster status from the league injuries by athlete id
# - Matches each leader to the roster and gives null when the leader is no longer on it
# - Gives a null leader when the roster entry has no position
# - Labels the leaders with the previous season when it was used
# - Picks the first unplayed game as the next game and marks it in the schedule
# - Gives no next game and the last group as default when every game is played
# - Groups games by US Eastern month across the date boundary with the playoffs last
# - Gives no schedule without games
# - Sets detail availability from the detail ids
# - Lists only team injuries with an athlete id and a date, with the roster number and position
# - Orders the roster by number with unnumbered players last
# - Fails the build for a team with no standings entry and for an invalid feed
# - Builds a valid team feed from the recorded payloads
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_team_feed.py
#
# SEE: api/app/jobs/team_feed.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
import respx

from app.feeds.game_detail import Conference, GameResult, Injury, InjuryStatus
from app.feeds.player import GameKind, GameTag, TagKind
from app.feeds.team import PlayoffStatus, TeamFeed
from app.jobs.team_feed import (
    TeamBuildError,
    age_on,
    build_team_feed,
    conference_rank,
    eastern_month,
    game_kind_and_tag,
    games_behind,
    next_game,
    playoff_position,
    roster_status,
    schedule,
    season_label,
    split_record,
    streak,
    win_pct,
)
from app.settings import Settings
from app.sources.division_standings import (
    DivisionEntry,
    DivisionStandings,
    fetch_division_standings,
)
from app.sources.http import create_client
from app.sources.league_injuries import (
    InjuryReport,
    LeagueInjuries,
    fetch_league_injuries,
)
from app.sources.team_info import TeamInfo, fetch_team_info
from app.sources.team_players import (
    PlayerAverages,
    Roster,
    RosterCoach,
    RosterEntry,
    SeasonLeaders,
    fetch_roster,
    fetch_team_leaders,
)
from app.sources.team_schedule import (
    ScheduledGame,
    SeasonSchedule,
    fetch_season_schedule,
)
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent.parent / "sources" / "fixtures"
NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
START = dt.datetime(2026, 10, 21, 1, 30, tzinfo=dt.UTC)


def standing(code: str = "OKC", **changes: Any) -> DivisionEntry:
    values: dict[str, Any] = {
        "code": code,
        "location": "Oklahoma City",
        "name": "Thunder",
        "display_name": "Oklahoma City Thunder",
        "conference": Conference.WEST,
        "division": "Northwest",
        "division_order": 2,
        "conference_order": 4,
        "wins": 30,
        "losses": 10,
        "playoff_seed": 1,
        "streak": "W2",
        "games_behind": "-",
        "home": "18-3",
        "road": "12-7",
        "last_ten": "8-2",
        "avg_points_for": 118.04,
        "avg_points_against": 107.92,
        "points_for": 4722,
        "points_against": 4317,
        "differential": 10.1,
        "point_differential": 405,
    }
    return DivisionEntry.model_validate(values | changes)


def standings(entry: DivisionEntry | None = None) -> DivisionStandings:
    entry = entry or standing()
    return DivisionStandings(teams={entry.code: entry})


def info() -> TeamInfo:
    return TeamInfo(
        location="Oklahoma City",
        name="Thunder",
        color="007ac1",
        alternate_color="ef3b24",
        venue_name="Paycom Center",
        venue_city="Oklahoma City",
        venue_photo_url="https://example.com/venue.jpg",
    )


def player(player_id: str, jersey: str | None, **changes: Any) -> RosterEntry:
    values: dict[str, Any] = {
        "player_id": player_id,
        "first_name": "First" + player_id,
        "last_name": "Last" + player_id,
        "display_name": f"First{player_id} Last{player_id}",
        "jersey": jersey,
        "position_name": "Guard",
        "position_abbreviation": "G",
        "height_inches": 78.0,
        "display_height": "6' 6\"",
        "weight_lb": 195.4,
        "birth_date": dt.date(1998, 7, 12),
        "birth_city": "Toronto",
        "birth_state": "ON",
        "birth_country": "Canada",
        "college": "Kentucky",
        "experience": 9,
        "headshot_url": f"https://example.com/{player_id}.png",
    }
    return RosterEntry.model_validate(values | changes)


def roster(*entries: RosterEntry, coach: RosterCoach | None = None) -> Roster:
    entries = entries or (player("1", "2"),)
    return Roster.model_validate(
        {
            "season": 2027,
            "team_id": "25",
            "players": [
                {
                    "player_id": e.player_id,
                    "first_name": e.first_name,
                    "last_name": e.last_name,
                    "short_name": e.last_name,
                    "team_code": "OKC",
                    "photo_url": "https://example.com/p.png",
                }
                for e in entries
            ],
            "entries": entries,
            "coach": coach,
        }
    )


def leaders(
    *averages: tuple[str, float, float, float], season: int = 2026
) -> SeasonLeaders:
    return SeasonLeaders(
        season=season,
        players=[
            PlayerAverages(player_id=i, points=p, rebounds=r, assists=a)
            for i, p, r, a in averages
        ],
    )


def injuries(**teams: list[InjuryReport]) -> LeagueInjuries:
    return LeagueInjuries(teams=teams)


def report(
    player_id: str | None = "1",
    status: InjuryStatus = InjuryStatus.OUT,
    updated_at: dt.datetime | None = NOW,
    name: str = "Injured Player",
) -> InjuryReport:
    return InjuryReport(
        injury=Injury(display_name=name, status=status, comment="knee"),
        player_id=player_id,
        updated_at=updated_at,
    )


def game(game_id: str, start: dt.datetime = START, **changes: Any) -> ScheduledGame:
    values: dict[str, Any] = {
        "game_id": game_id,
        "start_time": start,
        "opponent": "SAS",
        "is_home": False,
        "state": "pre",
        "completed": False,
        "arena": "Frost Bank Center",
        "city": "San Antonio",
        "playoffs": False,
    }
    return ScheduledGame.model_validate(values | changes)


def played(game_id: str, start: dt.datetime, **changes: Any) -> ScheduledGame:
    return game(
        game_id,
        start,
        state="post",
        completed=True,
        won=True,
        team_score=110,
        opponent_score=100,
        **changes,
    )


def season(*games: ScheduledGame) -> SeasonSchedule:
    return SeasonSchedule(games=list(games))


EMPTY = season()


def build(
    *,
    entry: DivisionEntry | None = None,
    team_roster: Roster | None = None,
    season_leaders: SeasonLeaders | None = None,
    league: LeagueInjuries | None = None,
    regular: SeasonSchedule = EMPTY,
    playoffs: SeasonSchedule = EMPTY,
    detail_ids: frozenset[str] = frozenset(),
    now: dt.datetime = NOW,
) -> TeamFeed:
    return build_team_feed(
        "OKC",
        info(),
        standings(entry),
        team_roster or roster(),
        season_leaders or leaders(),
        league or injuries(),
        regular,
        playoffs,
        now=now,
        detail_ids=detail_ids,
    )


def test_labels_a_season_from_its_end_year() -> None:
    assert season_label(2026) == "2025-26"
    assert season_label(2000) == "1999-00"
    assert season_label(2010) == "2009-10"


def test_computes_win_percentages_and_gives_zero_without_games() -> None:
    assert win_pct(2, 1) == 0.667
    assert win_pct(56, 26) == 0.683
    assert win_pct(0, 0) == 0.0
    assert win_pct(0, 5) == 0.0


def test_parses_home_road_and_last_ten_records() -> None:
    record = split_record("30-11")

    assert (record.wins, record.losses, record.win_pct) == (30, 11, 0.732)
    assert split_record("0-0").win_pct == 0.0


@pytest.mark.parametrize("text", ["", "30", "30-", "a-b", "30-11-1", "-1-2"])
def test_rejects_a_record_it_cannot_read(text: str) -> None:
    with pytest.raises(TeamBuildError):
        split_record(text)


def test_reads_a_win_and_a_loss_streak_and_gives_none_for_a_dash() -> None:
    win = streak("W2")
    loss = streak("L11")

    assert win is not None
    assert (win.kind, win.count) == (GameResult.WIN, 2)
    assert loss is not None
    assert (loss.kind, loss.count) == (GameResult.LOSS, 11)
    assert streak("-") is None
    assert streak("") is None


@pytest.mark.parametrize("text", ["W", "W0", "X2", "2W", "w2", "W2 "])
def test_rejects_a_streak_it_cannot_read(text: str) -> None:
    with pytest.raises(TeamBuildError):
        streak(text)


def test_reads_games_behind_with_a_dash_for_the_leader() -> None:
    assert games_behind("-") == 0
    assert games_behind("1.5") == 1.5
    with pytest.raises(TeamBuildError):
        games_behind("one")


@pytest.mark.parametrize(
    ("seed", "status"),
    [
        (1, PlayoffStatus.SEED),
        (6, PlayoffStatus.SEED),
        (7, PlayoffStatus.PLAYIN),
        (10, PlayoffStatus.PLAYIN),
        (11, PlayoffStatus.OUT),
        (15, PlayoffStatus.OUT),
    ],
)
def test_maps_seeds_to_their_status(seed: int, status: PlayoffStatus) -> None:
    position = playoff_position(seed, 82)

    assert position is not None
    assert (position.status, position.seed) == (status, seed)


def test_gives_no_playoff_position_before_the_first_game() -> None:
    assert playoff_position(0, 0) is None


@pytest.mark.parametrize("seed", [0, 16, -1])
def test_rejects_a_seed_outside_one_to_fifteen_after_a_game(seed: int) -> None:
    with pytest.raises(TeamBuildError):
        playoff_position(seed, 1)


def test_ranks_the_conference_by_seed_and_by_entry_order_before_the_first_game() -> (
    None
):
    assert conference_rank(standing(playoff_seed=3, conference_order=9)) == 3
    assert conference_rank(standing(playoff_seed=0, conference_order=9)) == 9


def test_ranks_the_division_by_entry_order() -> None:
    feed = build(entry=standing(division_order=4))

    assert feed.record.division_rank == 4


def test_records_the_standing_with_converted_values() -> None:
    feed = build(entry=standing(games_behind="2.5", streak="L3"))

    record = feed.record
    assert (record.wins, record.losses, record.win_pct) == (30, 10, 0.75)
    assert record.home.win_pct == 0.857
    assert (record.away.wins, record.last_ten.wins) == (12, 8)
    assert record.streak is not None and record.streak.count == 3
    assert record.games_behind == 2.5
    assert (record.conference_rank, record.division_rank) == (1, 2)
    assert record.playoff is not None and record.playoff.seed == 1
    assert (record.points_for.per_game, record.points_for.total) == (118.0, 4722)
    assert (record.points_against.per_game, record.points_against.total) == (
        107.9,
        4317,
    )
    assert (record.differential.per_game, record.differential.total) == (10.1, 405)
    assert feed.colors.primary == "#007ac1"
    assert feed.colors.secondary == "#ef3b24"
    assert (feed.conference, feed.division) == (Conference.WEST, "Northwest")
    assert (feed.arena.name, feed.arena.city) == ("Paycom Center", "Oklahoma City")
    assert feed.season == "2026-27"


def test_builds_a_record_before_the_first_game() -> None:
    entry = standing(
        wins=0,
        losses=0,
        playoff_seed=0,
        conference_order=7,
        streak="-",
        games_behind="-",
        home="0-0",
        road="0-0",
        last_ten="0-0",
        avg_points_for=0,
        avg_points_against=0,
        points_for=0,
        points_against=0,
        differential=0,
        point_differential=0,
    )

    record = build(entry=entry).record

    assert record.playoff is None
    assert record.streak is None
    assert (record.win_pct, record.conference_rank) == (0.0, 7)


@pytest.mark.parametrize(
    ("note", "tag"),
    [
        (
            "West 1st Round - Game 7",
            GameTag(kind=TagKind.PLAYOFFS, conference=Conference.WEST, round=1, game=7),
        ),
        (
            "East Semifinals - Game 2",
            GameTag(kind=TagKind.PLAYOFFS, conference=Conference.EAST, round=2, game=2),
        ),
        (
            "West Finals - Game 4",
            GameTag(kind=TagKind.PLAYOFFS, conference=Conference.WEST, round=3, game=4),
        ),
        ("NBA Finals - Game 5", GameTag(kind=TagKind.PLAYOFFS, round=4, game=5)),
    ],
)
def test_tags_every_playoff_round_format_and_the_nba_finals(
    note: str, tag: GameTag
) -> None:
    assert game_kind_and_tag(note, True) == (GameKind.PLAYOFFS, tag)


def test_tags_the_cup_and_all_star_games() -> None:
    assert game_kind_and_tag("NBA Cup - Group Play", False) == (
        GameKind.CUP,
        GameTag(kind=TagKind.CUP),
    )
    assert game_kind_and_tag("NBA Cup - Semifinals", False) == (
        GameKind.CUP,
        GameTag(kind=TagKind.CUP),
    )
    assert game_kind_and_tag("NBA All-Star - Championship", False) == (
        GameKind.ALLSTAR,
        GameTag(kind=TagKind.ALLSTAR),
    )


@pytest.mark.parametrize("note", [None, "", "Round of 16", "West Finals - Game x"])
def test_keeps_the_playoffs_kind_with_null_fields_for_an_unrecognized_playoff_note(
    note: str | None,
) -> None:
    kind, tag = game_kind_and_tag(note, True)

    assert kind is GameKind.PLAYOFFS
    assert tag == GameTag(kind=TagKind.PLAYOFFS)
    assert (tag.conference, tag.round, tag.game) == (None, None, None)


@pytest.mark.parametrize("note", [None, "", "Rivalry Night", "West Finals - Game 4"])
def test_gives_a_regular_game_with_an_unknown_note_no_tag(note: str | None) -> None:
    assert game_kind_and_tag(note, False) == (GameKind.REGULAR, None)


def test_computes_ages_with_a_birthday_on_the_build_day_and_the_day_after() -> None:
    birth = dt.date(2000, 10, 8)

    assert age_on(birth, dt.date(2026, 10, 8)) == 26
    assert age_on(birth, dt.date(2026, 10, 7)) == 25
    assert age_on(dt.date(2000, 10, 9), dt.date(2026, 10, 8)) == 25


def test_converts_the_roster_details_and_ages_on_the_us_eastern_date() -> None:
    # 2026-10-09T02:00Z is still 2026-10-08 in New York.
    late = dt.datetime(2026, 10, 9, 2, 0, tzinfo=dt.UTC)
    teammate = player("1", "2", birth_date=dt.date(2000, 10, 9))

    feed = build(team_roster=roster(teammate), now=late)

    row = feed.roster[0]
    assert row.age == 25
    assert row.birth_date == dt.date(2000, 10, 9)
    assert (row.height, row.weight) == ("6' 6\"", 195)
    assert row.birthplace == "Toronto, ON"
    assert (row.college, row.experience) == ("Kentucky", 9)
    assert (row.position, row.number) == ("G", "2")
    assert str(row.photo_url) == "https://example.com/1.png"
    assert row.status == "active"


@pytest.mark.parametrize(
    ("changes", "text"),
    [
        ({"birth_state": None}, "Toronto, Canada"),
        ({"birth_state": None, "birth_country": None}, "Toronto"),
        ({"birth_city": None}, None),
    ],
)
def test_writes_the_birthplace_with_the_parts_the_provider_gave(
    changes: dict[str, Any], text: str | None
) -> None:
    feed = build(team_roster=roster(player("1", "2", **changes)))

    assert feed.roster[0].birthplace == text


def test_keeps_missing_roster_details_as_null() -> None:
    bare = player(
        "1",
        None,
        position_abbreviation=None,
        display_height=None,
        weight_lb=None,
        birth_date=None,
        college=None,
        experience=None,
        headshot_url=None,
        display_name=None,
    )

    row = build(team_roster=roster(bare)).roster[0]

    assert row.name == "First1 Last1"
    assert (row.number, row.position, row.height, row.weight) == (None,) * 4
    assert (row.age, row.birth_date, row.college, row.photo_url) == (None,) * 4


def test_builds_the_roster_status_from_the_league_injuries_by_athlete_id() -> None:
    league = injuries(
        BOS=[report("7", InjuryStatus.DOUBTFUL)],
        OKC=[report("1", InjuryStatus.OUT), report(None)],
    )

    assert roster_status("1", league) == InjuryStatus.OUT
    assert roster_status("7", league) == InjuryStatus.DOUBTFUL
    assert roster_status("9", league) == "active"
    feed = build(team_roster=roster(player("1", "2"), player("7", "3")), league=league)
    assert [row.status for row in feed.roster] == [
        InjuryStatus.OUT,
        InjuryStatus.DOUBTFUL,
    ]


def test_matches_each_leader_to_the_roster_and_gives_null_when_the_leader_left() -> (
    None
):
    team_roster = roster(player("1", "2"), player("2", "5", position_name="Forward"))
    averages = leaders(("9", 30.04, 3.0, 1.0), ("1", 20.0, 9.96, 5.0), ("2", 1, 9.0, 6))

    feed = build(team_roster=team_roster, season_leaders=averages)

    assert feed.leaders.points is None
    assert feed.leaders.rebounds is not None
    assert (feed.leaders.rebounds.player_id, feed.leaders.rebounds.value) == ("1", 10.0)
    assert feed.leaders.assists is not None
    assert feed.leaders.assists.player_id == "2"
    assert feed.leaders.assists.position == "Forward"
    assert feed.leaders.assists.number == "5"
    assert feed.leaders.assists.name == "First2 Last2"
    assert str(feed.leaders.assists.photo_url) == "https://example.com/2.png"


def test_gives_null_for_a_leader_without_a_position() -> None:
    team_roster = roster(
        player("1", "2", position_name=None, position_abbreviation=None)
    )

    feed = build(team_roster=team_roster, season_leaders=leaders(("1", 20.0, 1, 1)))

    assert feed.leaders.points is None


def test_picks_the_first_of_tied_leaders_in_list_order() -> None:
    team_roster = roster(player("1", "2"), player("2", "5"))

    feed = build(
        team_roster=team_roster,
        season_leaders=leaders(("2", 20.0, 1, 1), ("1", 20.0, 1, 1)),
    )

    assert feed.leaders.points is not None and feed.leaders.points.player_id == "2"


def test_labels_the_leaders_with_the_previous_season_when_it_was_used() -> None:
    feed = build(season_leaders=leaders(("1", 20.0, 1, 1), season=2026))

    assert feed.leaders.season == "2025-26"
    assert feed.season == "2026-27"


def test_gives_no_leaders_without_players() -> None:
    feed = build(season_leaders=leaders())

    assert (feed.leaders.points, feed.leaders.rebounds, feed.leaders.assists) == (
        None,
    ) * 3


def test_picks_the_first_unplayed_game_as_the_next_game_and_marks_it() -> None:
    first = played("1", START - dt.timedelta(days=3))
    soon = game("3", START, note="NBA Cup - Group Play", broadcast="NBC")
    later = game("2", START + dt.timedelta(days=2))
    final = game("4", START + dt.timedelta(days=60), playoffs=True)

    upcoming = next_game(season(first, later, soon), season(final), frozenset())

    assert upcoming is not None
    assert upcoming.game_id == "3"
    assert upcoming.tag == GameTag(kind=TagKind.CUP)
    assert (upcoming.arena, upcoming.city, upcoming.broadcast) == (
        "Frost Bank Center",
        "San Antonio",
        "NBC",
    )
    feed = build(regular=season(first, later, soon), playoffs=season(final))
    assert feed.next_game is not None and feed.next_game.game_id == "3"
    assert feed.schedule is not None
    flagged = [
        g.game_id for grp in feed.schedule.groups for g in grp.games if g.is_next
    ]
    assert flagged == ["3"]
    assert feed.schedule.default_group == "2026-10"


def test_finds_a_playoff_game_as_the_next_game_when_the_regular_season_is_over() -> (
    None
):
    done = played("1", START - dt.timedelta(days=3))
    series = game("2", START, playoffs=True, note="West 1st Round - Game 1")

    upcoming = next_game(season(done), season(series), frozenset())

    assert upcoming is not None
    assert upcoming.tag == GameTag(
        kind=TagKind.PLAYOFFS, conference=Conference.WEST, round=1, game=1
    )


def test_gives_no_next_game_and_the_last_group_as_default_when_every_game_is_played() -> (
    None
):
    first = played("1", dt.datetime(2026, 1, 5, 1, 0, tzinfo=dt.UTC))
    last = played("2", dt.datetime(2026, 4, 5, 1, 0, tzinfo=dt.UTC))
    feed = build(regular=season(first, last))

    assert feed.next_game is None
    assert feed.schedule is not None
    assert feed.schedule.default_group == "2026-04"
    assert [group.key for group in feed.schedule.groups] == ["2026-01", "2026-04"]
    result = feed.schedule.groups[0].games[0]
    assert (result.result, result.team_score, result.opponent_score) == (
        GameResult.WIN,
        110,
        100,
    )
    assert result.is_next is False


def test_groups_games_by_us_eastern_month_across_the_date_boundary_with_the_playoffs_last() -> (
    None
):
    # 2026-11-01T02:00Z is 2026-10-31 22:00 in New York.
    boundary = game("1", dt.datetime(2026, 11, 1, 2, 0, tzinfo=dt.UTC))
    november = game("2", dt.datetime(2026, 11, 1, 18, 0, tzinfo=dt.UTC))
    october = game("3", dt.datetime(2026, 10, 25, 18, 0, tzinfo=dt.UTC))
    series = game("4", dt.datetime(2027, 4, 20, 18, 0, tzinfo=dt.UTC), playoffs=True)
    lost = game(
        "5",
        dt.datetime(2027, 4, 22, 18, 0, tzinfo=dt.UTC),
        playoffs=True,
        note="Play-in",
    )

    grouped = schedule(
        season(november, boundary, october), season(lost, series), None, frozenset()
    )

    assert grouped is not None
    assert eastern_month(boundary.start_time) == "2026-10"
    assert [group.key for group in grouped.groups] == ["2026-10", "2026-11", "playoffs"]
    assert [g.game_id for g in grouped.groups[0].games] == ["3", "1"]
    assert [g.game_id for g in grouped.groups[2].games] == ["4", "5"]
    assert grouped.default_group == "playoffs"
    assert grouped.groups[2].games[0].kind is GameKind.PLAYOFFS
    assert grouped.groups[2].games[0].tag == GameTag(kind=TagKind.PLAYOFFS)


def test_gives_no_schedule_without_games() -> None:
    assert schedule(EMPTY, EMPTY, None, frozenset()) is None
    feed = build()
    assert (feed.schedule, feed.next_game) == (None, None)


def test_keeps_the_result_and_scores_of_an_unplayed_game_null() -> None:
    feed = build(regular=season(game("1")))

    assert feed.schedule is not None
    scheduled = feed.schedule.groups[0].games[0]
    assert (scheduled.result, scheduled.team_score, scheduled.opponent_score) == (
        None,
    ) * 3


def test_sets_detail_availability_from_the_detail_ids() -> None:
    regular = season(played("1", START - dt.timedelta(days=2)), game("2"))

    feed = build(regular=regular, detail_ids=frozenset({"1", "2"}))
    other = build(regular=regular, detail_ids=frozenset({"1"}))

    assert feed.next_game is not None and feed.next_game.detail_available is True
    assert other.next_game is not None and other.next_game.detail_available is False
    assert feed.schedule is not None and other.schedule is not None
    assert [g.detail_available for g in feed.schedule.groups[0].games] == [True, True]
    assert [g.detail_available for g in other.schedule.groups[0].games] == [True, False]


def test_lists_only_team_injuries_with_an_athlete_id_and_a_date() -> None:
    league = injuries(
        OKC=[
            report("1", InjuryStatus.OUT, name="On Roster"),
            report("77", InjuryStatus.PROBABLE, name="Off Roster"),
            report(None, name="No Id"),
            report("1", updated_at=None, name="No Date"),
        ],
        BOS=[report("5", name="Other Team")],
    )

    feed = build(team_roster=roster(player("1", "2")), league=league)

    assert [(i.player_id, i.name) for i in feed.injuries] == [
        ("1", "On Roster"),
        ("77", "Off Roster"),
    ]
    on_roster, off_roster = feed.injuries
    assert (on_roster.number, on_roster.position) == ("2", "Guard")
    assert (off_roster.number, off_roster.position) == (None, None)
    assert (on_roster.status, on_roster.comment, on_roster.updated_at) == (
        InjuryStatus.OUT,
        "knee",
        NOW,
    )


def test_orders_the_roster_by_number_with_unnumbered_players_last() -> None:
    feed = build(
        team_roster=roster(
            player("1", "23"), player("2", None), player("3", "5"), player("4", "0")
        )
    )

    assert [row.id for row in feed.roster] == ["4", "3", "1", "2"]


def test_rejects_a_jersey_number_that_is_not_a_number() -> None:
    with pytest.raises(TeamBuildError):
        build(team_roster=roster(player("1", "x"), player("2", "3")))


def test_maps_the_coach() -> None:
    coach = RosterCoach(first_name="Mark", last_name="Daigneault", experience=4)

    assert build(team_roster=roster(coach=coach)).coach is not None
    feed = build(team_roster=roster(coach=coach))
    assert feed.coach is not None
    assert (feed.coach.name, feed.coach.seasons) == ("Mark Daigneault", 4)
    assert build().coach is None


def test_fails_the_build_for_a_team_with_no_standings_entry() -> None:
    with pytest.raises(TeamBuildError) as raised:
        build_team_feed(
            "BOS",
            info(),
            standings(),
            roster(),
            leaders(),
            injuries(),
            EMPTY,
            EMPTY,
            now=NOW,
            detail_ids=frozenset(),
        )

    assert raised.value.reason == "team BOS has no standing"


def test_wraps_an_invalid_feed_in_a_build_error() -> None:
    with pytest.raises(TeamBuildError) as raised:
        build(entry=standing(division_order=6))

    assert raised.value.reason.startswith("invalid feed: 1 errors, first at record")


def test_fails_the_build_for_a_record_or_streak_it_cannot_read() -> None:
    with pytest.raises(TeamBuildError):
        build(entry=standing(home="n/a"))
    with pytest.raises(TeamBuildError):
        build(entry=standing(streak="W"))


def recorded(name: str, folder: str) -> Any:
    return json.loads((FIXTURES / folder / name).read_text(encoding="utf-8"))


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


@pytest.mark.anyio
@pytest.mark.parametrize("schedule_season", [2026, 2027])
async def test_builds_a_valid_team_feed_from_the_recorded_payloads(
    mock: respx.MockRouter, schedule_season: int
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        team_info_url="https://example.com/teams/{team}",
        division_standings_url="https://example.com/standings?level=3&seasontype=2",
        team_roster_url="https://example.com/teams/{team}/roster",
        player_photo_url="https://example.com/players/{player_id}.png",
        team_averages_url="https://example.com/seasons/{season}/teams/{team}/leaders",
        league_injuries_url="https://example.com/injuries",
        team_schedule_url="https://example.com/teams/{team}/schedule",
    )
    mock.get("https://example.com/teams/OKC").respond(
        json=recorded("okc.json", "team_info")
    )
    mock.get("https://example.com/standings?level=3&seasontype=2").respond(
        json=recorded("regular-2026.json", "division_standings")
    )
    mock.get("https://example.com/teams/OKC/roster").respond(
        json=recorded("roster-okc.json", "team_players")
    )
    mock.get("https://example.com/seasons/2027/teams/25/leaders").respond(
        status_code=404
    )
    mock.get("https://example.com/seasons/2026/teams/25/leaders").respond(
        json=recorded("averages-okc-2026.json", "team_players")
    )
    mock.get("https://example.com/injuries").respond(
        json=recorded("injuries-detail.json", "league_injuries")
    )
    regular_name = f"okc-{schedule_season}-regular.json"
    mock.get(
        f"https://example.com/teams/OKC/schedule?season={schedule_season}&seasontype=2"
    ).respond(json=recorded(regular_name, "team_schedule"))
    playoff_events = (
        recorded("okc-2026-playoffs.json", "team_schedule")
        if schedule_season == 2026
        else {"events": []}
    )
    mock.get(
        f"https://example.com/teams/OKC/schedule?season={schedule_season}&seasontype=3"
    ).respond(json=playoff_events)

    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            team_info = await fetch_team_info(client, "OKC", settings)
            division = await fetch_division_standings(client, settings)
            team_roster = await fetch_roster(client, "OKC", settings)
            season_leaders = await fetch_team_leaders(client, team_roster, settings)
            league = await fetch_league_injuries(client, settings)
            regular = await fetch_season_schedule(
                client, "OKC", schedule_season, settings, playoffs=False
            )
            playoffs = await fetch_season_schedule(
                client, "OKC", schedule_season, settings, playoffs=True
            )

    feed = build_team_feed(
        "OKC",
        team_info,
        division,
        team_roster,
        season_leaders,
        league,
        regular,
        playoffs,
        now=NOW,
        detail_ids=frozenset({"401809243"}),
    )

    dumped = feed.model_dump(mode="json")
    assert TeamFeed.model_validate(dumped) == feed
    assert (feed.code, feed.city, feed.name) == ("OKC", "Oklahoma City", "Thunder")
    assert feed.record.playoff is not None and feed.record.playoff.seed == 1
    assert feed.leaders.season == "2025-26"
    assert feed.leaders.points is not None
    assert feed.leaders.points.player_id == "4278073"
    assert feed.coach is not None and feed.coach.name == "Mark Daigneault"
    assert len(feed.roster) == 21
    assert [row.player_id for row in feed.injuries] == ["5061603", "4433255"]
    assert feed.schedule is not None
    if schedule_season == 2027:
        assert feed.next_game is not None
        assert feed.next_game.game_id == "401909090"
        assert feed.schedule.default_group == "2026-10"
        assert feed.next_game.tag is None
    else:
        assert feed.next_game is None
        assert feed.schedule.default_group == "playoffs"
        assert [g.key for g in feed.schedule.groups][-1] == "playoffs"
