# api/tests/sources/test_all_star_mark.py
#
# Tests for the All-Star mark of a scoreboard game.
#
# Tested:
# - Tells an All-Star game by season type 2 and competition type ALLSTAR, and gives false for another competition type, another season type or none
# - Gives the round of a Round Robin note with the Championship flag false
# - Gives the Championship round with the flag true
# - Drops the format suffix from a Semifinals note
# - Gives no mark for a note that is not an All-Star note, an empty note and no note
#
# What is covered:
# - Happy path, edge cases and error cases of the pure mark function
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_all_star_mark.py
#
# SEE: api/app/sources/all_star_mark.py

import pytest

from app.sources.all_star_mark import all_star_mark, is_all_star


def test_tells_an_all_star_game_by_season_type_and_competition_type() -> None:
    assert is_all_star(2, "ALLSTAR") is True


@pytest.mark.parametrize(
    ("season_type", "competition_type"),
    [(2, "STD"), (3, "ALLSTAR"), (2, None), (None, "ALLSTAR"), (None, None)],
)
def test_is_not_all_star_for_another_type_or_none(
    season_type: int | None, competition_type: str | None
) -> None:
    assert is_all_star(season_type, competition_type) is False


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
