# api/tests/jobs/test_cup_titles.py
#
# Tests for the Cup title provider of the team feed.
#
# Tested:
# - The champion of the Cup feed gets the Cup title with the year of the championship game
# - A Cup feed without a championship game, a team that is not the champion, a stored feed of another season and no stored feed give no title
# - The title is read from the stored Cup feed for the label of the roster season
# - A rebuild of the stored Cup feed after a build is reported, and none otherwise
#
# What is covered:
# - Pure logic: happy path, edge cases
# - The stored-feed read and the freshness check, over a state store in a temporary directory
#
# The feed is built without validation, with only the fields the title reads.
# No test reads a source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_cup_titles.py
#
# SEE: api/app/jobs/cup_titles.py

import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from app.feeds.cup import BracketSlot, CupFeed, CupGame, SlotId
from app.feeds.opponent import Opponent
from app.feeds.team import TeamTitle, TitleKind
from app.jobs import cup_feed
from app.jobs.cup_titles import CupTitles, cup_titles
from app.storage.state import StateStore

SEASON = "2026-27"
NOW = dt.datetime(2026, 12, 20, 12, 0, tzinfo=dt.UTC)


def cup(champion: str | None, season: str = SEASON, with_game: bool = True) -> CupFeed:
    game = CupGame.model_construct(date=dt.date(2026, 12, 16)) if with_game else None
    return CupFeed.model_construct(
        season=season,
        champion=None if champion is None else Opponent.model_construct(code=champion),
        bracket=[BracketSlot.model_construct(id=SlotId.FINAL, game=game)],
    )


def test_gives_the_cup_champion_its_title_with_the_year_of_the_championship_game() -> (
    None
):
    assert cup_titles("OKC", SEASON, cup("OKC")) == [
        TeamTitle(kind=TitleKind.NBA_CUP_CHAMPIONS, year=2026, conference=None)
    ]


def test_gives_no_title_without_a_championship_game_or_to_another_team() -> None:
    assert cup_titles("OKC", SEASON, cup("OKC", with_game=False)) is None
    assert cup_titles("LAL", SEASON, cup("OKC")) is None
    assert cup_titles("OKC", SEASON, cup(None)) is None


def test_gives_no_title_from_a_stored_feed_of_another_season_or_none() -> None:
    assert cup_titles("OKC", SEASON, cup("OKC", "2025-26")) is None
    assert cup_titles("OKC", SEASON, None) is None


class Stored:
    """A stand-in for the Cup feed kind that has a stored feed."""

    def __init__(self, feed: Any) -> None:
        self.feed = feed

    def stored(self) -> Any:
        return self.feed


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


def provider(store: StateStore, feed: Any = None) -> CupTitles:
    return CupTitles(store, cast(Any, Stored(feed)))


def test_reads_the_stored_feed_for_the_season_label_of_the_rosters_season(
    store: StateStore,
) -> None:
    reader = provider(store, cup("OKC"))

    assert [t.kind for t in reader.titles("OKC", 2027) or []] == [
        TitleKind.NBA_CUP_CHAMPIONS
    ]
    assert reader.titles("OKC", 2026) is None


def test_reports_a_rebuild_of_the_cup_feed_after_the_build_and_none_otherwise(
    store: StateStore,
) -> None:
    reader = provider(store)
    assert not reader.rebuilt_after(NOW)

    store.record_build(cup_feed.KIND, cup_feed.FEED_ID, NOW)

    assert reader.rebuilt_after(NOW - dt.timedelta(seconds=1))
    assert not reader.rebuilt_after(NOW)
