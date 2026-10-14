# api/tests/jobs/test_playoffs_titles.py
#
# Tests for the playoffs title provider of the team feed.
#
# Tested:
# - The champion of the playoffs feed gets the NBA title with the year of the last Finals date
# - Each conference finals winner gets its conference title, and the champion gets both titles in order
# - A team without a title, a stored feed of another season and no stored feed give no titles
# - The titles are read from the stored feed for the label of the roster season
# - A rebuild of the stored playoffs feed after a build is reported, and none otherwise
#
# What is covered:
# - Pure logic: happy path, edge cases
# - The stored-feed read and the freshness check, over a state store in a temporary directory
#
# The feed is built without validation, with only the fields the titles read.
# No test reads a source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_playoffs_titles.py
#
# SEE: api/app/jobs/playoffs_titles.py

import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from app.feeds.games import Conference
from app.feeds.playoffs import (
    Champion,
    PlayoffsFeed,
    PlayoffTeam,
    Series,
    SeriesId,
    SeriesStatus,
)
from app.feeds.team import TeamTitle, TitleKind
from app.jobs import playoffs_feed
from app.jobs.playoffs_titles import PlayoffsTitles, playoffs_titles
from app.storage.state import StateStore

SEASON = "2026-27"
NOW = dt.datetime(2027, 6, 21, 12, 0, tzinfo=dt.UTC)


def series(series_id: SeriesId, winner: str | None, conference: Conference) -> Series:
    return Series.model_construct(
        id=series_id,
        conference=conference,
        status=SeriesStatus.COMPLETE if winner else SeriesStatus.IN_PROGRESS,
        winner=winner,
    )


def playoffs(
    champion: str | None = None,
    east: str | None = None,
    west: str | None = None,
    season: str = SEASON,
) -> PlayoffsFeed:
    return PlayoffsFeed.model_construct(
        season=season,
        champion=None
        if champion is None
        else Champion.model_construct(
            team=PlayoffTeam.model_construct(code=champion),
            last_date=dt.date(2027, 6, 20),
        ),
        bracket=[
            series(SeriesId.EAST_R3, east, Conference.EAST),
            series(SeriesId.WEST_R3, west, Conference.WEST),
        ],
    )


def kinds(titles: list[TeamTitle] | None) -> list[TitleKind]:
    return [t.kind for t in titles or []]


def test_gives_the_champion_nba_champions_with_the_year_of_the_last_finals_date() -> (
    None
):
    assert playoffs_titles("OKC", SEASON, playoffs(champion="OKC")) == [
        TeamTitle(kind=TitleKind.NBA_CHAMPIONS, year=2027, conference=None)
    ]


def test_gives_each_conference_finals_winner_its_conference_title() -> None:
    feed = playoffs(east="BOS", west="OKC")

    assert playoffs_titles("BOS", SEASON, feed) == [
        TeamTitle(
            kind=TitleKind.CONFERENCE_CHAMPIONS, year=None, conference=Conference.EAST
        )
    ]
    assert playoffs_titles("OKC", SEASON, feed) == [
        TeamTitle(
            kind=TitleKind.CONFERENCE_CHAMPIONS, year=None, conference=Conference.WEST
        )
    ]
    assert playoffs_titles("NYK", SEASON, playoffs(east=None)) is None


def test_gives_the_champion_both_titles_in_order() -> None:
    titles = playoffs_titles("OKC", SEASON, playoffs(champion="OKC", west="OKC"))

    assert kinds(titles) == [TitleKind.NBA_CHAMPIONS, TitleKind.CONFERENCE_CHAMPIONS]


def test_gives_no_titles_to_a_team_without_one() -> None:
    feed = playoffs(champion="OKC", east="BOS", west="OKC")

    assert playoffs_titles("LAL", SEASON, feed) is None


def test_gives_no_titles_from_a_stored_feed_of_another_season_or_none() -> None:
    past = playoffs(champion="OKC", season="2025-26")

    assert playoffs_titles("OKC", SEASON, past) is None
    assert playoffs_titles("OKC", SEASON, None) is None


class Stored:
    """A stand-in for the playoffs feed kind that has a stored feed."""

    def __init__(self, feed: Any) -> None:
        self.feed = feed

    def stored(self) -> Any:
        return self.feed


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


def provider(store: StateStore, feed: Any = None) -> PlayoffsTitles:
    return PlayoffsTitles(store, cast(Any, Stored(feed)))


def test_reads_the_stored_feed_for_the_season_label_of_the_rosters_season(
    store: StateStore,
) -> None:
    reader = provider(store, playoffs(champion="OKC"))

    assert kinds(reader.titles("OKC", 2027)) == [TitleKind.NBA_CHAMPIONS]
    assert reader.titles("OKC", 2026) is None


def test_reports_a_rebuild_of_the_playoffs_feed_after_the_build_and_none_otherwise(
    store: StateStore,
) -> None:
    reader = provider(store)
    assert not reader.rebuilt_after(NOW)

    store.record_build(playoffs_feed.KIND, playoffs_feed.FEED_ID, NOW)

    assert reader.rebuilt_after(NOW - dt.timedelta(seconds=1))
    assert not reader.rebuilt_after(NOW)
