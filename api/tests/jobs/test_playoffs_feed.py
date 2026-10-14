# api/tests/jobs/test_playoffs_feed.py
#
# Tests for the playoffs feed builder and its feed kind.
#
# Tested:
# - State: picture before the play-in window (in the preseason and in the regular season), playin on the first day of the window and after play-in games, playoffs once a round 1 game is live, finals once a Finals game is scheduled, complete once the Finals series object says completed
# - Stages: statuses (next play-in in picture, overlapping rounds, complete), first and last US Eastern dates, null dates with no game
# - Current round: 1, 2 when round 1 is complete and round 2 not started, 3 during the conference finals, null outside the playoffs
# - Finals game and summary: null before game 1, set after game 3
# - Bracket: 15 series in order in every state; label parts of an undecided series; one side decided; round 1 placement by seed pair with the play-in winners as seeds 7 and 8; round 2, round 3 and Finals placement by feeder; wins, summary and status from the series object, never counted from the games; overtime from the period; a series lists only the games scheduled; a canceled game is not listed
# - Bracket errors: a seed pair outside the table, a team outside its feeder, two series in one slot, an unknown competition type, a note without a game number, a conference mix, a team outside the league in a live or final game
# - Placeholder side: a game neither live nor final with an undecided side (a guest or no code) is ignored in the play-in and in round 1, its slots keep the standings or label value
# - Play-in: slots with places 7 to 10, games with date and time, outcomes (seed 7, loser out, seed 8), the 8th seed game takes the loser of 7th vs 8th and the winner of 9th vs 10th, the bracket seeds 7 and 8 fill once decided; fails on an unknown note and on two games of one kind
# - Champion: null until complete; the Finals result, dates, record, home and road from the record read, the point differential over the postseason games only with the minus sign U+2212; null record values with no record read
# - Leaders: nine categories with five leaders and ranks, fewer leaders keep their ranks, a leader on no roster leaves a rank gap, a missing photo is null, null when the read failed or no category has a leader
# - Awards: code order, team awards of up to five, an award with no winner on a roster is not in the feed, null when the read failed or none has a winner
# - Picture: rows in conference order with games behind, no record, seed or clinch in the preseason
# - Helpers: postseason_days, reads_days, group_series, finals_winner
# - Errors: an invalid feed is wrapped in a build error
# - The kind: an id other than league answers unknown with no build; not ready with no season or rosters; no build without a request; a request builds and stores and a second reads storage
# - The kind: no scoreboard day is read before the play-in window and every day of both windows inside it
# - The kind: a failed season type, standings or scoreboard day answers unavailable and is not retried for 10 minutes; a failed rebuild keeps and serves the stored feed
# - The kind: a failed leaders, awards, team info or champion record read only nulls its part; the record is read only for the champion of a complete Finals
# - The kind: expiry (a final postseason game of the feed or of the games job inside the postseason dates plus 1 hour; a picture feed also at a final league game plus 1 hour; the start of the play-in window; 7 days; a complete feed kept while its season is current)
# - The kind: detailAvailable is set from the loaded games and not stored; the cleanup keeps league; stored() reads the stored feed
#
# What is covered:
# - Pure logic: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Fixtures use the league's own team codes, made-up names, arenas and broadcasters.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_playoffs_feed.py
#
# SEE: api/app/jobs/playoffs_feed.py

import asyncio
import datetime as dt
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest
import respx

from app.feeds.game_detail import Conference
from app.feeds.games import GameStatus, GameTeam, LineScore, Score
from app.feeds.playoffs import (
    AwardCode,
    LeaderCategory,
    PlayoffsFeed,
    PlayoffsState,
    PlayoffStage,
    PlayoffStageStatus,
    SeriesId,
    SeriesStatus,
)
from app.feeds.standings import Clinch
from app.jobs.games import GamesJob
from app.jobs.on_demand import (
    RETRY_AFTER,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.playoffs_feed import (
    CODES,
    FEED_ID,
    KIND,
    PlayoffsBuildError,
    PlayoffsFeeds,
    PlayoffsSources,
    build_playoffs_feed,
    finals_winner,
    group_series,
    postseason_days,
    reads_days,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import FEED_LIFETIME
from app.settings import Settings
from app.sources.division_standings import DivisionStandings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.postseason_leaders import LeaderEntry, PostseasonLeaders
from app.sources.postseason_scoreboard import PostseasonGame, SeriesState
from app.sources.scoreboard import ScoreboardGame
from app.sources.season_awards import AwardWinnerRef, SeasonAward, SeasonAwards
from app.sources.season_types import SeasonWindow
from app.sources.team_info import TeamInfo
from app.sources.team_players import RosterEntry
from app.sources.team_postseason import TeamPostseasonRecord
from app.sources.teams import TEAM_CODES
from app.storage.feeds import read_by_id
from app.storage.state import StateStore
from tests.jobs.test_standings_feed import league, team
from tests.jobs.test_team_feed import info

EAST = Conference.EAST
WEST = Conference.WEST
HOUR = dt.timedelta(hours=1)
SECOND = dt.timedelta(seconds=1)
DAY = dt.timedelta(days=1)
ALL = sorted(set(TEAM_CODES.values()))
EAST_CODES = ALL[:15]
WEST_CODES = ALL[15:]
PLAY_IN_WINDOW = SeasonWindow(
    season_type=5,
    start=dt.datetime(2027, 4, 14, 7, tzinfo=dt.UTC),
    end=dt.datetime(2027, 4, 18, 6, 59, tzinfo=dt.UTC),
)
POSTSEASON_WINDOW = SeasonWindow(
    season_type=3,
    start=dt.datetime(2027, 4, 18, 7, tzinfo=dt.UTC),
    end=dt.datetime(2027, 6, 21, 6, 59, tzinfo=dt.UTC),
)
TODAY = dt.date(2027, 4, 20)
BEFORE = dt.date(2027, 3, 1)
NOW = dt.datetime(2027, 4, 20, 15, 0, tzinfo=dt.UTC)
PLAY_IN_DAY = dt.datetime(2027, 4, 14, 23, 0, tzinfo=dt.UTC)
BASES = {
    1: dt.datetime(2027, 4, 19, 23, 0, tzinfo=dt.UTC),
    2: dt.datetime(2027, 5, 5, 23, 0, tzinfo=dt.UTC),
    3: dt.datetime(2027, 5, 20, 23, 0, tzinfo=dt.UTC),
    4: dt.datetime(2027, 6, 4, 23, 0, tzinfo=dt.UTC),
}
COMPETITIONS = {1: "RD16", 2: "QTR", 3: "SEMI", 4: "FINAL"}


# Fixtures


def codes_of(conference: Conference) -> list[str]:
    return EAST_CODES if conference is EAST else WEST_CODES


def seed(conference: Conference, number: int) -> str:
    return codes_of(conference)[number - 1]


def standings(
    season: int = 2027,
    played: bool = True,
    changes: dict[str, dict[str, Any]] | None = None,
) -> DivisionStandings:
    entries = []
    for conference in (EAST, WEST):
        for index, code in enumerate(codes_of(conference)):
            values: dict[str, Any] = {
                "conference": conference,
                "division": f"{conference.value}-{index // 5}",
                "division_order": index % 5 + 1,
                "conference_order": index + 1,
                "provider_order": index + 1 + (0 if conference is EAST else 15),
                "playoff_seed": index + 1,
                "wins": 60 - 3 * index if played else 0,
                "losses": 22 + 3 * index if played else 0,
                "clinch": Clinch.CONFERENCE if index == 0 and played else None,
            }
            values.update((changes or {}).get(code, {}))
            entries.append(team(code, **values))
    return league(*entries, season=season)


def board(
    game_id: str,
    home: str,
    away: str,
    start: dt.datetime,
    status: GameStatus = GameStatus.FINAL,
    scores: tuple[int, int] = (100, 90),
) -> ScoreboardGame:
    data: dict[str, Any] = {
        "id": game_id,
        "away": GameTeam(code=away, name=away.title(), city="City"),
        "home": GameTeam(code=home, name=home.title(), city="City"),
        "status": status,
        "start_time": start,
        "venue": "Example Arena",
        "broadcast": "Example Network",
    }
    if status is GameStatus.LIVE:
        data.update(period=2, clock="5:00")
    if status in (GameStatus.LIVE, GameStatus.FINAL):
        data["line_score"] = LineScore(away=[20, 20], home=[18, 20])
        data["score"] = Score(home=scores[0], away=scores[1])
    return ScoreboardGame.model_validate(data)


def post(
    game_id: str,
    home: str,
    away: str,
    start: dt.datetime,
    *,
    status: GameStatus = GameStatus.FINAL,
    scores: tuple[int, int] = (100, 90),
    season_type: int | None = 3,
    competition: str | None = None,
    note: str | None = None,
    period: int | None = 4,
    series: SeriesState | None = None,
) -> PostseasonGame:
    in_play = status in (GameStatus.LIVE, GameStatus.FINAL)
    return PostseasonGame(
        game=board(game_id, home, away, start, status, scores),
        season_type=season_type,
        competition_type=competition,
        note=note,
        period=period if in_play else None,
        series=series,
    )


def play_in_game(
    conference: Conference,
    kind: str,
    home: str,
    away: str,
    start: dt.datetime,
    status: GameStatus = GameStatus.FINAL,
    home_wins: bool = True,
) -> PostseasonGame:
    label = {
        "seven_eight": "7th Place vs 8th Place",
        "nine_ten": "9th Place vs 10th Place",
        "eighth_seed": "8th Seed Game",
    }[kind]
    return post(
        f"pi-{conference.value}-{kind}",
        home,
        away,
        start,
        status=status,
        scores=(100, 90) if home_wins else (90, 100),
        season_type=5,
        note=f"NBA Play-In - {conference.value.title()} - {label}",
    )


def play_in_of(conference: Conference, seven_wins: bool = True) -> list[PostseasonGame]:
    """The three play-in games: 7th hosts 8th, 9th hosts 10th, the loser of the
    first hosts the winner of the second (who is always the 9th place team)."""
    seven, eight, nine, ten = (seed(conference, n) for n in (7, 8, 9, 10))
    first_loser = eight if seven_wins else seven
    return [
        play_in_game(
            conference, "seven_eight", seven, eight, PLAY_IN_DAY, home_wins=seven_wins
        ),
        play_in_game(conference, "nine_ten", nine, ten, PLAY_IN_DAY),
        play_in_game(conference, "eighth_seed", first_loser, nine, PLAY_IN_DAY + DAY),
    ]


def series_games(
    top: str,
    bottom: str,
    round_: int,
    results: str,
    *,
    key: str,
    scheduled: int = 0,
    completed: bool | None = None,
    summary: str | None = None,
    label: str = "Example Round",
) -> list[PostseasonGame]:
    """The games of a series: results is one T (top wins) or B per final game."""
    games = []
    top_wins = bottom_wins = 0
    for number in range(1, len(results) + scheduled + 1):
        final = number <= len(results)
        if final:
            top_wins += results[number - 1] == "T"
            bottom_wins += results[number - 1] == "B"
        done = (
            max(top_wins, bottom_wins) == 4 if completed is None else completed
        ) and number == len(results)
        home, away = (top, bottom) if number in (1, 2, 5, 7) else (bottom, top)
        top_won = final and results[number - 1] == "T"
        scores = (100, 90) if (top_won == (home == top)) else (90, 100)
        games.append(
            post(
                f"{key}-{number}",
                home,
                away,
                BASES[round_] + (number - 1) * DAY,
                status=GameStatus.FINAL if final else GameStatus.SCHEDULED,
                scores=scores,
                competition=COMPETITIONS[round_],
                note=f"{label} - Game {number}",
                series=SeriesState(
                    summary=summary or f"{top} {top_wins}-{bottom_wins} {bottom}",
                    completed=done,
                    total_games=7,
                    wins={top: top_wins, bottom: bottom_wins},
                ),
            )
        )
    return games


def round_one(conference: Conference, results: str = "TTTT") -> list[PostseasonGame]:
    games = []
    for number, (high, low) in enumerate(((1, 8), (4, 5), (3, 6), (2, 7)), start=1):
        games += series_games(
            seed(conference, high),
            seed(conference, low),
            1,
            results,
            key=f"{conference.value}-r1-{number}",
        )
    return games


def round_two(conference: Conference, results: str = "TTTT") -> list[PostseasonGame]:
    return series_games(
        seed(conference, 1),
        seed(conference, 4),
        2,
        results,
        key=f"{conference.value}-r2-1",
    ) + series_games(
        seed(conference, 3),
        seed(conference, 2),
        2,
        results,
        key=f"{conference.value}-r2-2",
    )


def round_three(conference: Conference, results: str = "TTTT") -> list[PostseasonGame]:
    return series_games(
        seed(conference, 1),
        seed(conference, 3),
        3,
        results,
        key=f"{conference.value}-r3",
    )


def finals(results: str = "TTTT", **changes: Any) -> list[PostseasonGame]:
    return series_games(
        seed(EAST, 1), seed(WEST, 1), 4, results, key="finals", **changes
    )


def both(
    make: Callable[[Conference, str], list[PostseasonGame]], results: str = "TTTT"
) -> list[PostseasonGame]:
    return make(EAST, results) + make(WEST, results)


def play_ins() -> list[PostseasonGame]:
    return play_in_of(EAST) + play_in_of(WEST)


def player(player_id: str, **changes: Any) -> RosterEntry:
    values: dict[str, Any] = {
        "player_id": player_id,
        "first_name": "Example",
        "last_name": f"Player{player_id}",
        "display_name": f"Example Player{player_id}",
        "jersey": "1",
        "position_name": "Guard",
        "position_abbreviation": "G",
        "headshot_url": f"https://example.com/{player_id}.png",
    }
    return RosterEntry.model_validate(values | changes)


def roster(count: int = 12) -> dict[str, tuple[str, RosterEntry]]:
    return {str(n): (ALL[n % 30], player(str(n))) for n in range(1, count + 1)}


def build(
    games: list[PostseasonGame] | None = None,
    *,
    today: dt.date = TODAY,
    standing: DivisionStandings | None = None,
    **changes: Any,
) -> PlayoffsFeed:
    values: dict[str, Any] = {
        "season": 2027,
        "today": today,
        "play_in": PLAY_IN_WINDOW,
        "postseason": POSTSEASON_WINDOW,
        "standings": standing or standings(),
        "colors": dict.fromkeys(CODES, info()),
        "games": games or [],
        "players": roster(),
        "leaders": None,
        "awards": None,
        "champion_record": None,
    }
    return build_playoffs_feed(PlayoffsSources(**(values | changes)))


def bracket(feed: PlayoffsFeed) -> dict[SeriesId, Any]:
    return {series.id: series for series in feed.bracket}


def codes(side: Any) -> str | None:
    return None if side.team is None else str(side.team.code)


# State


def test_the_state_is_picture_in_the_preseason_before_the_play_in_window() -> None:
    feed = build(today=BEFORE, standing=standings(season=2026))

    assert feed.state is PlayoffsState.PICTURE
    assert feed.current_round is None and feed.champion is None
    assert feed.postseason_dates.first_date == dt.date(2027, 4, 14)
    assert feed.postseason_dates.last_date == dt.date(2027, 6, 21)
    assert [row.seed for row in feed.picture[0].rows] == [None] * 10
    assert [row.wins for row in feed.picture[0].rows] == [None] * 10
    assert all(row.clinch is None for row in feed.picture[0].rows)
    assert all(
        side.currently is None
        for series in feed.bracket
        for side in (series.top, series.bottom)
    )


def test_a_standing_with_no_game_is_the_preseason() -> None:
    feed = build(today=BEFORE, standing=standings(played=False))

    assert [row.games_behind for row in feed.picture[1].rows] == [None] * 10
    assert [row.team.code for row in feed.picture[1].rows] == WEST_CODES[:10]


def test_the_state_is_picture_in_the_regular_season_with_seeds_and_currently() -> None:
    feed = build(today=BEFORE)

    assert feed.state is PlayoffsState.PICTURE
    east = feed.picture[0]
    assert [row.seed for row in east.rows] == list(range(1, 11))
    assert [row.line for row in east.rows] == [
        None,
        None,
        None,
        None,
        None,
        "playoffs",
        None,
        None,
        None,
        "playin",
    ]
    assert (east.rows[0].wins, east.rows[0].losses) == (60, 22)
    assert east.rows[0].games_behind is None
    assert east.rows[1].games_behind == "3.0"
    assert east.rows[0].clinch is Clinch.CONFERENCE
    first = bracket(feed)[SeriesId.EAST_R1_1]
    assert codes(first.top) is None and first.top.currently is not None
    assert first.top.currently.code == seed(EAST, 1)
    assert first.bottom.currently is not None
    assert first.bottom.currently.code == seed(EAST, 8)
    assert (first.bottom.label.key.value, first.bottom.label.seed) == (
        "playin_winner",
        8,
    )
    slot = feed.play_in[1].games[0].top
    assert slot.team is None and slot.currently is not None
    assert (slot.label.place, slot.currently.code) == (7, seed(WEST, 7))
    assert feed.play_in[0].games[1].bottom.currently is not None


def test_the_state_is_playin_on_the_first_day_of_the_window_with_no_game_played() -> (
    None
):
    feed = build(today=dt.date(2027, 4, 14))

    assert feed.state is PlayoffsState.PLAYIN
    first = bracket(feed)[SeriesId.EAST_R1_1]
    assert codes(first.top) == seed(EAST, 1)
    assert first.top.seed == 1 and first.top.wins is None
    assert codes(first.bottom) is None and first.bottom.currently is None
    assert [e.status for e in feed.stages][:2] == [
        PlayoffStageStatus.NEXT,
        PlayoffStageStatus.UPCOMING,
    ]


def test_the_state_is_playin_after_play_in_games_with_round_one_not_started() -> None:
    feed = build(play_ins())

    assert feed.state is PlayoffsState.PLAYIN
    assert feed.current_round is None
    statuses = [entry.status for entry in feed.stages]
    assert statuses == [
        PlayoffStageStatus.COMPLETE,
        PlayoffStageStatus.NEXT,
        PlayoffStageStatus.UPCOMING,
        PlayoffStageStatus.UPCOMING,
        PlayoffStageStatus.UPCOMING,
    ]


def test_the_state_is_playoffs_once_a_round_one_game_is_live_with_current_round_1() -> (
    None
):
    live = post(
        "east-r1-1-1",
        seed(EAST, 1),
        seed(EAST, 8),
        BASES[1],
        status=GameStatus.LIVE,
        competition="RD16",
        note="East 1st Round - Game 1",
        series=SeriesState(
            summary="Series tied 0-0",
            completed=False,
            total_games=7,
            wins={seed(EAST, 1): 0, seed(EAST, 8): 0},
        ),
    )
    feed = build(play_ins() + [live])

    assert feed.state is PlayoffsState.PLAYOFFS
    assert feed.current_round == 1
    assert feed.stages[1].status is PlayoffStageStatus.IN_PROGRESS
    assert feed.stages[2].status is PlayoffStageStatus.NEXT


def test_the_current_round_is_2_when_round_one_is_complete_and_round_two_not_started() -> (
    None
):
    feed = build(play_ins() + both(round_one))

    assert feed.state is PlayoffsState.PLAYOFFS
    assert feed.current_round == 2
    assert feed.stages[1].status is PlayoffStageStatus.COMPLETE
    assert feed.stages[2].status is PlayoffStageStatus.NEXT


def test_the_current_round_is_2_while_round_two_is_in_progress() -> None:
    games = play_ins() + both(round_one) + round_two(EAST, "TT")

    feed = build(games)

    assert feed.current_round == 2
    assert [e.status for e in feed.stages][1:3] == [
        PlayoffStageStatus.COMPLETE,
        PlayoffStageStatus.IN_PROGRESS,
    ]


def test_the_current_round_is_3_during_the_conference_finals() -> None:
    games = play_ins() + both(round_one) + both(round_two) + round_three(EAST, "TT")

    feed = build(games)

    assert feed.current_round == 3
    assert feed.stages[3].status is PlayoffStageStatus.IN_PROGRESS
    assert feed.stages[4].status is PlayoffStageStatus.NEXT


def test_rounds_overlap_as_in_progress() -> None:
    games = play_ins() + round_one(EAST) + round_one(WEST, "TT") + round_two(EAST, "TT")
    games = [g for g in games if g.game.id != "x"]

    feed = build(games)

    assert [e.status for e in feed.stages][1:3] == [
        PlayoffStageStatus.IN_PROGRESS,
        PlayoffStageStatus.IN_PROGRESS,
    ]
    assert feed.stages[3].status is PlayoffStageStatus.NEXT


def test_the_state_is_finals_once_a_finals_game_is_scheduled_with_no_finals_line() -> (
    None
):
    games = (
        play_ins()
        + both(round_one)
        + both(round_two)
        + both(round_three)
        + finals("", scheduled=1)
    )

    feed = build(games)

    assert feed.state is PlayoffsState.FINALS
    assert feed.current_round is None
    assert feed.finals_game is None and feed.finals_summary is None
    assert feed.stages[3].status is PlayoffStageStatus.COMPLETE
    assert feed.stages[4].status is PlayoffStageStatus.NEXT


def everything(finals_results: str = "TTTT") -> list[PostseasonGame]:
    return (
        play_ins()
        + both(round_one)
        + both(round_two)
        + both(round_three)
        + finals(finals_results)
    )


def test_the_finals_line_is_set_after_game_3() -> None:
    feed = build(
        play_ins()
        + both(round_one)
        + both(round_two)
        + both(round_three)
        + finals("TBT", scheduled=1)
    )

    assert feed.state is PlayoffsState.FINALS
    assert feed.finals_game == 3
    assert feed.finals_summary == f"{seed(EAST, 1)} 2-1 {seed(WEST, 1)}"
    assert feed.stages[4].status is PlayoffStageStatus.IN_PROGRESS


def test_the_state_is_complete_once_the_finals_series_object_says_completed() -> None:
    feed = build(everything("TTBTT"))

    assert feed.state is PlayoffsState.COMPLETE
    assert feed.current_round is None
    assert feed.finals_game == 5
    assert feed.stages[4].status is PlayoffStageStatus.COMPLETE
    assert [e.status for e in feed.stages] == [PlayoffStageStatus.COMPLETE] * 5


# Stages


def test_the_stage_dates_are_the_first_and_last_us_eastern_dates_of_its_games() -> None:
    late_night = (
        BASES[1] + 7 * DAY + dt.timedelta(hours=2)
    )  # 01:00 Eastern the next day
    games = play_ins() + round_one(EAST)
    games.append(
        post(
            "late",
            seed(WEST, 1),
            seed(WEST, 8),
            late_night,
            competition="RD16",
            note="West 1st Round - Game 1",
            series=SeriesState(
                summary="x",
                completed=False,
                total_games=7,
                wins={seed(WEST, 1): 1, seed(WEST, 8): 0},
            ),
        )
    )

    feed = build(games)

    assert (feed.stages[0].first_date, feed.stages[0].last_date) == (
        dt.date(2027, 4, 14),
        dt.date(2027, 4, 15),
    )
    assert feed.stages[1].first_date == dt.date(2027, 4, 19)
    assert feed.stages[1].last_date == dt.date(2027, 4, 26)
    assert (feed.stages[2].first_date, feed.stages[2].last_date) == (None, None)


def test_the_play_in_is_next_in_picture_and_every_other_stage_is_upcoming() -> None:
    feed = build(today=BEFORE)

    assert [e.status for e in feed.stages] == [
        PlayoffStageStatus.NEXT,
        *[PlayoffStageStatus.UPCOMING] * 4,
    ]
    assert feed.stages[0].stage is PlayoffStage.PLAYIN
    assert all(e.first_date is None for e in feed.stages)


# Bracket


def test_the_bracket_has_the_15_series_in_order_in_every_state() -> None:
    for games, today in (
        ([], BEFORE),
        (play_ins(), TODAY),
        (everything(), TODAY),
    ):
        assert [s.id for s in build(games, today=today).bracket] == list(SeriesId)


def test_an_undecided_series_has_its_label_parts_and_no_team() -> None:
    feed = build(play_ins())
    series = bracket(feed)

    assert (
        series[SeriesId.EAST_R2_1].top.label.key.value,
        series[SeriesId.EAST_R2_1].top.label.series,
    ) == ("round_1_winner", 1)
    assert series[SeriesId.EAST_R2_1].bottom.label.series == 2
    assert series[SeriesId.WEST_R2_2].top.label.series == 3
    assert series[SeriesId.WEST_R2_2].bottom.label.series == 4
    assert series[SeriesId.EAST_R3].bottom.label.key.value == "round_2_winner"
    assert series[SeriesId.EAST_R3].bottom.label.series == 2
    assert [
        s.label.key.value
        for s in (series[SeriesId.FINALS].top, series[SeriesId.FINALS].bottom)
    ] == ["round_3_winner"] * 2
    assert [
        s.label.conference
        for s in (series[SeriesId.FINALS].top, series[SeriesId.FINALS].bottom)
    ] == [EAST, WEST]
    assert series[SeriesId.EAST_R3].top.label.series == 1
    assert series[SeriesId.EAST_R1_4].top.label.seed == 2
    assert series[SeriesId.EAST_R1_4].bottom.label.seed == 7
    for sid in (SeriesId.EAST_R2_1, SeriesId.EAST_R3, SeriesId.FINALS):
        assert (
            series[sid].top.team is None and series[sid].status is SeriesStatus.UPCOMING
        )
        assert series[sid].games == [] and series[sid].summary is None


def test_the_play_in_winners_fill_the_bracket_seeds_7_and_8_once_decided() -> None:
    feed = build(play_ins())

    series = bracket(feed)
    assert codes(series[SeriesId.EAST_R1_1].bottom) == seed(EAST, 8)
    assert codes(series[SeriesId.EAST_R1_4].bottom) == seed(EAST, 7)
    assert series[SeriesId.EAST_R1_4].bottom.seed == 7
    assert series[SeriesId.EAST_R1_1].bottom.seed == 8


def test_a_series_with_one_side_decided_shows_that_side_only() -> None:
    games = play_ins() + round_one(EAST)

    feed = build(games)

    series = bracket(feed)
    assert codes(series[SeriesId.EAST_R2_1].top) == seed(EAST, 1)
    assert codes(series[SeriesId.EAST_R2_1].bottom) == seed(EAST, 4)
    one = [g for g in games if not g.game.id.startswith("east-r1-2")]
    feed = build(one)
    series = bracket(feed)
    assert codes(series[SeriesId.EAST_R2_1].bottom) is None


def test_round_one_is_placed_by_seed_pair_with_the_lower_seed_on_top() -> None:
    games = play_ins() + round_one(EAST, "T")

    series = bracket(build(games))

    expected = {
        SeriesId.EAST_R1_1: (1, 8),
        SeriesId.EAST_R1_2: (4, 5),
        SeriesId.EAST_R1_3: (3, 6),
        SeriesId.EAST_R1_4: (2, 7),
    }
    for series_id, (top, bottom) in expected.items():
        assert (codes(series[series_id].top), codes(series[series_id].bottom)) == (
            seed(EAST, top),
            seed(EAST, bottom),
        )
        assert (series[series_id].top.seed, series[series_id].bottom.seed) == (
            top,
            bottom,
        )
        assert series[series_id].conference is EAST


def test_the_winner_of_the_7th_vs_8th_game_is_the_seed_7_of_round_one() -> None:
    games = play_in_of(EAST, seven_wins=False) + play_in_of(WEST)
    first = series_games(seed(EAST, 2), seed(EAST, 8), 1, "TTTT", key="east-r1-4")

    series = bracket(build(games + first))

    r1_4 = series[SeriesId.EAST_R1_4]
    assert (codes(r1_4.top), codes(r1_4.bottom)) == (seed(EAST, 2), seed(EAST, 8))
    assert r1_4.bottom.seed == 7


def test_later_rounds_are_placed_by_their_feeders_and_the_finals_has_the_east_on_top() -> (
    None
):
    series = bracket(build(everything()))

    assert (
        codes(series[SeriesId.EAST_R2_1].top),
        codes(series[SeriesId.EAST_R2_1].bottom),
    ) == (seed(EAST, 1), seed(EAST, 4))
    assert (
        codes(series[SeriesId.WEST_R2_2].top),
        codes(series[SeriesId.WEST_R2_2].bottom),
    ) == (seed(WEST, 3), seed(WEST, 2))
    assert (
        codes(series[SeriesId.WEST_R3].top),
        codes(series[SeriesId.WEST_R3].bottom),
    ) == (seed(WEST, 1), seed(WEST, 3))
    final = series[SeriesId.FINALS]
    assert (codes(final.top), codes(final.bottom)) == (seed(EAST, 1), seed(WEST, 1))
    assert final.conference is None and final.round == 4


def test_a_decided_feeder_fills_the_next_series_side_before_it_has_games() -> None:
    feed = build(play_ins() + round_one(EAST))

    series = bracket(feed)
    assert codes(series[SeriesId.EAST_R3].top) is None
    assert codes(series[SeriesId.EAST_R2_2].top) == seed(EAST, 3)
    assert series[SeriesId.EAST_R2_2].top.seed == 3
    assert series[SeriesId.EAST_R2_2].top.wins is None


def test_wins_summary_and_status_come_from_the_series_object_not_the_games() -> None:
    games = play_ins() + series_games(
        seed(EAST, 1),
        seed(EAST, 8),
        1,
        "TTB",
        key="east-r1-1",
        summary="Series object text",
    )
    last = games[-1]
    games[-1] = last.model_copy(
        update={
            "series": SeriesState(
                summary="Series object text",
                completed=False,
                total_games=7,
                wins={seed(EAST, 1): 3, seed(EAST, 8): 3},
            )
        }
    )

    series = bracket(build(games))[SeriesId.EAST_R1_1]

    assert (series.top.wins, series.bottom.wins) == (3, 3)
    assert series.summary == "Series object text"
    assert series.status is SeriesStatus.IN_PROGRESS
    assert series.winner is None


def test_a_series_with_4_games_scheduled_lists_4_and_keeps_its_summary() -> None:
    games = play_ins() + series_games(
        seed(EAST, 1),
        seed(EAST, 8),
        1,
        "TBTB",
        key="east-r1-1",
        summary="Series tied 2-2",
    )

    series = bracket(build(games))[SeriesId.EAST_R1_1]

    assert [g.number for g in series.games] == [1, 2, 3, 4]
    assert series.summary == "Series tied 2-2"


def test_a_not_started_series_has_wins_0_from_the_series_object_and_null_without_one() -> (
    None
):
    games = play_ins() + series_games(
        seed(EAST, 1), seed(EAST, 8), 1, "", key="east-r1-1", scheduled=1
    )
    plain = post(
        "east-r1-2-1",
        seed(EAST, 4),
        seed(EAST, 5),
        BASES[1],
        status=GameStatus.SCHEDULED,
        competition="RD16",
        note="East 1st Round - Game 1",
    )

    series = bracket(build(games + [plain]))

    started = series[SeriesId.EAST_R1_1]
    assert (started.top.wins, started.bottom.wins) == (0, 0)
    assert started.status is SeriesStatus.UPCOMING
    unseen = series[SeriesId.EAST_R1_2]
    assert (unseen.top.wins, unseen.bottom.wins) == (None, None)
    assert unseen.summary is None


def test_a_complete_series_has_its_winner() -> None:
    series = bracket(build(play_ins() + round_one(EAST, "TBTTT")))[SeriesId.EAST_R1_1]

    assert series.status is SeriesStatus.COMPLETE
    assert series.winner == seed(EAST, 1)
    assert (series.top.wins, series.bottom.wins) == (4, 1)


def test_an_overtime_game_is_flagged_from_the_period() -> None:
    games = play_ins() + series_games(
        seed(EAST, 1), seed(EAST, 8), 1, "TT", key="east-r1-1"
    )
    games[-2] = games[-2].model_copy(update={"period": 5})
    games[-1] = games[-1].model_copy(update={"period": 4})

    played = bracket(build(games))[SeriesId.EAST_R1_1].games

    assert [g.overtime for g in played] == [True, False]


def test_a_canceled_game_is_not_listed() -> None:
    games = play_ins() + series_games(
        seed(EAST, 1), seed(EAST, 8), 1, "TT", key="east-r1-1", scheduled=1
    )
    games[-1] = games[-1].model_copy(
        update={
            "game": games[-1].game.model_copy(update={"status": GameStatus.CANCELED})
        }
    )

    played = bracket(build(games))[SeriesId.EAST_R1_1].games

    assert [g.number for g in played] == [1, 2]


def test_a_repeated_game_id_keeps_one_game() -> None:
    games = play_ins() + series_games(
        seed(EAST, 1), seed(EAST, 8), 1, "TT", key="east-r1-1"
    )

    played = bracket(build(games + games))[SeriesId.EAST_R1_1].games

    assert len(played) == 2


def test_the_series_games_carry_the_date_the_start_time_the_venue_and_the_winner() -> (
    None
):
    games = play_ins() + series_games(
        seed(EAST, 1), seed(EAST, 8), 1, "TB", key="east-r1-1"
    )

    played = bracket(build(games))[SeriesId.EAST_R1_1].games

    first = played[0]
    assert (first.id, first.number, first.date) == (
        "east-r1-1-1",
        1,
        dt.date(2027, 4, 19),
    )
    assert first.venue == "Example Arena" and first.broadcast == "Example Network"
    assert first.winner is not None and first.winner.value == "home"
    assert first.home.code == seed(EAST, 1) and first.detail_available is False
    assert played[1].winner is not None and played[1].winner.value == "away"


def test_a_late_game_has_the_us_eastern_date() -> None:
    games = play_ins() + [
        post(
            "g",
            seed(EAST, 1),
            seed(EAST, 8),
            dt.datetime(2027, 4, 20, 2, 30, tzinfo=dt.UTC),
            competition="RD16",
            note="East 1st Round - Game 1",
        )
    ]

    played = bracket(build(games))[SeriesId.EAST_R1_1].games

    assert played[0].date == dt.date(2027, 4, 19)


def failing(games: list[PostseasonGame], message: str) -> None:
    with pytest.raises(PlayoffsBuildError, match=message):
        build(games)


def test_it_fails_on_a_seed_pair_outside_the_table() -> None:
    failing(
        play_ins()
        + series_games(
            seed(EAST, 1), seed(EAST, 5), 1, "T", key="x", label="East 1st Round"
        ),
        "seeds outside the bracket",
    )


def test_it_fails_on_a_round_one_series_that_mixes_the_conferences() -> None:
    failing(
        play_ins() + series_games(seed(EAST, 1), seed(WEST, 8), 1, "T", key="x"),
        "mixes the conferences",
    )


def test_it_fails_on_a_team_outside_its_feeder() -> None:
    failing(
        play_ins()
        + round_one(EAST)
        + series_games(seed(EAST, 1), seed(EAST, 3), 2, "T", key="y"),
        "is not fed by its series",
    )


def test_it_fails_on_two_series_in_one_slot() -> None:
    # Two teams share the standings seed 2, so both series map to the same slot.
    entries = standings(changes={seed(EAST, 3): {"playoff_seed": 2}})
    games = series_games(seed(EAST, 2), seed(EAST, 7), 1, "T", key="a") + series_games(
        seed(EAST, 3), seed(EAST, 7), 1, "T", key="b"
    )

    with pytest.raises(PlayoffsBuildError, match="two series in the slot east-r1-4"):
        build(play_ins() + games, standing=entries)


def test_it_fails_on_an_unknown_competition_type() -> None:
    games = series_games(seed(EAST, 1), seed(EAST, 8), 1, "T", key="a")
    games[0] = games[0].model_copy(update={"competition_type": "XYZ"})

    failing(play_ins() + games, "unknown competition type 'XYZ'")


def test_it_fails_on_a_note_without_a_game_number() -> None:
    games = series_games(seed(EAST, 1), seed(EAST, 8), 1, "T", key="a")
    games[0] = games[0].model_copy(update={"note": "East 1st Round"})

    failing(play_ins() + games, "note without a game number")


def test_it_fails_on_a_team_outside_the_league() -> None:
    guest = GameTeam(code="ZZZ", name="Guest", city="Elsewhere", guest=True)
    games = series_games(seed(EAST, 1), seed(EAST, 8), 1, "T", key="a")
    games[0] = games[0].model_copy(
        update={"game": games[0].game.model_copy(update={"away": guest})}
    )

    failing(play_ins() + games, "team outside the league")


def placeholder(game: PostseasonGame, side: str = "away") -> PostseasonGame:
    team = GameTeam(code=None, name="Winner of 9th vs 10th", city="TBD", guest=True)
    return game.model_copy(
        update={
            "game": game.game.model_copy(
                update={
                    "status": GameStatus.SCHEDULED,
                    "score": None,
                    "line_score": None,
                    side: team,
                }
            ),
            "period": None,
        }
    )


def test_a_scheduled_8th_seed_game_with_a_placeholder_side_is_ignored() -> None:
    games = play_in_of(EAST) + play_in_of(WEST)
    index = next(i for i, g in enumerate(games) if g.game.id == "pi-east-eighth_seed")
    games[index] = placeholder(games[index])

    feed = build(games)

    series = bracket(feed)
    assert codes(series[SeriesId.EAST_R1_1].top) == seed(EAST, 1)
    assert codes(series[SeriesId.EAST_R1_1].bottom) is None
    assert codes(series[SeriesId.EAST_R1_4].bottom) == seed(EAST, 7)


def test_a_scheduled_round_one_game_against_a_placeholder_is_ignored() -> None:
    games = play_ins() + series_games(
        seed(EAST, 1), seed(EAST, 8), 1, "TT", key="east-r1-1", scheduled=1
    )
    games[-1] = placeholder(games[-1])

    played = bracket(build(games))[SeriesId.EAST_R1_1].games

    assert [g.number for g in played] == [1, 2]


def test_a_live_game_with_a_placeholder_side_still_fails() -> None:
    games = series_games(seed(EAST, 1), seed(EAST, 8), 1, "T", key="a", scheduled=1)
    broken = placeholder(games[-1])
    games[-1] = broken.model_copy(
        update={"game": broken.game.model_copy(update={"status": GameStatus.LIVE})}
    )

    failing(play_ins() + games, "team outside the league")


def test_it_fails_on_a_team_missing_from_the_standings() -> None:
    entries = standings()
    del entries.teams[seed(EAST, 7)]

    with pytest.raises(PlayoffsBuildError, match="has no standing"):
        build(play_ins(), standing=entries)


def test_it_fails_on_a_complete_series_with_tied_wins() -> None:
    games = series_games(seed(EAST, 1), seed(EAST, 8), 1, "TB", key="a", completed=True)

    failing(play_ins() + games, "complete with tied wins")


# Play-in


def test_before_any_game_the_play_in_slots_carry_places_7_to_10_and_the_games_their_date() -> (
    None
):
    games = [
        play_in_game(
            EAST,
            "seven_eight",
            seed(EAST, 7),
            seed(EAST, 8),
            PLAY_IN_DAY,
            GameStatus.SCHEDULED,
        )
    ]

    feed = build(games)

    first = feed.play_in[0].games[0]
    assert (first.top.label.place, first.bottom.label.place) == (7, 8)
    assert (first.top.team.code if first.top.team else None) == seed(EAST, 7)
    assert first.game is not None and first.game.date == dt.date(2027, 4, 14)
    assert first.game.start_time == PLAY_IN_DAY
    assert first.outcome is None
    second = feed.play_in[0].games[1]
    assert (second.top.label.place, second.bottom.label.place) == (9, 10)
    assert second.game is None and second.top.team is None
    eighth = feed.play_in[0].games[2]
    assert [
        eighth.top.label.key.value,
        eighth.top.label.game.value if eighth.top.label.game else None,
    ] == ["loser_of", "seven_eight"]
    assert [
        eighth.bottom.label.key.value,
        eighth.bottom.label.game.value if eighth.bottom.label.game else None,
    ] == ["winner_of", "nine_ten"]
    assert eighth.top.team is None and eighth.bottom.team is None


def test_after_each_game_the_play_in_has_its_outcome() -> None:
    feed = build(play_ins())

    games = feed.play_in[0].games
    assert [
        (g.outcome.seed, g.outcome.loser_out) if g.outcome else None for g in games
    ] == [
        (7, False),
        (None, True),
        (8, True),
    ]


def test_the_8th_seed_game_takes_the_loser_of_7th_vs_8th_and_the_winner_of_9th_vs_10th() -> (
    None
):
    feed = build(play_ins())

    eighth = feed.play_in[0].games[2]
    assert eighth.top.team is not None and eighth.top.team.code == seed(EAST, 8)
    assert eighth.bottom.team is not None and eighth.bottom.team.code == seed(EAST, 9)
    assert eighth.game is not None and eighth.game.home.code == seed(EAST, 8)


def test_the_8th_seed_slots_stay_empty_until_their_feeder_game_is_final() -> None:
    games = [
        play_in_game(EAST, "seven_eight", seed(EAST, 7), seed(EAST, 8), PLAY_IN_DAY),
        play_in_game(
            EAST,
            "nine_ten",
            seed(EAST, 9),
            seed(EAST, 10),
            PLAY_IN_DAY,
            GameStatus.SCHEDULED,
        ),
    ]

    eighth = build(games).play_in[0].games[2]

    assert eighth.top.team is not None
    assert eighth.bottom.team is None


def test_it_fails_on_an_unknown_play_in_note() -> None:
    game = play_in_game(EAST, "seven_eight", seed(EAST, 7), seed(EAST, 8), PLAY_IN_DAY)
    game = game.model_copy(update={"note": "NBA Play-In - East - Mystery Game"})

    failing([game], "unknown note")


def test_it_fails_on_a_play_in_game_without_a_note() -> None:
    game = play_in_game(EAST, "seven_eight", seed(EAST, 7), seed(EAST, 8), PLAY_IN_DAY)

    failing([game.model_copy(update={"note": None})], "unknown note")


def test_it_fails_on_two_play_in_games_of_one_kind() -> None:
    first = play_in_game(EAST, "seven_eight", seed(EAST, 7), seed(EAST, 8), PLAY_IN_DAY)
    second = first.model_copy(
        update={"game": first.game.model_copy(update={"id": "other"})}
    )

    failing([first, second], "two play-in games of the kind seven_eight")


# Champion


def test_the_champion_is_null_until_the_finals_series_is_complete() -> None:
    feed = build(everything("TTT"))

    assert feed.state is PlayoffsState.FINALS
    assert feed.champion is None


def test_the_champion_has_the_result_the_dates_the_record_and_the_differential() -> (
    None
):
    record = TeamPostseasonRecord(overall="16-6", home="9-2", road="7-4")

    feed = build(everything("TBTTT"), champion_record=record)

    champion = feed.champion
    assert champion is not None
    assert champion.team.code == seed(EAST, 1)
    assert (champion.wins, champion.losses) == (4, 1)
    assert (champion.first_date, champion.last_date) == (
        dt.date(2027, 6, 4),
        dt.date(2027, 6, 8),
    )
    assert (champion.record, champion.home, champion.road) == ("16-6", "9-2", "7-4")
    assert champion.point_differential.value == "+150"
    assert champion.point_differential.non_negative is True


def test_the_point_differential_counts_postseason_games_only() -> None:
    games = everything("TBTTT")
    # A play-in game of the champion lost by 100 points must not count.
    index = next(i for i, g in enumerate(games) if g.game.id == "pi-west-nine_ten")
    games[index] = post(
        "pi-west-nine_ten",
        seed(EAST, 1),
        seed(WEST, 10),
        PLAY_IN_DAY,
        season_type=5,
        scores=(0, 100),
        note="NBA Play-In - West - 9th Place vs 10th Place",
    )

    feed = build(games)

    assert feed.champion is not None
    assert feed.champion.point_differential.value == "+150"


def test_the_point_differential_is_signed_with_the_minus_sign_when_negative() -> None:
    flipped = [
        g.model_copy(
            update={
                "game": g.game.model_copy(
                    update={
                        "score": Score(home=g.game.score.away, away=g.game.score.home)
                    }
                )
            }
        )
        if g.season_type == 3 and g.game.score is not None
        else g
        for g in everything("TBTTT")
    ]

    feed = build(flipped)

    assert feed.champion is not None
    assert feed.champion.point_differential.value == "−150"
    assert feed.champion.point_differential.non_negative is False


def test_the_champion_record_values_are_null_when_the_record_read_failed() -> None:
    champion = build(everything()).champion

    assert champion is not None
    assert (champion.record, champion.home, champion.road) == (None, None, None)


# Leaders


def leaders_source(count: int = 5, category_count: int = 9) -> PostseasonLeaders:
    return PostseasonLeaders(
        categories={
            category: [
                LeaderEntry(player_id=str(n), value=f"{30 - n}.0")
                for n in range(1, count + 1)
            ]
            for category in list(LeaderCategory)[:category_count]
        }
    )


def test_the_leaders_have_nine_categories_in_order_with_five_leaders_and_ranks() -> (
    None
):
    feed = build(leaders=leaders_source(7))

    assert feed.leaders is not None
    assert [g.category for g in feed.leaders] == list(LeaderCategory)
    assert all(
        [leader.rank for leader in g.leaders] == [1, 2, 3, 4, 5] for g in feed.leaders
    )
    first = feed.leaders[0].leaders[0]
    assert (first.player_id, first.name, first.value) == (
        "1",
        "Example Player1",
        "29.0",
    )
    assert first.team_code == ALL[1]
    assert str(first.photo_url) == "https://example.com/1.png"


def test_a_category_with_fewer_leaders_has_the_ranks_it_has() -> None:
    feed = build(leaders=leaders_source(2))

    assert feed.leaders is not None
    assert [leader.rank for leader in feed.leaders[3].leaders] == [1, 2]


def test_a_leader_on_no_roster_is_left_out_with_its_rank_gap() -> None:
    players = roster()
    del players["2"]

    feed = build(leaders=leaders_source(), players=players)

    assert feed.leaders is not None
    assert [leader.rank for leader in feed.leaders[0].leaders] == [1, 3, 4, 5]


def test_a_leader_with_no_photo_has_a_null_photo() -> None:
    players = roster()
    players["1"] = (ALL[1], player("1", headshot_url=None))

    feed = build(leaders=leaders_source(), players=players)

    assert feed.leaders is not None
    assert feed.leaders[0].leaders[0].photo_url is None


def test_the_leaders_are_null_when_the_read_failed_or_no_category_has_a_leader() -> (
    None
):
    assert build(leaders=None).leaders is None
    assert build(leaders=PostseasonLeaders(categories={})).leaders is None
    assert build(leaders=leaders_source(), players={}).leaders is None


# Awards


def award(
    code: AwardCode,
    ids: list[str],
    team: int | None = None,
    team_code: str | None = None,
) -> SeasonAward:
    return SeasonAward(
        code=code,
        team=team,
        winners=[AwardWinnerRef(player_id=n, team_code=team_code) for n in ids],
    )


def test_the_awards_come_in_code_order_with_team_awards_of_up_to_five() -> None:
    source = SeasonAwards(
        awards=[
            award(AwardCode.ALL_NBA, ["1", "2", "3", "4", "5"], 2),
            award(AwardCode.ALL_NBA, ["6"], 1),
            award(AwardCode.MVP, ["7"]),
        ]
    )

    feed = build(awards=source)

    assert feed.awards is not None
    assert [(a.code, a.team) for a in feed.awards] == [
        (AwardCode.MVP, None),
        (AwardCode.ALL_NBA, 1),
        (AwardCode.ALL_NBA, 2),
    ]
    assert len(feed.awards[2].winners) == 5


def test_an_award_with_no_winner_on_a_roster_is_not_in_the_feed() -> None:
    source = SeasonAwards(
        awards=[award(AwardCode.MVP, ["99"]), award(AwardCode.DPOY, ["99", "3"])]
    )

    feed = build(awards=source)

    assert feed.awards is not None
    assert [a.code for a in feed.awards] == [AwardCode.DPOY]
    assert [w.player_id for w in feed.awards[0].winners] == ["3"]


def test_the_award_team_is_the_award_team_else_the_roster_team() -> None:
    source = SeasonAwards(
        awards=[
            award(AwardCode.MVP, ["3"]),
            award(AwardCode.DPOY, ["3"], team_code="BOS"),
        ]
    )

    feed = build(awards=source)

    assert feed.awards is not None
    assert [w.winners[0].team_code for w in feed.awards] == [ALL[3], "BOS"]


def test_a_winner_with_no_photo_has_a_null_photo() -> None:
    players = roster()
    players["3"] = (ALL[3], player("3", headshot_url=None))

    feed = build(
        awards=SeasonAwards(awards=[award(AwardCode.MVP, ["3"])]), players=players
    )

    assert feed.awards is not None
    assert feed.awards[0].winners[0].photo_url is None


def test_the_awards_are_null_when_the_read_failed_or_none_has_a_winner() -> None:
    assert build(awards=None).awards is None
    assert build(awards=SeasonAwards(awards=[])).awards is None
    assert (
        build(awards=SeasonAwards(awards=[award(AwardCode.MVP, ["99"])])).awards is None
    )


# Helpers and errors


def test_the_postseason_days_cover_both_windows_with_no_repeats() -> None:
    days = postseason_days(PLAY_IN_WINDOW, POSTSEASON_WINDOW)

    assert days[0] == dt.date(2027, 4, 14)
    assert days[-1] == dt.date(2027, 6, 21)
    assert len(days) == len(set(days)) == 69
    assert days == sorted(days)


def test_the_days_are_read_from_the_first_day_of_the_play_in_window() -> None:
    assert not reads_days(dt.date(2027, 4, 13), PLAY_IN_WINDOW)
    assert reads_days(dt.date(2027, 4, 14), PLAY_IN_WINDOW)


def test_group_series_keeps_only_postseason_games_by_round_and_pair() -> None:
    games = play_ins() + series_games(seed(EAST, 1), seed(EAST, 8), 1, "TT", key="a")

    groups = group_series(games)

    assert list(groups) == [(1, frozenset({seed(EAST, 1), seed(EAST, 8)}))]
    assert [g.game.id for g in groups[next(iter(groups))]] == ["a-1", "a-2"]


def test_finals_winner_is_the_team_with_more_wins_of_a_completed_finals_series() -> (
    None
):
    assert finals_winner(everything("TTBTT")) == seed(EAST, 1)
    assert finals_winner(everything("BBTBB")) == seed(WEST, 1)
    assert finals_winner(everything("TT")) is None
    assert finals_winner(play_ins()) is None


def test_an_invalid_feed_is_wrapped_in_a_build_error_with_the_first_location() -> None:
    entries = standings(changes={seed(EAST, 1): {"wins": -1}})

    with pytest.raises(
        PlayoffsBuildError, match="invalid feed: 1 errors, first at picture"
    ):
        build(standing=entries, today=BEFORE)


def test_the_picture_rows_follow_the_conference_order() -> None:
    entries = standings(
        changes={seed(EAST, 3): {"playoff_seed": 1}, seed(EAST, 1): {"playoff_seed": 3}}
    )

    feed = build(today=BEFORE, standing=entries)

    assert [r.team.code for r in feed.picture[0].rows][:3] == [
        seed(EAST, 3),
        seed(EAST, 2),
        seed(EAST, 1),
    ]
    assert feed.picture[0].rows[0].team.colors.primary == "#007ac1"


def test_a_team_with_no_info_has_null_colors() -> None:
    feed = build(today=BEFORE, colors={})

    assert feed.picture[0].rows[0].team.colors.primary is None


# Group 2: the kind


DATABASE_NOW = dt.datetime(2027, 4, 20, 15, 0, tzinfo=dt.UTC)


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027
        self.ready = True

    def current_season(self) -> int | None:
        return self.season

    def rosters_ready(self) -> bool:
        return self.ready

    def roster_entries(self) -> dict[str, list[RosterEntry]]:
        return {ALL[n % 30]: [player(str(n))] for n in range(1, 13)}

    def player_team(self, player_id: str) -> str | None:
        return ALL[int(player_id) % 30]


class FakeGames:
    def __init__(self) -> None:
        self.final: list[ScoreboardGame] = []
        self.loaded: list[ScoreboardGame] = []

    def final_games(self) -> list[ScoreboardGame]:
        return list(self.final)

    def loaded_games(self) -> list[ScoreboardGame]:
        return list(self.loaded)


class PlayoffsKit:
    """The playoffs kind over one client and one clock, with fake adapters that
    count their calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.calls: list[str] = []
        self.failing: set[str] = set()
        self.days: dict[dt.date, list[PostseasonGame]] = {}
        self.standing = standings()
        self.stars = FakeStars()
        self.games = FakeGames()
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.playoffs = PlayoffsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(GamesJob, self.games),
            cast(StarsJob, self.stars),
            fetch_season_type=self.fetch_season_type,
            fetch_postseason_games=self.fetch_postseason_games,
            fetch_division_standings=self.fetch_division_standings,
            fetch_team_info=self.fetch_team_info,
            fetch_postseason_leaders=self.fetch_postseason_leaders,
            fetch_season_awards=self.fetch_season_awards,
            fetch_team_postseason_record=self.fetch_team_postseason_record,
        )

    def read(self, name: str) -> None:
        self.calls.append(name)
        if name in self.failing:
            raise SourceError("test", f"{name} is down")

    def called(self, prefix: str) -> int:
        return sum(1 for name in self.calls if name.startswith(prefix))

    async def fetch_season_type(
        self, client: SourceClient, season: int, season_type: int, settings: Settings
    ) -> SeasonWindow:
        self.read(f"type/{season_type}")
        return PLAY_IN_WINDOW if season_type == 5 else POSTSEASON_WINDOW

    async def fetch_postseason_games(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[PostseasonGame]:
        self.read(f"day/{day.isoformat()}")
        return list(self.days.get(day, []))

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings
    ) -> DivisionStandings:
        self.read("standings")
        return self.standing

    async def fetch_team_info(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamInfo:
        self.read(f"info/{code}")
        return info()

    async def fetch_postseason_leaders(
        self, client: SourceClient, season: int, settings: Settings
    ) -> PostseasonLeaders:
        self.read("leaders")
        return leaders_source()

    async def fetch_season_awards(
        self, client: SourceClient, season: int, settings: Settings
    ) -> SeasonAwards:
        self.read("awards")
        return SeasonAwards(awards=[award(AwardCode.MVP, ["1"])])

    async def fetch_team_postseason_record(
        self, client: SourceClient, team: str, season: int, settings: Settings
    ) -> TeamPostseasonRecord:
        self.read(f"record/{team}")
        return TeamPostseasonRecord(overall="16-6", home="9-2", road="7-4")

    def load(self, games: list[PostseasonGame]) -> None:
        self.days = {}
        for game in games:
            day = game.game.start_time.astimezone(
                dt.timezone(dt.timedelta(hours=-4))
            ).date()
            self.days.setdefault(day, []).append(game)

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    def stored(self) -> PlayoffsFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else PlayoffsFeed.model_validate_json(body)

    def last_build(self) -> dt.datetime | None:
        state = self.store.feed_build(KIND, FEED_ID)
        return None if state is None else state.last_build


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> PlayoffsKit:
    return PlayoffsKit(tmp_path)


@pytest.mark.anyio
async def test_an_id_other_than_league_answers_unknown_with_no_build(
    kit: PlayoffsKit, tmp_path: Path
) -> None:
    for feed_id in ("LEAGUE", "playoffs", ""):
        assert kit.playoffs.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, feed_id)

    assert kit.playoffs.check("league") is IdStatus.KNOWN
    assert kit.calls == []
    assert not (tmp_path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_it_answers_not_ready_with_no_season_or_rosters_not_ready_and_nothing_stored(
    kit: PlayoffsKit,
) -> None:
    kit.stars.season = None

    assert kit.playoffs.check(FEED_ID) is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    kit.stars.season = 2027
    kit.stars.ready = False
    assert kit.playoffs.check(FEED_ID) is IdStatus.NOT_READY
    assert kit.calls == []

    kit.stars.ready = True
    await kit.serve()
    kit.stars.season = None
    kit.stars.ready = False

    assert kit.playoffs.check(FEED_ID) is IdStatus.KNOWN


@pytest.mark.anyio
async def test_no_feed_is_built_stored_or_fetched_without_a_request(
    kit: PlayoffsKit,
) -> None:
    await kit.settle()

    assert kit.calls == []
    assert kit.stored() is None
    assert kit.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_a_request_builds_and_stores_the_feed_and_a_second_request_reads_storage(
    kit: PlayoffsKit,
) -> None:
    first = await kit.serve()
    calls = list(kit.calls)
    second = await kit.serve(NOW + 30 * SECOND)

    feed = PlayoffsFeed.model_validate_json(first)
    assert (feed.season, feed.state) == ("2026-27", PlayoffsState.PLAYIN)
    assert feed.leaders is not None and feed.awards is not None
    assert second == first
    assert kit.calls == calls
    assert (kit.path / "feeds" / KIND / "league.json").exists()
    assert kit.last_build() == NOW
    assert kit.called("type/") == 2 and kit.called("info/") == 30
    assert kit.called("standings") == 1 and kit.called("leaders") == 1
    assert kit.called("awards") == 1


@pytest.mark.anyio
async def test_no_scoreboard_day_is_read_before_the_play_in_window(
    kit: PlayoffsKit,
) -> None:
    kit.clock[0] = dt.datetime(2027, 4, 13, 20, 0, tzinfo=dt.UTC)

    feed = PlayoffsFeed.model_validate_json(await kit.serve())

    assert feed.state is PlayoffsState.PICTURE
    assert kit.called("day/") == 0


@pytest.mark.anyio
async def test_every_day_of_both_windows_is_read_inside_the_window(
    kit: PlayoffsKit,
) -> None:
    await kit.serve()

    days = sorted(name for name in kit.calls if name.startswith("day/"))
    assert len(days) == 69
    assert days[0] == "day/2027-04-14" and days[-1] == "day/2027-06-21"


@pytest.mark.anyio
@pytest.mark.parametrize("failing", ["type/5", "type/3", "standings", "day/2027-05-01"])
async def test_a_failed_season_type_standings_or_day_read_answers_unavailable_and_is_not_retried_for_10_minutes(
    kit: PlayoffsKit, failing: str
) -> None:
    kit.failing.add(failing)

    with pytest.raises(FeedUnavailableError):
        await kit.serve()
    await kit.settle()
    attempts = kit.called(failing)
    kit.clock[0] = NOW + RETRY_AFTER - SECOND
    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.called(failing) == attempts == 1
    assert [f.feed_id for f in kit.store.failed_feed_builds()] == ["league"]
    assert kit.stored() is None
    kit.failing.clear()
    body = await kit.serve(NOW + RETRY_AFTER)
    assert PlayoffsFeed.model_validate_json(body).state is PlayoffsState.PLAYIN


@pytest.mark.anyio
async def test_a_failed_rebuild_of_a_stale_feed_keeps_and_serves_the_stored_feed(
    kit: PlayoffsKit,
) -> None:
    first = await kit.serve()
    kit.failing.add("standings")

    body = await kit.serve(NOW + FEED_LIFETIME)
    await kit.settle()

    assert body == first
    assert kit.called("standings") == 2
    assert kit.stored() is not None
    assert kit.last_build() == NOW


@pytest.mark.anyio
@pytest.mark.parametrize("failing", ["leaders", "awards", "info/ATL"])
async def test_a_failed_leaders_awards_or_team_info_read_only_nulls_its_part(
    kit: PlayoffsKit, failing: str
) -> None:
    kit.failing.add(failing)

    feed = PlayoffsFeed.model_validate_json(await kit.serve())

    assert (feed.leaders is None) == (failing == "leaders")
    assert (feed.awards is None) == (failing == "awards")
    atlanta = next(r for t in feed.picture for r in t.rows if r.team.code == "ATL")
    assert (atlanta.team.colors.primary is None) == (failing == "info/ATL")


@pytest.mark.anyio
async def test_the_postseason_record_is_read_only_for_the_champion_of_a_complete_finals(
    kit: PlayoffsKit,
) -> None:
    kit.load(everything("TTT"))
    await kit.serve()
    assert kit.called("record/") == 0

    kit.load(everything("TTTT"))
    await kit.serve(NOW + FEED_LIFETIME)

    assert kit.called("record/") == 1 and kit.called(f"record/{seed(EAST, 1)}") == 1
    stored = kit.stored()
    assert stored is not None and stored.champion is not None
    assert stored.champion.record == "16-6"


@pytest.mark.anyio
async def test_a_failed_champion_record_read_only_nulls_the_record(
    kit: PlayoffsKit,
) -> None:
    kit.load(everything())
    kit.failing.add(f"record/{seed(EAST, 1)}")

    champion = PlayoffsFeed.model_validate_json(await kit.serve()).champion

    assert champion is not None
    assert (champion.record, champion.home, champion.road) == (None, None, None)


def a_game_id(kit: PlayoffsKit) -> str:
    stored = kit.stored()
    assert stored is not None
    return stored.play_in[0].games[0].game.id  # type: ignore[union-attr]


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_a_final_postseason_game_of_the_feed_plus_1_hour_and_stale_at_it(
    kit: PlayoffsKit,
) -> None:
    kit.load(play_ins())
    await kit.serve()
    game_id = a_game_id(kit)
    kit.store.set_final_time(game_id, NOW.date(), NOW + 3 * HOUR)

    await kit.serve(NOW + 4 * HOUR - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(NOW + 4 * HOUR)

    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_final_game_of_the_games_job_inside_the_postseason_dates_expires_the_feed(
    kit: PlayoffsKit,
) -> None:
    await kit.serve()
    kit.games.final = [board("elsewhere", "ATL", "BOS", NOW + 2 * HOUR)]
    kit.store.set_final_time("elsewhere", NOW.date(), NOW + 2 * HOUR)

    await kit.serve(NOW + 3 * HOUR - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(NOW + 3 * HOUR)

    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_final_game_outside_the_postseason_dates_does_not_expire_a_playin_feed(
    kit: PlayoffsKit,
) -> None:
    await kit.serve()
    outside = dt.datetime(2027, 3, 1, 1, 0, tzinfo=dt.UTC)
    kit.games.final = [board("regular", "ATL", "BOS", outside)]
    kit.store.set_final_time("regular", outside.date(), NOW + 2 * HOUR)

    await kit.serve(NOW + 4 * HOUR)

    assert kit.called("standings") == 1


@pytest.mark.anyio
async def test_a_picture_feed_is_fresh_before_a_final_league_game_plus_1_hour_and_stale_at_it(
    kit: PlayoffsKit,
) -> None:
    kit.clock[0] = dt.datetime(2027, 3, 1, 20, 0, tzinfo=dt.UTC)
    start = kit.clock[0]
    await kit.serve()
    kit.games.final = [board("regular", "ATL", "BOS", start + HOUR)]
    kit.store.set_final_time("regular", start.date(), start + 2 * HOUR)

    await kit.serve(start + 3 * HOUR - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(start + 3 * HOUR)

    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_picture_feed_goes_stale_at_the_play_in_start_and_at_7_days(
    kit: PlayoffsKit,
) -> None:
    start = dt.datetime(2027, 4, 13, 12, 0, tzinfo=dt.UTC)
    await kit.serve(start)
    midnight = dt.datetime(2027, 4, 14, 4, 0, tzinfo=dt.UTC)

    await kit.serve(midnight - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(midnight)
    assert kit.called("standings") == 2
    stored = kit.stored()
    assert stored is not None and stored.state is PlayoffsState.PLAYIN


@pytest.mark.anyio
async def test_a_picture_feed_is_stale_at_7_days(kit: PlayoffsKit) -> None:
    start = dt.datetime(2027, 3, 1, 12, 0, tzinfo=dt.UTC)
    await kit.serve(start)

    await kit.serve(start + FEED_LIFETIME - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(start + FEED_LIFETIME)

    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_7_days_and_stale_at_7_days(
    kit: PlayoffsKit,
) -> None:
    await kit.serve()

    await kit.serve(NOW + FEED_LIFETIME - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(NOW + FEED_LIFETIME)

    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_complete_feed_stays_fresh_past_7_days_and_is_stale_once_the_season_changes(
    kit: PlayoffsKit,
) -> None:
    kit.load(everything())
    await kit.serve()
    kit.games.final = [board("later", "ATL", "BOS", NOW + 3 * HOUR)]
    kit.store.set_final_time("later", NOW.date(), NOW + 3 * HOUR)

    await kit.serve(NOW + 2 * FEED_LIFETIME)
    assert kit.called("standings") == 1
    kit.stars.season = 2028
    await kit.serve(NOW + 2 * FEED_LIFETIME + HOUR)

    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_detail_available_is_set_from_the_loaded_games_and_not_stored(
    kit: PlayoffsKit,
) -> None:
    kit.load(play_ins() + series_games(seed(EAST, 1), seed(EAST, 8), 1, "T", key="g"))
    kit.games.loaded = [board("g-1", seed(EAST, 1), seed(EAST, 8), BASES[1])]

    body = PlayoffsFeed.model_validate_json(await kit.serve())

    served = bracket(body)[SeriesId.EAST_R1_1].games[0]
    assert served.detail_available is True
    stored = kit.stored()
    assert stored is not None
    assert bracket(stored)[SeriesId.EAST_R1_1].games[0].detail_available is False
    assert body.play_in[0].games[0].game is not None
    assert body.play_in[0].games[0].game.detail_available is False


@pytest.mark.anyio
async def test_the_cleanup_keeps_league_and_stored_reads_the_stored_feed(
    kit: PlayoffsKit,
) -> None:
    assert kit.playoffs.keep("league") and not kit.playoffs.keep("other")
    assert kit.playoffs.stored() is None

    await kit.serve()

    assert kit.playoffs.stored() == kit.stored()
    (kit.path / "feeds" / KIND / "league.json").write_text("{}", encoding="utf-8")
    assert kit.playoffs.stored() is None
