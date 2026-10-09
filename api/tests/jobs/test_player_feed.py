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
# - Takes the next game it is given, or none when the season is over
# - Fails the build for a player not on the roster, without a position, or with a team without a standing
# - Builds a valid player feed from the recorded payloads
# - The live block is none with no live game or a game missing its period, clock or score, carries the game from the team's side and the player's box score line, and has a null line when the detail is missing, has no box score or does not list him
# - Sets detailAvailable exactly for the ids given on the next game, last games and game log
# - The kind: before every roster is fetched a request answers unavailable, after it an id in no roster answers unknown, with no source request
# - The kind: no player or team feed is built, stored or fetched by stars runs, games runs and the cleanup without a request
# - The kind: a request builds the team feed first when it is missing or stale, then the player, and stores both
# - The kind: a fresh stored team feed is reused with no roster, schedule or team info request and its next game is the player's
# - The kind: a stale team whose rebuild fails is used as stored, and a missing team whose build fails fails the player build
# - The kind: a failed rebuild of a stale player feed keeps and serves the stored feed
# - The kind: a player feed is fresh before a final game of its team plus 1 hour and before 7 days, and stale at either
# - The kind: live is added when served from the team's live game, with the line from the stored detail feed, and is never stored
# - The kind: a live player request refreshes the game and serves its detail feed within the wait, and makes no request for an unknown id
# - The kind: detailAvailable is true exactly for the games inside the days shown when served
# - The kind: after a stars run the cleanup deletes the feeds of players on no roster with no source request, and nothing while the rosters are not all fetched
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, dependency, expiry and cleanup edges
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

from app.feeds.game_detail import (
    Conference,
    GameDetailFeed,
    GameResult,
    Injury,
    InjuryStatus,
)
from app.feeds.games import GameStatus, Star
from app.feeds.player import GameKind, NextGame, PlayerFeed, TagKind
from app.jobs import game_detail_feed
from app.jobs.on_demand import (
    FeedKind,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.player_feed import (
    KIND,
    PlayerBuildError,
    PlayerFeeds,
    averages,
    awards,
    build_player_feed,
    game_log,
    height,
    live_block,
    made_attempted,
    milestones,
    percentage,
    season_split,
    weight,
    with_player_detail,
)
from app.jobs.stars import RETRY, StarsJob
from app.jobs.team_feed import FEED_LIFETIME, next_game
from app.jobs.team_feed import KIND as TEAM_KIND
from app.settings import Settings
from app.sources.division_standings import (
    DivisionEntry,
    DivisionStandings,
    fetch_division_standings,
)
from app.sources.game_detail import GameDetailSections
from app.sources.http import SourceClient, SourceError, create_client
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
from app.sources.scoreboard import ScoreboardGame
from app.sources.team_players import (
    PlayerAverages,
    Roster,
    RosterEntry,
    fetch_roster,
)
from app.sources.team_schedule import (
    ScheduledGame,
    SeasonSchedule,
    fetch_season_schedule,
)
from app.sources.teams import TEAM_CODES
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_game_detail_feed import TEAM_STATS, VENUE
from tests.jobs.test_game_detail_feed import build as build_detail
from tests.jobs.test_game_detail_feed import standings as detail_standings
from tests.jobs.test_team_feed import (
    DAY,
    HOUR,
    SECOND,
    TODAY,
    TeamKit,
    scoreboard,
)
from tests.jobs.test_team_feed import game as scheduled_game
from tests.jobs.test_team_feed import season as schedule_of

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
    return DivisionStandings(
        season=2026, teams={entry.code: entry for entry in entries}
    )


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
    upcoming: NextGame | None = None,
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
        upcoming,
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


def test_takes_the_next_game_it_is_given_or_none_when_the_season_is_over() -> None:
    given = next_game(
        SeasonSchedule(games=[future("g9")]),
        SeasonSchedule(games=[]),
        frozenset({"g9"}),
    )
    upcoming = build(upcoming=given).next_game
    over = build(upcoming=None).next_game

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
            None,
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
        next_game(regular, playoffs, frozenset({"401809243"})),
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


# The live block and the detail availability


def box_line(player_id: str) -> dict[str, Any]:
    zero = dict.fromkeys(
        (
            "points",
            "field_goals_made",
            "field_goals_attempted",
            "three_points_made",
            "three_points_attempted",
            "free_throws_made",
            "free_throws_attempted",
            "offensive_rebounds",
            "defensive_rebounds",
            "rebounds",
            "assists",
            "turnovers",
            "steals",
            "blocks",
            "fouls",
        ),
        0,
    )
    return {
        **zero,
        "player_id": player_id,
        "display_name": "A B",
        "starter": True,
        "minutes": "12",
        "plus_minus": 3,
        "photo_url": "https://example.com/p.png",
    }


def box_side(*player_ids: str) -> dict[str, Any]:
    totals = {**box_line("x"), "field_goal_pct": 0.5}
    for key in (
        "player_id",
        "display_name",
        "starter",
        "minutes",
        "plus_minus",
        "photo_url",
    ):
        del totals[key]
    totals.update(three_point_pct=0.4, free_throw_pct=0.8)
    return {"players": [box_line(i) for i in player_ids], "totals": totals}


def live_game(home: str = "OKC", away: str = "SAS") -> ScoreboardGame:
    return scoreboard("L1", GameStatus.LIVE, NOW - HOUR, away=away, home=home)


def detail_of(
    game: ScoreboardGame, home_ids: tuple[str, ...], away_ids: tuple[str, ...] = ()
) -> GameDetailFeed:
    """A live game detail feed of the game with a box score listing the given players."""
    detail = GameDetailSections.model_validate(
        {
            "venue": VENUE,
            "team_stats": TEAM_STATS,
            "box_score": {"away": box_side(*away_ids), "home": box_side(*home_ids)},
        }
    )
    return build_detail(
        game,
        detail,
        league_standings=detail_standings(game.away.code, game.home.code),
    )


def test_live_block_is_none_with_no_live_game_and_when_the_game_lacks_a_field() -> None:
    game = live_game()

    assert live_block("OKC", "1", None, None) is None
    for field in ("period", "clock", "score"):
        assert (
            live_block("OKC", "1", game.model_copy(update={field: None}), None) is None
        )


def test_live_block_carries_the_game_from_the_teams_side_and_the_players_line() -> None:
    game = live_game()
    detail = detail_of(game, ("1",), ("9",))

    home = live_block("OKC", "1", game, detail)
    away = live_block("SAS", "9", game, detail)

    assert home is not None and away is not None
    assert (home.game_id, home.opponent, home.is_home) == ("L1", "SAS", True)
    assert (home.period, home.clock) == (2, "5:00")
    assert (home.team_score, home.opponent_score) == (38, 40)
    assert home.line is not None and home.line.player_id == "1"
    assert (away.opponent, away.is_home) == ("OKC", False)
    assert (away.team_score, away.opponent_score) == (40, 38)
    assert away.line is not None and away.line.player_id == "9"


def test_live_block_has_a_null_line_when_the_detail_is_missing_has_no_box_score_or_does_not_list_him() -> (
    None
):
    game = live_game()
    without_box = detail_of(game, ("1",)).model_copy(update={"box_score": None})

    assert live_block("OKC", "1", game, None) is not None
    assert live_block("OKC", "1", game, None).line is None  # type: ignore[union-attr]
    assert live_block("OKC", "1", game, without_box).line is None  # type: ignore[union-attr]
    assert live_block("OKC", "1", game, detail_of(game, ("2",))).line is None  # type: ignore[union-attr]
    assert live_block("OKC", "1", game, detail_of(game, (), ("1",))).line is None  # type: ignore[union-attr]


def test_with_player_detail_sets_detail_availability_exactly_for_the_ids_given() -> (
    None
):
    log = PlayerGameLog(
        season="2025-26", games=[log_game("a", at_day(3)), log_game("b", at_day(2))]
    )
    next_up = next_game(
        SeasonSchedule(games=[future("c")]), SeasonSchedule(games=[]), frozenset()
    )
    feed = build(log=log, upcoming=next_up)

    served = with_player_detail(feed, frozenset({"a", "c"}))

    assert served.next_game is not None and served.next_game.detail_available
    assert {g.game_id: g.detail_available for g in served.last_games} == {
        "a": True,
        "b": False,
    }
    assert served.game_log is not None
    assert {g.game_id: g.detail_available for g in served.game_log.entries} == {
        "a": True,
        "b": False,
    }
    assert with_player_detail(feed, frozenset()).next_game is not None


# The kind


class PlayerKit(TeamKit):
    """The team kit plus the stars job, the player kind and a fake games kind."""

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.roster_errors: set[str] = set()
        self.detail_builds = 0
        self.detail_feeds: dict[str, GameDetailFeed] = {}
        self.stars = StarsJob(
            self.settings,
            self.store,
            self.client,
            fetch_roster=self.stars_roster,
            fetch_season_averages=self.stars_averages,
            final_games=lambda: self.games.final_games(),
            clock=lambda: self.clock[0],
            after_run=lambda: self.players.after_stars_run(),
        )
        self.cache.register(
            FeedKind(
                game_detail_feed.KIND,
                GameDetailFeed,
                check=lambda _: IdStatus.KNOWN,
                build=self.build_detail,
                is_fresh=lambda feed, built_at, now: True,
                keep=lambda _: True,
            )
        )
        self.players = PlayerFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.games,
            self.stars,
            self.teams,
            fetch_roster=self.fetch_roster,
            fetch_division_standings=self.fetch_division_standings,
            fetch_league_injuries=self.fetch_league_injuries,
            fetch_player_bio=self.fetch_bio,
            fetch_player_draft=self.fetch_draft,
            fetch_player_awards=self.fetch_awards,
            fetch_player_gamelog=self.fetch_gamelog,
            fetch_player_stats=self.fetch_stats,
        )

    async def build_detail(self, game_id: str) -> GameDetailFeed:
        self.detail_builds += 1
        if game_id not in self.detail_feeds:
            raise SourceError("test", "no detail")
        return self.detail_feeds[game_id]

    def team_players(self, code: str) -> list[str]:
        return ["1", "2"] if code == "OKC" else [f"{code}1", f"{code}2"]

    async def stars_roster(
        self, client: SourceClient, code: str, settings: Settings
    ) -> Roster:
        if code in self.roster_errors:
            raise SourceError("test", f"roster {code} is down")
        return Roster(
            season=2027,
            team_id=f"id-{code}",
            players=[
                Star.model_validate(
                    {
                        "player_id": player_id,
                        "first_name": "A",
                        "last_name": "B",
                        "short_name": "A. B",
                        "team_code": code,
                        "photo_url": "https://example.com/p.png",
                    }
                )
                for player_id in self.team_players(code)
            ],
        )

    async def stars_averages(
        self, client: SourceClient, team_id: str, season_year: int, settings: Settings
    ) -> list[PlayerAverages]:
        code = team_id.removeprefix("id-")
        return [
            PlayerAverages(player_id=i, points=10, rebounds=1, assists=1)
            for i in self.team_players(code)
        ]

    async def fetch_roster(
        self, client: SourceClient, team: str, settings: Settings
    ) -> Roster:
        await self.read(f"roster/{team}", dt.timedelta(hours=24))
        return roster()

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings
    ) -> DivisionStandings:
        await self.read("standings", HOUR)
        return standings()

    async def fetch_bio(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> PlayerBio | None:
        await self.read(f"bio/{player_id}", HOUR)
        return bio()

    async def fetch_draft(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> DraftPick | None:
        await self.read(f"draft/{player_id}", HOUR)
        return None

    async def fetch_awards(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> list[ProviderAward]:
        await self.read(f"awards/{player_id}", HOUR)
        return []

    async def fetch_gamelog(
        self, client: SourceClient, player_id: str, settings: Settings
    ) -> PlayerGameLog:
        await self.read(f"gamelog/{player_id}", HOUR)
        return PlayerGameLog(
            season="2025-26",
            games=[log_game("g1", at_day(2)), log_game("g9", at_day(1))],
        )

    async def fetch_stats(
        self,
        client: SourceClient,
        player_id: str,
        settings: Settings,
        *,
        playoffs: bool,
    ) -> PlayerStats:
        await self.read(f"stats/{player_id}/{playoffs}", HOUR)
        return PlayerStats() if playoffs else stats()

    async def run_stars(self, at: dt.datetime | None = None) -> None:
        if at is not None:
            self.clock[0] = at
        await self.stars.run(self.clock[0])

    async def serve_player(
        self, player_id: str, at: dt.datetime | None = None
    ) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, player_id)
        await self.settle()
        return body

    def stored_player(self, player_id: str) -> PlayerFeed | None:
        body = read_by_id(self.path, KIND, player_id)
        return None if body is None else PlayerFeed.model_validate_json(body)


@pytest.fixture
def kit(tmp_path: Path) -> Iterator[PlayerKit]:
    with respx.mock:
        yield PlayerKit(tmp_path)


@pytest.mark.anyio
async def test_before_every_roster_is_fetched_a_request_is_unavailable_and_after_it_an_unknown_id_is_unknown(
    kit: PlayerKit,
) -> None:
    kit.roster_errors.add("BOS")
    await kit.run_stars()

    assert kit.players.check("1") is IdStatus.KNOWN
    assert kit.players.check("nobody") is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "nobody")
    await kit.players.refresh_live("nobody", wait=1)
    kit.roster_errors.clear()
    await kit.run_stars(NOW + RETRY)
    assert kit.players.check("nobody") is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "nobody")
    await kit.players.refresh_live("nobody", wait=1)

    assert kit.requests == [] and kit.calls == []
    assert kit.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_no_player_or_team_feed_is_built_stored_or_fetched_without_a_request(
    kit: PlayerKit, tmp_path: Path
) -> None:
    kit.scoreboard[TODAY] = [live_game()]

    await kit.run_stars()
    await kit.run_games()
    await kit.run_games(NOW + 31 * SECOND)
    await kit.run_stars(NOW + DAY)
    kit.cache.cleanup()
    await kit.settle()

    assert kit.requests == [] and kit.calls == []
    assert not (tmp_path / "feeds" / KIND).exists()
    assert not (tmp_path / "feeds" / TEAM_KIND).exists()
    assert kit.store.feed_build_ids(KIND) == set()
    assert kit.store.feed_build_ids(TEAM_KIND) == set()


@pytest.mark.anyio
async def test_a_request_with_no_stored_team_feed_builds_the_team_first_then_the_player(
    kit: PlayerKit,
) -> None:
    await kit.run_stars()

    body = await kit.serve_player("1")

    assert PlayerFeed.model_validate_json(body).id == "1"
    assert kit.calls.index("schedule/OKC/True") < kit.calls.index("bio/1")
    assert kit.stored("okc") is not None
    assert kit.stored_player("1") is not None
    assert kit.last_build("okc") == kit.store.feed_build(KIND, "1").last_build  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_a_fresh_stored_team_feed_is_reused_with_no_roster_schedule_or_info_request(
    kit: PlayerKit,
) -> None:
    kit.regular = schedule_of(scheduled_game("g1"))
    await kit.run_stars()
    await kit.serve("okc")
    kit.requests.clear()
    kit.calls.clear()

    body = await kit.serve_player("1", NOW + 30 * SECOND)

    assert [
        name for name in kit.requests if name.startswith(("roster", "schedule", "info"))
    ] == []
    assert not any(name.startswith(("schedule", "info")) for name in kit.calls)
    team = kit.stored("okc")
    assert team is not None and team.next_game is not None
    served = PlayerFeed.model_validate_json(body)
    assert served.next_game == team.next_game
    assert kit.called("roster/OKC") == 1
    assert kit.called("schedule/OKC/False") == 0


@pytest.mark.anyio
async def test_a_stale_team_feed_is_rebuilt_before_the_player(kit: PlayerKit) -> None:
    await kit.run_stars()
    await kit.serve("okc")
    kit.calls.clear()

    await kit.serve_player("1", NOW + FEED_LIFETIME)

    assert kit.calls.index("info/OKC") < kit.calls.index("bio/1")
    assert kit.last_build("okc") == NOW + FEED_LIFETIME


@pytest.mark.anyio
async def test_a_stale_team_whose_rebuild_fails_is_used_as_stored_by_the_player_build(
    kit: PlayerKit,
) -> None:
    kit.regular = schedule_of(scheduled_game("g1"))
    await kit.run_stars()
    await kit.serve("okc")
    kit.failing.add("info/OKC")

    body = await kit.serve_player("1", NOW + FEED_LIFETIME)

    assert PlayerFeed.model_validate_json(body).next_game is not None
    assert kit.last_build("okc") == NOW
    assert [f.feed_id for f in kit.store.failed_feed_builds()] == ["okc"]


@pytest.mark.anyio
async def test_a_failed_rebuild_of_a_stale_player_feed_keeps_and_serves_the_stored_feed(
    kit: PlayerKit,
) -> None:
    await kit.run_stars()
    first = await kit.serve_player("1")
    stored = read_by_id(kit.path, KIND, "1")
    kit.failing.add("bio/1")

    body = await kit.serve_player("1", NOW + FEED_LIFETIME)

    assert body == first
    assert kit.called("bio/1") == 2
    assert read_by_id(kit.path, KIND, "1") == stored
    build = kit.store.feed_build(KIND, "1")
    assert build is not None and build.last_build == NOW
    assert [(f.kind, f.feed_id) for f in kit.store.failed_feed_builds()] == [
        (KIND, "1")
    ]


@pytest.mark.anyio
async def test_a_missing_team_whose_build_fails_fails_the_player_build(
    kit: PlayerKit,
) -> None:
    await kit.run_stars()
    kit.failing.add("info/OKC")

    with pytest.raises(FeedUnavailableError):
        await kit.serve_player("1")

    failed = {(f.kind, f.feed_id) for f in kit.store.failed_feed_builds()}
    assert failed == {(TEAM_KIND, "okc"), (KIND, "1")}
    assert kit.called("bio/1") == 0
    assert kit.stored_player("1") is None


@pytest.mark.anyio
async def test_a_player_feed_is_fresh_before_a_final_game_of_its_team_plus_1_hour_and_stale_at_it(
    kit: PlayerKit,
) -> None:
    final = NOW + 2 * HOUR
    kit.scoreboard[TODAY] = [scoreboard("f1", GameStatus.FINAL, NOW - HOUR)]
    kit.store.set_final_time("f1", TODAY, final)
    await kit.run_stars()
    await kit.run_games()
    await kit.serve_player("1")

    await kit.serve_player("1", final + HOUR - SECOND)
    assert kit.called("bio/1") == 1
    await kit.serve_player("1", final + HOUR)

    assert kit.called("bio/1") == 2
    build = kit.store.feed_build(KIND, "1")
    assert build is not None and build.last_build == final + HOUR


@pytest.mark.anyio
async def test_a_player_feed_is_fresh_before_7_days_and_stale_at_7_days(
    kit: PlayerKit,
) -> None:
    await kit.run_stars()
    await kit.serve_player("1")

    await kit.serve_player("1", NOW + FEED_LIFETIME - SECOND)
    assert kit.called("bio/1") == 1
    await kit.serve_player("1", NOW + FEED_LIFETIME)

    assert kit.called("bio/1") == 2


def stored_live(kit: PlayerKit, home_ids: tuple[str, ...]) -> None:
    game = live_game()
    publish_by_id(
        kit.path, game_detail_feed.KIND, GameDetailFeed, "L1", detail_of(game, home_ids)
    )


@pytest.mark.anyio
async def test_live_is_null_with_no_live_game_of_the_team(kit: PlayerKit) -> None:
    kit.scoreboard[TODAY] = [
        scoreboard("L2", GameStatus.LIVE, NOW - HOUR, away="BOS", home="NYK")
    ]
    await kit.run_stars()
    await kit.run_games()

    body = await kit.serve_player("1")

    assert PlayerFeed.model_validate_json(body).live is None


@pytest.mark.anyio
async def test_live_carries_the_game_and_the_players_line_and_is_never_stored(
    kit: PlayerKit,
) -> None:
    kit.scoreboard[TODAY] = [live_game()]
    await kit.run_stars()
    await kit.run_games()
    stored_live(kit, ("1",))

    served = PlayerFeed.model_validate_json(await kit.serve_player("1"))

    assert served.live is not None
    assert (served.live.game_id, served.live.opponent, served.live.is_home) == (
        "L1",
        "SAS",
        True,
    )
    assert (served.live.team_score, served.live.opponent_score) == (38, 40)
    assert served.live.line is not None and served.live.line.player_id == "1"
    stored = kit.stored_player("1")
    assert stored is not None and stored.live is None


@pytest.mark.anyio
async def test_live_has_a_null_line_before_the_player_is_in_the_box_score(
    kit: PlayerKit,
) -> None:
    kit.scoreboard[TODAY] = [live_game()]
    await kit.run_stars()
    await kit.run_games()
    stored_live(kit, ("2",))

    served = PlayerFeed.model_validate_json(await kit.serve_player("1"))

    assert served.live is not None and served.live.line is None


@pytest.mark.anyio
async def test_a_live_player_request_refreshes_the_game_and_serves_its_detail_feed(
    kit: PlayerKit,
) -> None:
    game = live_game()
    kit.scoreboard[TODAY] = [game]
    kit.detail_feeds["L1"] = detail_of(game, ("1",))
    await kit.run_stars()
    await kit.run_games()
    kit.clock[0] = NOW + 31 * SECOND

    await kit.players.refresh_live("1", wait=5)
    await kit.settle()

    assert kit.detail_builds == 1
    assert read_by_id(kit.path, game_detail_feed.KIND, "L1") is not None
    served = PlayerFeed.model_validate_json(await kit.serve_player("1"))
    assert served.live is not None and served.live.line is not None


@pytest.mark.anyio
async def test_a_live_refresh_whose_detail_build_fails_never_raises(
    kit: PlayerKit,
) -> None:
    kit.scoreboard[TODAY] = [live_game()]
    await kit.run_stars()
    await kit.run_games()

    await kit.players.refresh_live("1", wait=5)
    await kit.settle()

    assert kit.detail_builds == 1
    assert read_by_id(kit.path, game_detail_feed.KIND, "L1") is None


@pytest.mark.anyio
async def test_detail_availability_is_set_when_served_from_the_days_shown_and_not_stored(
    kit: PlayerKit,
) -> None:
    kit.regular = schedule_of(scheduled_game("g1"))
    await kit.run_stars()
    await kit.serve_player("1")
    kit.scoreboard[TODAY] = [scoreboard("g1", GameStatus.SCHEDULED, NOW + HOUR)]
    await kit.run_games()

    served = PlayerFeed.model_validate_json(
        await kit.serve_player("1", NOW + 30 * SECOND)
    )

    assert served.next_game is not None and served.next_game.detail_available
    assert served.game_log is not None
    assert {g.game_id: g.detail_available for g in served.game_log.entries} == {
        "g1": True,
        "g9": False,
    }
    assert {g.game_id: g.detail_available for g in served.last_games} == {
        "g1": True,
        "g9": False,
    }
    stored = kit.stored_player("1")
    assert stored is not None and stored.game_log is not None
    assert not any(g.detail_available for g in stored.game_log.entries)
    assert stored.next_game is not None and not stored.next_game.detail_available


@pytest.mark.anyio
async def test_the_cleanup_after_a_stars_run_deletes_players_on_no_roster_with_no_request(
    kit: PlayerKit,
) -> None:
    feed = build()
    for player_id in ("1", "gone"):
        publish_by_id(kit.path, KIND, PlayerFeed, player_id, feed)
        kit.store.record_build(KIND, player_id, NOW)
    kit.roster_errors.add("BOS")

    await kit.run_stars()

    assert not kit.stars.rosters_ready()
    assert kit.store.feed_build_ids(KIND) == {"1", "gone"}
    kit.roster_errors.clear()
    await kit.run_stars(NOW + RETRY)

    assert kit.stars.rosters_ready()
    assert kit.store.feed_build_ids(KIND) == {"1"}
    assert read_by_id(kit.path, KIND, "gone") is None
    assert read_by_id(kit.path, KIND, "1") is not None
    assert kit.requests == [] and kit.calls == []
    assert len(set(TEAM_CODES.values())) == 30
