# api/tests/sources/test_postseason_mark.py
#
# Tests for the postseason mark of a scoreboard game.
#
# Tested:
# - Gives the same mark for an upper-case note as for its title case, in the play-in and series paths, and none for an empty note or FINALS
# - Marks a seventh game as game_7 in any status, a final game that gives a side four wins as clinched, and a game entering with three wins against fewer as can_clinch
# - Keeps the entering stake on a final game the leader lost or that tied the series, and marks three wins each on a game that is not the seventh as elimination
# - Marks the nine-ten and eighth-seed play-in games as elimination and the seven-eight game with no stakes
# - Gives no stakes without three entering wins, without a series object, without both sides in its wins or when the final winner has no win
# - Maps a play-in note, a round 1 to 3 game and a Finals game to their stage, round, conference, number and summary
# - Gives no mark to a regular season game, an unknown competition type, a note without a game number or a conference, or an unknown play-in note
#
# What is covered:
# - Happy path, edge cases and error cases of the pure mark function
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_postseason_mark.py
#
# SEE: api/app/sources/postseason_mark.py

from collections.abc import Mapping
from typing import Any

import pytest

from app.feeds.games import (
    Conference,
    GamePostseason,
    GameStatus,
    PlayInGameKind,
    PostseasonStage,
    Score,
    Stakes,
)
from app.sources.postseason_mark import postseason_mark, stakes_of

AWAY, HOME = "BOS", "NYK"


def series_mark(
    number: int,
    wins: Mapping[str, int] | None,
    status: GameStatus = GameStatus.SCHEDULED,
    score: Score | None = None,
    **extra: Any,
) -> GamePostseason | None:
    arguments: dict[str, Any] = {
        "season_type": 3,
        "competition_type": "QTR",
        "note": f"East Semifinals - Game {number}",
        "summary": "BOS leads series 3-1",
        "wins": wins,
        "status": status,
        "away": AWAY,
        "home": HOME,
        "score": score,
    }
    arguments.update(extra)
    return postseason_mark(**arguments)


def stakes(
    number: int,
    wins: Mapping[str, int] | None,
    status: GameStatus = GameStatus.SCHEDULED,
    score: Score | None = None,
) -> Stakes | None:
    return stakes_of(number, wins, AWAY, HOME, status, score)


def play_in(note: str | None) -> GamePostseason | None:
    return postseason_mark(
        season_type=5,
        competition_type=None,
        note=note,
        summary=None,
        wins=None,
        status=GameStatus.SCHEDULED,
        away=AWAY,
        home=HOME,
        score=None,
    )


def test_marks_a_seventh_game_as_game_7_in_any_status() -> None:
    tied = {AWAY: 3, HOME: 3}

    assert stakes(7, tied) is Stakes.GAME_7
    assert stakes(7, tied, GameStatus.LIVE) is Stakes.GAME_7
    assert stakes(
        7, {AWAY: 4, HOME: 3}, GameStatus.FINAL, Score(away=100, home=90)
    ) is (Stakes.GAME_7)
    assert stakes(7, None) is Stakes.GAME_7


def test_marks_the_final_game_that_gives_a_side_four_wins_as_clinched() -> None:
    result = stakes(6, {AWAY: 4, HOME: 2}, GameStatus.FINAL, Score(away=101, home=95))

    assert result is Stakes.CLINCHED


def test_marks_a_game_entering_with_three_wins_against_fewer_as_can_clinch() -> None:
    assert stakes(5, {AWAY: 3, HOME: 1}) is Stakes.CAN_CLINCH
    assert stakes(6, {AWAY: 2, HOME: 3}, GameStatus.LIVE) is Stakes.CAN_CLINCH


def test_keeps_can_clinch_on_a_final_game_the_leader_lost() -> None:
    result = stakes(5, {AWAY: 3, HOME: 2}, GameStatus.FINAL, Score(away=90, home=99))

    assert result is Stakes.CAN_CLINCH


def test_keeps_can_clinch_on_a_final_game_six_that_tied_the_series() -> None:
    result = stakes(6, {AWAY: 3, HOME: 3}, GameStatus.FINAL, Score(away=90, home=99))

    assert result is Stakes.CAN_CLINCH


def test_marks_a_series_game_entering_at_three_wins_each_and_not_game_7_as_elimination() -> (
    None
):
    assert stakes(6, {AWAY: 3, HOME: 3}) is Stakes.ELIMINATION


def test_marks_the_nine_ten_and_eighth_seed_play_in_games_as_elimination() -> None:
    nine_ten = play_in("NBA Play-In - West - 9th Place vs 10th Place")
    eighth = play_in("NBA Play-In - East - 8th Seed Game")

    assert nine_ten is not None and nine_ten.stakes is Stakes.ELIMINATION
    assert eighth is not None and eighth.stakes is Stakes.ELIMINATION


def test_gives_the_seven_eight_play_in_game_no_stakes() -> None:
    mark = play_in("NBA Play-In - East - 7th Place vs 8th Place")

    assert mark is not None and mark.stakes is None


def test_gives_no_stakes_when_neither_side_has_three_entering_wins() -> None:
    assert stakes(3, {AWAY: 1, HOME: 1}) is None
    assert (
        stakes(4, {AWAY: 2, HOME: 1}, GameStatus.FINAL, Score(away=100, home=90))
        is None
    )


def test_gives_no_stakes_without_a_series_object_or_without_both_sides_in_its_wins() -> (
    None
):
    assert stakes(5, None) is None
    assert stakes(5, {AWAY: 3}) is None
    assert (
        stakes_of(5, {AWAY: 3, HOME: 1}, None, HOME, GameStatus.SCHEDULED, None) is None
    )


def test_gives_no_stakes_when_a_final_winner_has_no_win_in_the_series_object() -> None:
    result = stakes(3, {AWAY: 0, HOME: 1}, GameStatus.FINAL, Score(away=100, home=90))

    assert result is None
    assert stakes(3, {AWAY: 1, HOME: 1}, GameStatus.FINAL, None) is None
    assert (
        stakes(3, {AWAY: 1, HOME: 1}, GameStatus.FINAL, Score(away=90, home=90)) is None
    )


def test_maps_a_play_in_note_to_its_conference_and_kind() -> None:
    mark = play_in("NBA Play-In - West - 9th Place vs 10th Place")

    assert mark == GamePostseason(
        stage=PostseasonStage.PLAYIN,
        round=None,
        conference=Conference.WEST,
        number=None,
        summary=None,
        play_in=PlayInGameKind.NINE_TEN,
        stakes=Stakes.ELIMINATION,
    )


def test_maps_a_round_1_to_3_game_to_playoffs_with_round_conference_number_and_summary() -> (
    None
):
    mark = series_mark(5, {AWAY: 3, HOME: 1})

    assert mark == GamePostseason(
        stage=PostseasonStage.PLAYOFFS,
        round=2,
        conference=Conference.EAST,
        number=5,
        summary="BOS leads series 3-1",
        play_in=None,
        stakes=Stakes.CAN_CLINCH,
    )
    west = series_mark(
        2, None, competition_type="RD16", note="West 1st Round - Game 2", summary=None
    )
    assert west is not None
    assert (west.round, west.conference, west.summary) == (1, Conference.WEST, None)


def test_maps_a_finals_game_to_round_4_with_no_conference() -> None:
    mark = series_mark(
        6,
        {AWAY: 4, HOME: 2},
        GameStatus.FINAL,
        Score(away=101, home=95),
        competition_type="FINAL",
        note="NBA Finals - Game 6",
    )

    assert mark is not None
    assert (mark.stage, mark.round, mark.conference, mark.number) == (
        PostseasonStage.FINALS,
        4,
        None,
        6,
    )
    assert mark.stakes is Stakes.CLINCHED


def test_gives_no_mark_to_a_regular_season_game() -> None:
    assert series_mark(1, None, season_type=2) is None
    assert series_mark(1, None, season_type=None) is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"competition_type": "XYZ"},
        {"competition_type": None},
        {"note": "East Semifinals"},
        {"note": None},
        {"note": "Semifinals - Game 2"},
    ],
)
def test_gives_no_mark_for_an_unknown_competition_type_a_note_without_a_game_number_or_a_series_note_without_a_conference(
    overrides: dict[str, Any],
) -> None:
    assert series_mark(2, {AWAY: 1, HOME: 1}, **overrides) is None


def test_gives_no_mark_for_an_unknown_play_in_note() -> None:
    assert play_in("NBA Play-In - East - Tournament") is None
    assert play_in(None) is None


def test_an_upper_case_play_in_note_gives_the_mark_of_its_title_case() -> None:
    note = "NBA Play-In - West - 9th Place vs 10th Place"

    assert play_in(note.upper()) == play_in(note)
    assert play_in(note.upper()) is not None


def test_an_upper_case_series_note_gives_the_mark_of_its_title_case() -> None:
    wins = {AWAY: 1, HOME: 1}

    upper = series_mark(1, wins, note="EAST 1ST ROUND - GAME 3")
    title = series_mark(1, wins, note="East 1st Round - Game 3")

    assert upper is not None
    assert upper == title
    assert upper.conference == Conference.EAST
    assert upper.number == 3


@pytest.mark.parametrize("note", ["", "FINALS", None])
def test_an_empty_note_or_finals_gives_no_series_mark(note: str | None) -> None:
    assert series_mark(1, None, note=note) is None
