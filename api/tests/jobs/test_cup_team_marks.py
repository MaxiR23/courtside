# api/tests/jobs/test_cup_team_marks.py
#
# Tests for the Cup mark the Cup section gives the team feed (ADR 0066).
#
# Tested:
# - cup_window_open: closed on Oct 31 with no stored feed, open on Nov 1 and Dec 31, closed on Jan 1; open from a stored first game date of Oct 28
# - team_mark: the group and record of a team in a group row, none for a team in no row
# - CupTeamMarks.reads_tables: true inside the window with no stored feed or an incomplete one, false with a complete stored feed, false outside the window, and a stored feed of another season is ignored
# - CupTeamMarks.stored_mark: the group and record from the stored Cup feed of the season, none with no stored feed or one of another season
#
# What is covered:
# - Pure logic: happy path, edges and errors
# - The provider over a stored Cup feed
#
# The stored Cup feed is built with the Cup feed builder from the test_cup_feed
# helpers. No test reads a source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_cup_team_marks.py
#
# SEE: api/app/jobs/cup_team_marks.py

import datetime as dt
from typing import cast

from app.feeds.cup import CupFeed, CupStage
from app.feeds.game_detail import Conference
from app.feeds.team import CupGroupName, TeamCup
from app.jobs.cup_feed import CupFeeds
from app.jobs.cup_team_marks import CupTeamMarks, cup_window_open, team_mark
from tests.jobs.test_cup_feed import all_final, build, group_pairs, knockouts

SEASON = 2027


class StoredCup:
    """The stored Cup feed of a CupFeeds, set by the test."""

    def __init__(self, feed: CupFeed | None) -> None:
        self.feed = feed

    def stored(self) -> CupFeed | None:
        return self.feed


def marks(feed: CupFeed | None) -> CupTeamMarks:
    return CupTeamMarks(cast(CupFeeds, StoredCup(feed)))


def with_first_game(feed: CupFeed, day: dt.date | None) -> CupFeed:
    return feed.model_copy(update={"first_game_date": day})


def test_the_window_is_closed_on_oct_31_with_no_stored_feed_and_open_from_nov_1_to_dec_31() -> (
    None
):
    assert not cup_window_open(SEASON, dt.date(2026, 10, 31), None)
    assert cup_window_open(SEASON, dt.date(2026, 11, 1), None)
    assert cup_window_open(SEASON, dt.date(2026, 12, 31), None)
    assert not cup_window_open(SEASON, dt.date(2027, 1, 1), None)


def test_the_window_opens_at_the_stored_first_game_date() -> None:
    feed = with_first_game(build(), dt.date(2026, 10, 28))

    assert cup_window_open(SEASON, dt.date(2026, 10, 28), feed)
    assert not cup_window_open(SEASON, dt.date(2026, 10, 27), feed)


def test_a_stored_feed_with_no_first_game_date_opens_the_window_on_nov_1() -> None:
    feed = with_first_game(build(), None)

    assert not cup_window_open(SEASON, dt.date(2026, 10, 31), feed)
    assert cup_window_open(SEASON, dt.date(2026, 11, 1), feed)


def test_the_mark_of_a_team_is_its_group_and_record() -> None:
    feed = build()

    assert team_mark("OKC", feed) == TeamCup(
        group=CupGroupName(conference=Conference.WEST, letter="B"), wins=0, losses=4
    )


def test_a_team_in_no_group_row_has_no_mark() -> None:
    assert team_mark("OKC", build(rows=False)) is None


def test_tables_are_read_inside_the_window_with_no_stored_feed_or_an_incomplete_one() -> (
    None
):
    day = dt.date(2026, 12, 1)

    assert marks(None).reads_tables(SEASON, day)
    assert marks(build()).reads_tables(SEASON, day)


def test_tables_are_not_read_for_a_complete_stored_feed_inside_the_window() -> None:
    complete = build([*group_pairs(all_final()), *knockouts(3, 3)])
    assert complete.stage is CupStage.COMPLETE

    assert not marks(complete).reads_tables(SEASON, dt.date(2026, 12, 1))


def test_tables_are_not_read_outside_the_window() -> None:
    assert not marks(None).reads_tables(SEASON, dt.date(2026, 10, 31))
    assert not marks(build()).reads_tables(SEASON, dt.date(2027, 1, 1))


def test_a_stored_feed_of_another_season_is_ignored() -> None:
    feed = build()

    assert marks(feed).stored_mark("OKC", SEASON + 1) is None
    # Another season's complete feed does not close this season's window.
    other = build([*group_pairs(all_final()), *knockouts(3, 3)])
    assert marks(other).reads_tables(SEASON + 1, dt.date(2027, 12, 1))


def test_the_stored_mark_comes_from_the_stored_cup_feed_of_the_season() -> None:
    assert marks(build()).stored_mark("OKC", SEASON) == TeamCup(
        group=CupGroupName(conference=Conference.WEST, letter="B"), wins=0, losses=4
    )
    assert marks(None).stored_mark("OKC", SEASON) is None
