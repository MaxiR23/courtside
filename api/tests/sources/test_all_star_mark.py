# api/tests/sources/test_all_star_mark.py
#
# Tests for the All-Star mark of a scoreboard game.
#
# Tested:
# - Tells an All-Star game by season type 2 and competition type ALLSTAR, and gives false for another competition type, another season type or none
# - Gives the round of a Round Robin note with the Championship flag false
# - Gives the Championship round with the flag true
# - Drops the format suffix from a Semifinals note
# - Gives the label as written and the Championship flag for an upper-case note
# - Gives the round All-Star Game, with the Championship flag false, for the notes ALL STAR GAME and NBA All-Star Game in any case (ADR 0051), and none for All-Star Game Extra
# - Gives no mark for a note that is not an All-Star note, an empty note and no note
#
# What is covered:
# - Happy path, edge cases and error cases of the pure mark function
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_all_star_mark.py
#
# SEE: api/app/sources/all_star_mark.py

import pytest

from app.sources.all_star_mark import all_star_mark, is_an_all_star_game, parse_note


def test_tells_an_all_star_game_by_season_type_and_competition_type() -> None:
    assert is_an_all_star_game(2, "ALLSTAR") is True


@pytest.mark.parametrize(
    ("season_type", "competition_type"),
    [(2, "STD"), (3, "ALLSTAR"), (2, None), (None, "ALLSTAR"), (None, None)],
)
def test_is_not_all_star_for_another_type_or_none(
    season_type: int | None, competition_type: str | None
) -> None:
    assert is_an_all_star_game(season_type, competition_type) is False


def test_marks_a_round_robin_note() -> None:
    mark = all_star_mark("NBA All-Star - Round Robin")
    assert mark is not None
    assert mark.round_label == "Round Robin"
    assert mark.championship is False


def test_marks_the_championship() -> None:
    mark = all_star_mark("NBA All-Star - Championship")
    assert mark is not None
    assert mark.round_label == "Championship"
    assert mark.championship is True


def test_drops_the_format_suffix() -> None:
    mark = all_star_mark(
        "NBA All-Star - Semifinals First team to 40 points wins - Untimed"
    )
    assert mark is not None
    assert mark.round_label == "Semifinals"
    assert mark.championship is False


@pytest.mark.parametrize("note", ["NBA Cup - Final", "", None])
def test_gives_no_mark_for_a_note_that_is_not_an_all_star_note(
    note: str | None,
) -> None:
    assert all_star_mark(note) is None


def test_marks_an_upper_case_note_with_its_label_as_written() -> None:
    mark = all_star_mark("NBA ALL-STAR - ROUND ROBIN")
    assert mark is not None
    assert mark.round_label == "ROUND ROBIN"
    assert mark.championship is False


def test_marks_an_upper_case_championship() -> None:
    mark = all_star_mark("NBA ALL-STAR - CHAMPIONSHIP")
    assert mark is not None
    assert mark.round_label == "CHAMPIONSHIP"
    assert mark.championship is True


@pytest.mark.parametrize(
    "note", ["ALL STAR GAME", "NBA All-Star Game", "nba all-star game", "All Star Game"]
)
def test_reads_the_single_game_notes_as_the_all_star_game_round(note: str) -> None:
    assert parse_note(note) == ("All-Star Game", None)
    mark = all_star_mark(note)
    assert mark is not None
    assert mark.round_label == "All-Star Game"
    assert mark.championship is False


def test_reads_the_semifinals_note_with_its_suffix_as_before() -> None:
    note = "NBA All-Star - Semifinals First team to 40 points wins - Untimed"

    assert parse_note(note) == (
        "Semifinals",
        "First team to 40 points wins - Untimed",
    )


def test_gives_no_mark_for_a_single_game_note_with_extra_words() -> None:
    assert parse_note("All-Star Game Extra") == (None, None)
    assert all_star_mark("All-Star Game Extra") is None
