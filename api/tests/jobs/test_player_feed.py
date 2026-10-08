# api/tests/jobs/test_player_feed.py
#
# Tests for the player feed builder.
#
# Tested:
# - Parses made and attempted numbers from whole and per game text
# - Rejects made-attempted text it cannot read
# - Converts percentages from 0-100 to 0-1
# - Converts height to centimeters and weight to kilograms
# - Computes the age on the US Eastern date
# - Builds a two-team season as one row with both codes in order
# - Takes totals games played and started from the per game row and leaves totals minutes null
# - Counts the regular seasons and takes the oldest as the debut
# - Gives an undrafted player a null draft and names the drafting team from the standings
# - Labels award seasons and reads the count
# - Excludes All-Star games from the last five games and keeps them in the game log with no opponent
# - Tags the game log entries and converts their numbers
# - Takes the playoffs average of the latest regular season only
# - Gives null averages for a row with no games
# - Builds the milestones from the newest season and the career
# - Takes the injury from the league injuries by athlete id
# - Gives the team's next game, or none when the season is over
# - Fails the build for a player not on the roster, without a position, or with a team without a standing
# - Builds a valid player feed from the recorded payloads
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_player_feed.py
#
# SEE: api/app/jobs/player_feed.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
import respx

from app.feeds.game_detail import Conference, GameResult, Injury, InjuryStatus
from app.feeds.player import GameKind, PlayerFeed, TagKind
from app.jobs.player_feed import (
    PlayerBuildError,
    averages,
    awards,
    build_player_feed,
    game_log,
    height,
    made_attempted,
    milestones,
    percentage,
    season_split,
    weight,
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
from app.sources.player_bio import PlayerBio, RankedValue, fetch_player_bio
from app.sources.player_draft import DraftPick, fetch_player_draft
from app.sources.player_gamelog import (
    GameLogGame,
    PlayerGameLog,
    fetch_player_gamelog,
)
from app.sources.player_overview import ProviderAward, fetch_player_awards
from app.sources.player_stats import (
    MiscLine,
    PlayerStats,
    StatLine,
    fetch_player_stats,
)
from app.sources.team_players import Roster, RosterEntry, fetch_roster
from app.sources.team_schedule import (
    ScheduledGame,
    SeasonSchedule,
    fetch_season_schedule,
)
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent.parent / "sources" / "fixtures"
NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
START = dt.datetime(2026, 10, 21, 1, 30, tzinfo=dt.UTC)


def standing(code: str, display_name: str, **changes: Any) -> DivisionEntry:
    values: dict[str, Any] = {
        "code": code,
        "location": display_name.rsplit(" ", 1)[0],
        "name": display_name.rsplit(" ", 1)[1],
        "display_name": display_name,
        "conference": Conference.WEST,
        "division": "Northwest",
        "division_order": 1,
        "conference_order": 1,
        "wins": 30,
        "losses": 10,
        "playoff_seed": 1,
        "streak": "W2",
        "games_behind": "-",
        "home": "18-3",
        "road": "12-7",
        "last_ten": "8-2",
        "avg_points_for": 118.0,
        "avg_points_against": 107.9,
        "points_for": 4722,
        "points_against": 4317,
        "differential": 10.1,
        "point_differential": 405,
    }
    return DivisionEntry.model_validate(values | changes)


def standings() -> DivisionStandings:
    entries = [
        standing("OKC", "Oklahoma City Thunder"),
        standing("CHA", "Charlotte Hornets", conference=Conference.EAST),
    ]
    return DivisionStandings(teams={entry.code: entry for entry in entries})


def player(player_id: str = "1", **changes: Any) -> RosterEntry:
    values: dict[str, Any] = {
        "player_id": player_id,
        "first_name": "Shai",
        "last_name": "Gilgeous-Alexander",
        "display_name": "Shai Gilgeous-Alexander",
        "jersey": "2",
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
        "headshot_url": "https://example.com/1.png",
    }
    return RosterEntry.model_validate(values | changes)


def roster(*entries: RosterEntry) -> Roster:
    entries = entries or (player(),)
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
        }
    )


def line(season: str | None = "2025-26", **changes: Any) -> StatLine:
    values: dict[str, Any] = {
        "season": season,
        "teams": ["OKC"],
        "games_played": 60,
        "games_started": 58,
        "minutes": 34.5,
        "field_goals": "10.8-22.8",
        "field_goal_pct": 47.6,
        "three_points": "4.0-10.8",
        "three_point_pct": 36.6,
        "free_throws": "7.9-10.1",
        "free_throw_pct": 78.0,
        "offensive_rebounds": 0.6,
        "defensive_rebounds": 7.1,
        "rebounds": 7.7,
        "assists": 8.3,
        "blocks": 0.5,
        "steals": 1.6,
        "fouls": 2.4,
        "turnovers": 4.0,
        "points": 33.5,
    }
    return StatLine.model_validate(values | changes)


def totals_line(season: str | None = "2025-26", **changes: Any) -> StatLine:
    values: dict[str, Any] = {
        "games_played": None,
        "games_started": None,
        "minutes": None,
        "field_goals": "693-1457",
        "three_points": "254-694",
        "free_throws": "503-645",
        "rebounds": 495,
        "points": 2143,
    }
    return line(season, **(values | changes))


def misc(season: str | None = "2025-26", **changes: Any) -> MiscLine:
    values: dict[str, Any] = {
        "season": season,
        "double_doubles": 34,
        "triple_doubles": 8,
        "disqualifications": 0,
        "ejections": 0,
        "technicals": 17,
        "flagrants": 0,
        "assist_turnover_ratio": 2.1,
        "steal_turnover_ratio": 0.4,
    }
    return MiscLine.model_validate(values | changes)


def stats(
    *seasons: str, with_career: bool = True, with_misc: bool = True
) -> PlayerStats:
    seasons = seasons or ("2025-26",)
    return PlayerStats(
        per_game=[line(s) for s in seasons],
        totals=[totals_line(s) for s in seasons],
        misc=[misc(s) for s in seasons] if with_misc else [],
        career_per_game=line(None, games_played=514, games_started=514)
        if with_career
        else None,
        career_totals=totals_line(None, field_goals="5052-10778")
        if with_career
        else None,
        career_misc=misc(None, double_doubles=273)
        if with_misc and with_career
        else None,
    )


def log_game(game_id: str, start: dt.datetime, **changes: Any) -> GameLogGame:
    values: dict[str, Any] = {
        "game_id": game_id,
        "start_time": start,
        "is_home": True,
        "opponent": "SAS",
        "won": True,
        "team_score": 110,
        "opponent_score": 100,
        "note": None,
        "playoffs": False,
        "minutes": "36",
        "field_goals": "12-21",
        "field_goal_pct": 57.1,
        "three_points": "2-5",
        "three_point_pct": 40.0,
        "free_throws": "9-11",
        "free_throw_pct": 81.8,
        "rebounds": 4,
        "assists": 9,
        "blocks": 1,
        "steals": 3,
        "fouls": 1,
        "turnovers": 3,
        "points": 35,
    }
    return GameLogGame.model_validate(values | changes)


def at_day(day: int) -> dt.datetime:
    return dt.datetime(2026, 3, day, 1, 30, tzinfo=dt.UTC)


def bio() -> PlayerBio:
    return PlayerBio(
        season="2025-26",
        points=RankedValue(value=31.132353, rank=2),
        rebounds=RankedValue(value=4.2941175, rank=None),
        assists=RankedValue(value=6.5882354, rank=14),
        field_goal_pct=RankedValue(value=55.337, rank=12),
    )


def future(game_id: str = "g1") -> ScheduledGame:
    return ScheduledGame.model_validate(
        {
            "game_id": game_id,
            "start_time": START,
            "opponent": "SAS",
            "is_home": False,
            "state": "pre",
            "completed": False,
            "arena": "Frost Bank Center",
            "playoffs": False,
        }
    )


def build(
    *,
    team_roster: Roster | None = None,
    league: LeagueInjuries | None = None,
    regular: SeasonSchedule | None = None,
    draft: DraftPick | None = None,
    summary: PlayerBio | None = None,
    provided_awards: list[ProviderAward] | None = None,
    log: PlayerGameLog | None = None,
    regular_stats: PlayerStats | None = None,
    playoff_stats: PlayerStats | None = None,
    player_id: str = "1",
    now: dt.datetime = NOW,
    detail_ids: frozenset[str] = frozenset(),
) -> PlayerFeed:
    return build_player_feed(
        player_id,
        "OKC",
        team_roster or roster(),
        standings(),
        league or LeagueInjuries(teams={}),
        regular or SeasonSchedule(games=[]),
        SeasonSchedule(games=[]),
        summary,
        draft,
        provided_awards or [],
        log or PlayerGameLog(season=None, games=[]),
        regular_stats or PlayerStats(),
        playoff_stats or PlayerStats(),
        now=now,
        detail_ids=detail_ids,
    )


def test_parses_made_and_attempted_numbers_from_whole_and_per_game_text() -> None:
    assert made_attempted("8-17") == (8.0, 17.0)
    assert made_attempted("8.6-17.1") == (8.6, 17.1)
    assert made_attempted("0-0") == (0.0, 0.0)


@pytest.mark.parametrize("text", ["", "8", "8/17", "8-", "-17", "a-b", "8-17-3"])
def test_rejects_made_attempted_text_it_cannot_read(text: str) -> None:
    with pytest.raises(PlayerBuildError):
        made_attempted(text)


def test_converts_percentages_from_zero_to_one_hundred_to_zero_to_one() -> None:
    assert percentage(55.337) == 0.553
    assert percentage(100.0) == 1.0
    assert percentage(0.0) == 0.0
    assert percentage(81.8) == 0.818


def test_converts_height_to_centimeters_and_weight_to_kilograms() -> None:
    assert height(78.0, "6' 6\"") == {"display": "6' 6\"", "cm": 198}
    assert height(82.0, None) == {"display": "6' 10\"", "cm": 208}
    assert weight(195.4) == {"lb": 195, "kg": 89}
    assert weight(250.0) == {"lb": 250, "kg": 113}


def test_computes_the_age_on_the_us_eastern_date() -> None:
    before_midnight = dt.datetime(2026, 7, 12, 2, 0, tzinfo=dt.UTC)
    after_midnight = dt.datetime(2026, 7, 12, 5, 0, tzinfo=dt.UTC)

    assert build(now=before_midnight).profile.age == 27
    assert build(now=after_midnight).profile.age == 28


def test_builds_the_profile_from_the_roster_entry() -> None:
    profile = build().profile

    assert profile.height is not None and profile.height.cm == 198
    assert profile.weight is not None and (profile.weight.lb, profile.weight.kg) == (
        195,
        89,
    )
    assert profile.birthplace is not None
    assert (profile.birthplace.place, profile.birthplace.country) == (
        "Toronto, ON",
        "Canada",
    )
    assert profile.college == "Kentucky"
    assert (profile.seasons, profile.debut_season, profile.draft) == (None, None, None)


def test_gives_a_player_without_details_null_profile_fields() -> None:
    bare = player(
        height_inches=None,
        weight_lb=None,
        birth_date=None,
        birth_city=None,
        college=None,
        headshot_url=None,
        jersey=None,
    )

    feed = build(team_roster=roster(bare))

    assert feed.profile.height is None and feed.profile.weight is None
    assert feed.profile.age is None and feed.profile.birthplace is None
    assert feed.photo_url is None and feed.number is None


def test_builds_a_two_team_season_as_one_row_with_both_codes_in_order() -> None:
    split = season_split(
        PlayerStats(
            per_game=[line("2024-25", teams=["DAL", "LAL"], games_played=50)],
            totals=[totals_line("2024-25", teams=["DAL", "LAL"])],
        )
    )

    assert [row["teams"] for row in split["per_game"]] == [["DAL", "LAL"]]
    assert split["totals"][0]["teams"] == ["DAL", "LAL"]


def test_takes_totals_games_from_the_per_game_row_and_leaves_totals_minutes_null() -> (
    None
):
    split = season_split(stats("2025-26", "2024-25"))

    assert [row["season"] for row in split["totals"]] == ["2025-26", "2024-25"]
    totals = split["totals"][0]
    assert (totals["games_played"], totals["games_started"]) == (60, 58)
    assert totals["minutes"] is None
    assert split["per_game"][0]["minutes"] == 34.5
    assert split["career"]["totals"]["games_played"] == 514
    assert split["career"]["totals"]["minutes"] is None
    assert split["career"]["per_game"]["minutes"] == 34.5


def test_lists_season_rows_newest_first_whatever_the_order_received() -> None:
    split = season_split(stats("2018-19", "2025-26", "2024-25"))

    assert [r["season"] for r in split["per_game"]] == ["2025-26", "2024-25", "2018-19"]


def test_gives_no_career_rows_without_both_career_lines() -> None:
    assert season_split(stats(with_career=False))["career"] is None


def test_fails_for_a_totals_row_without_a_per_game_row() -> None:
    broken = PlayerStats(per_game=[], totals=[totals_line()])

    with pytest.raises(PlayerBuildError):
        season_split(broken)


def test_counts_the_regular_seasons_and_takes_the_oldest_as_the_debut() -> None:
    feed = build(regular_stats=stats("2025-26", "2024-25", "2018-19"))

    assert feed.profile.seasons == 3
    assert feed.profile.debut_season == "2018-19"
    assert [row.season for row in feed.seasons.regular.per_game] == [
        "2025-26",
        "2024-25",
        "2018-19",
    ]
    assert feed.seasons.playoffs.per_game == []


def test_gives_an_undrafted_player_a_null_draft() -> None:
    assert build(draft=None).profile.draft is None


def test_names_the_drafting_team_from_the_standings() -> None:
    feed = build(draft=DraftPick(year=2018, round=1, pick=11, team_code="CHA"))

    assert feed.profile.draft is not None
    assert feed.profile.draft.team_name == "Charlotte Hornets"
    assert (feed.profile.draft.year, feed.profile.draft.pick) == (2018, 11)


def test_labels_award_seasons_and_reads_the_count() -> None:
    result = awards(
        [
            ProviderAward(name="MVP", display_count="2x", seasons=[2026, 2025]),
            ProviderAward(name="All-Rookie", display_count="1x", seasons=[2000]),
            ProviderAward(name="Empty", display_count="1x", seasons=[]),
        ]
    )

    assert result == [
        {"name": "MVP", "count": 2, "seasons": ["2025-26", "2024-25"]},
        {"name": "All-Rookie", "count": 1, "seasons": ["1999-00"]},
    ]


def test_excludes_all_star_games_from_the_last_five_games_and_keeps_them_in_the_log() -> (
    None
):
    games = [log_game(f"g{day}", at_day(day)) for day in range(1, 8)]
    games.append(
        log_game(
            "star",
            at_day(20),
            opponent=None,
            note="NBA All-Star - Championship",
        )
    )

    log, recent = game_log(PlayerGameLog(season="2025-26", games=games), frozenset())

    assert log is not None
    assert len(log["entries"]) == 8
    star = log["entries"][0]
    assert (star["game_id"], star["opponent"], star["kind"]) == (
        "star",
        None,
        GameKind.ALLSTAR,
    )
    assert [e["game_id"] for e in recent] == ["g7", "g6", "g5", "g4", "g3"]


def test_tags_the_game_log_entries_and_converts_their_numbers() -> None:
    games = [
        log_game(
            "p",
            dt.datetime(2026, 5, 31, 0, 0, tzinfo=dt.UTC),
            note="West Finals - Game 7",
            playoffs=True,
            won=False,
            team_score=103,
            opponent_score=111,
            minutes="43",
        ),
        log_game("c", at_day(2), note="NBA Cup - Quarterfinals"),
        log_game("r", at_day(1)),
    ]

    feed = build(
        log=PlayerGameLog(season="2025-26", games=games),
        detail_ids=frozenset({"p"}),
    )

    assert feed.game_log is not None and feed.game_log.season == "2025-26"
    by_id = {entry.game_id: entry for entry in feed.game_log.entries}
    playoff = by_id["p"]
    assert playoff.kind is GameKind.PLAYOFFS
    assert playoff.tag is not None
    assert (playoff.tag.kind, playoff.tag.conference, playoff.tag.round) == (
        TagKind.PLAYOFFS,
        Conference.WEST,
        3,
    )
    assert playoff.tag.game == 7
    assert playoff.date == dt.date(2026, 5, 30)
    assert playoff.result is GameResult.LOSS
    assert (playoff.team_score, playoff.opponent_score, playoff.minutes) == (
        103,
        111,
        43,
    )
    assert (playoff.field_goals_made, playoff.field_goals_attempted) == (12, 21)
    assert playoff.field_goal_pct == 0.571
    assert playoff.detail_available is True
    assert by_id["c"].kind is GameKind.CUP and by_id["c"].tag is not None
    assert by_id["r"].kind is GameKind.REGULAR and by_id["r"].tag is None
    assert by_id["r"].detail_available is False
    assert [e.game_id for e in feed.last_games] == ["p", "c", "r"]


def test_gives_no_game_log_without_games() -> None:
    assert game_log(PlayerGameLog(season="2025-26", games=[]), frozenset()) == (
        None,
        [],
    )
    assert build().game_log is None
    assert build().last_games == []


def test_takes_the_playoffs_average_of_the_latest_regular_season_only() -> None:
    regular = stats("2025-26", "2024-25")
    playoffs = PlayerStats(per_game=[line("2024-25", games_played=5, points=30.2)])

    assert averages(regular, playoffs)["playoffs"] is None

    playoffs = PlayerStats(
        per_game=[
            line("2025-26", games_played=7, points=26.1),
            line("2024-25", games_played=5, points=30.2),
        ]
    )
    result = averages(regular, playoffs)
    assert result["regular"]["season"] == "2025-26"
    assert result["playoffs"]["season"] == "2025-26"
    assert result["playoffs"]["points"] == 26.1
    assert result["career"]["games_played"] == 514
    assert "season" not in result["career"]


def test_gives_null_averages_for_a_row_with_no_games() -> None:
    regular = PlayerStats(
        per_game=[line("2025-26", games_played=0)],
        career_per_game=line(None, games_played=0),
    )

    assert averages(regular, PlayerStats()) == {
        "regular": None,
        "playoffs": None,
        "career": None,
    }
    assert averages(PlayerStats(), PlayerStats()) == {
        "regular": None,
        "playoffs": None,
        "career": None,
    }


def test_converts_the_average_percentages_in_the_built_feed() -> None:
    feed = build(regular_stats=stats())

    assert feed.averages.regular is not None
    assert feed.averages.regular.field_goal_pct == 0.476
    assert feed.averages.regular.season == "2025-26"
    assert feed.averages.career is not None
    assert feed.averages.career.games_played == 514
    assert feed.seasons.regular.per_game[0].field_goals_made == 10.8


def test_builds_the_milestones_from_the_newest_season_and_the_career() -> None:
    result = milestones(stats("2024-25", "2025-26"))

    assert result is not None
    assert result["season"] == "2025-26"
    assert result["current"]["double_doubles"] == 34
    assert result["career"]["double_doubles"] == 273
    assert milestones(PlayerStats()) is None
    assert milestones(stats(with_career=False)) is None
    assert build(regular_stats=stats()).milestones is not None


def test_builds_the_summary_with_values_ranks_and_the_percentage_as_a_share() -> None:
    summary = build(summary=bio()).summary

    assert summary is not None and summary.season == "2025-26"
    assert (summary.points.value, summary.points.rank) == (31.1, 2)
    assert summary.rebounds.rank is None
    assert summary.field_goal_pct.value == 0.553
    assert build().summary is None


def test_takes_the_injury_from_the_league_injuries_by_athlete_id() -> None:
    league = LeagueInjuries(
        teams={
            "OKC": [
                InjuryReport(
                    injury=Injury(
                        display_name="Other", status=InjuryStatus.OUT, comment="knee"
                    ),
                    player_id="2",
                    updated_at=NOW,
                ),
                InjuryReport(
                    injury=Injury(
                        display_name="Shai",
                        status=InjuryStatus.DAY_TO_DAY,
                        comment=None,
                    ),
                    player_id="1",
                    updated_at=NOW,
                ),
            ]
        }
    )

    injury = build(league=league).injury

    assert injury is not None
    assert injury.status is InjuryStatus.DAY_TO_DAY
    assert (injury.comment, injury.updated_at) == (None, NOW)
    assert build().injury is None


def test_gives_no_injury_for_a_report_without_a_date() -> None:
    league = LeagueInjuries(
        teams={
            "OKC": [
                InjuryReport(
                    injury=Injury(display_name="Shai", status=InjuryStatus.OUT),
                    player_id="1",
                    updated_at=None,
                )
            ]
        }
    )

    assert build(league=league).injury is None


def test_gives_the_teams_next_game_or_none_when_the_season_is_over() -> None:
    upcoming = build(
        regular=SeasonSchedule(games=[future("g9")]),
        detail_ids=frozenset({"g9"}),
    ).next_game
    over = build(regular=SeasonSchedule(games=[])).next_game

    assert upcoming is not None
    assert (upcoming.game_id, upcoming.opponent, upcoming.detail_available) == (
        "g9",
        "SAS",
        True,
    )
    assert over is None
    assert build().live is None


def test_names_the_team_and_the_player_from_the_roster_and_standings() -> None:
    feed = build()

    assert (feed.id, feed.first_name, feed.last_name) == (
        "1",
        "Shai",
        "Gilgeous-Alexander",
    )
    assert (feed.number, feed.position) == ("2", "Guard")
    assert (feed.team.code, feed.team.name, feed.team.city) == (
        "OKC",
        "Thunder",
        "Oklahoma City",
    )
    assert str(feed.photo_url) == "https://example.com/1.png"


def test_fails_the_build_for_a_player_not_on_the_roster() -> None:
    with pytest.raises(PlayerBuildError) as raised:
        build(player_id="99")

    assert raised.value.reason == "player 99 is not on the roster"


def test_fails_the_build_for_a_player_without_a_position() -> None:
    with pytest.raises(PlayerBuildError) as raised:
        build(team_roster=roster(player(position_name=None)))

    assert raised.value.reason == "player 1 has no position"


def test_fails_the_build_when_the_drafting_team_has_no_standing() -> None:
    with pytest.raises(PlayerBuildError) as raised:
        build(draft=DraftPick(year=2018, round=1, pick=11, team_code="BOS"))

    assert raised.value.reason == "team BOS has no standing"


def test_fails_the_build_when_the_team_has_no_standing() -> None:
    with pytest.raises(PlayerBuildError) as raised:
        build_player_feed(
            "1",
            "BOS",
            roster(),
            standings(),
            LeagueInjuries(teams={}),
            SeasonSchedule(games=[]),
            SeasonSchedule(games=[]),
            None,
            None,
            [],
            PlayerGameLog(season=None, games=[]),
            PlayerStats(),
            PlayerStats(),
            now=NOW,
            detail_ids=frozenset(),
        )

    assert raised.value.reason == "team BOS has no standing"


def test_fails_the_build_for_an_invalid_feed() -> None:
    with pytest.raises(PlayerBuildError) as raised:
        build(team_roster=roster(player(jersey="123")))

    assert raised.value.reason.startswith("invalid feed: ")


def recorded(name: str, folder: str) -> Any:
    return json.loads((FIXTURES / folder / name).read_text(encoding="utf-8"))


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


@pytest.mark.anyio
async def test_builds_a_valid_player_feed_from_the_recorded_payloads(
    mock: respx.MockRouter,
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        division_standings_url="https://example.com/standings?level=3&seasontype=2",
        team_roster_url="https://example.com/teams/{team}/roster",
        player_photo_url="https://example.com/players/{player_id}.png",
        league_injuries_url="https://example.com/injuries",
        team_schedule_url="https://example.com/teams/{team}/schedule",
        player_bio_url="https://example.com/athletes/{player_id}",
        player_draft_url="https://example.com/draft/{player_id}",
        player_overview_url="https://example.com/athletes/{player_id}/overview",
        player_gamelog_url="https://example.com/athletes/{player_id}/gamelog",
        player_stats_url="https://example.com/athletes/{player_id}/stats",
    )
    athlete = "https://example.com/athletes/4278073"
    mock.get("https://example.com/standings?level=3&seasontype=2").respond(
        json=recorded("regular-2026.json", "division_standings")
    )
    mock.get("https://example.com/teams/OKC/roster").respond(
        json=recorded("roster-okc.json", "team_players")
    )
    mock.get("https://example.com/injuries").respond(
        json=recorded("injuries-detail.json", "league_injuries")
    )
    mock.get("https://example.com/teams/OKC/schedule?season=2027&seasontype=2").respond(
        json=recorded("okc-2027-regular.json", "team_schedule")
    )
    mock.get("https://example.com/teams/OKC/schedule?season=2027&seasontype=3").respond(
        json={"events": []}
    )
    mock.get(athlete).respond(json=recorded("bio.json", "player_bio"))
    mock.get("https://example.com/draft/4278073").respond(
        json=recorded("drafted.json", "player_draft")
    )
    mock.get(f"{athlete}/overview").respond(
        json=recorded("overview.json", "player_overview")
    )
    mock.get(f"{athlete}/gamelog").respond(
        json=recorded("gamelog-2026.json", "player_gamelog")
    )
    mock.get(f"{athlete}/stats?seasontype=3").respond(
        json=recorded("playoffs.json", "player_stats")
    )
    mock.get(f"{athlete}/stats").respond(json=recorded("regular.json", "player_stats"))
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            division = await fetch_division_standings(client, settings)
            team_roster = await fetch_roster(client, "OKC", settings)
            league = await fetch_league_injuries(client, settings)
            regular = await fetch_season_schedule(
                client, "OKC", 2027, settings, playoffs=False
            )
            playoffs = await fetch_season_schedule(
                client, "OKC", 2027, settings, playoffs=True
            )
            summary = await fetch_player_bio(client, "4278073", settings)
            draft = await fetch_player_draft(client, "4278073", settings)
            provided = await fetch_player_awards(client, "4278073", settings)
            log = await fetch_player_gamelog(client, "4278073", settings)
            regular_stats = await fetch_player_stats(
                client, "4278073", settings, playoffs=False
            )
            playoff_stats = await fetch_player_stats(
                client, "4278073", settings, playoffs=True
            )

    feed = build_player_feed(
        "4278073",
        "OKC",
        team_roster,
        division,
        league,
        regular,
        playoffs,
        summary,
        draft,
        provided,
        log,
        regular_stats,
        playoff_stats,
        now=NOW,
        detail_ids=frozenset({"401809243"}),
    )

    dumped = feed.model_dump(mode="json")
    assert PlayerFeed.model_validate(dumped) == feed
    assert (feed.id, feed.team.code, feed.live) == ("4278073", "OKC", None)
    assert feed.summary is not None and feed.summary.season == "2025-26"
    assert feed.profile.draft is not None
    assert feed.profile.draft.team_name == "Charlotte Hornets"
    assert feed.profile.seasons == 3 and feed.profile.debut_season == "2018-19"
    assert [row.season for row in feed.seasons.regular.per_game] == [
        "2025-26",
        "2024-25",
        "2018-19",
    ]
    assert feed.seasons.regular.per_game[1].teams == ["DAL", "LAL"]
    assert feed.averages.regular is not None
    assert feed.averages.playoffs is None
    assert feed.game_log is not None and len(feed.game_log.entries) == 10
    assert len(feed.last_games) == 5
    assert [award.name for award in feed.awards][:2] == ["MVP", "All-NBA 1st Team"]
    assert feed.awards[0].count == 2
    assert feed.next_game is not None
