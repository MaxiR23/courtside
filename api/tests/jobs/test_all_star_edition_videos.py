# api/tests/jobs/test_all_star_edition_videos.py
#
# Tests for the All-Star edition video provider of the highlights backfill.
#
# Tested:
# - An upload within the window is the edition video when its title has All-Star, the year and Highlights
# - An upload with Full in the title is found, in any letter case
# - An upload published the day before or 4 days after the game day is not found
# - A title of another year, or without Highlight or Full, is not found
# - No target while the window is open, and none for an edition with a stored video
# - The video is stored by season
#
# What is covered:
# - Pure logic: the title rule and the window; the edition targets over a state store in a temporary directory
#
# Fixtures are invented titles; no test reads a source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_all_star_edition_videos.py
#
# SEE: api/app/jobs/all_star_edition_videos.py

import datetime as dt
from pathlib import Path

import pytest

from app.feeds.games import Highlight
from app.jobs.all_star_edition_videos import (
    AllStarEditionVideos,
    EditionTarget,
    edition_title_matches,
)
from app.sources.video_channel import ChannelVideo
from app.storage.state import StateStore

GAME_DATE = dt.date(2027, 2, 14)
# Midnight US Eastern of the game day, in UTC.
START = dt.datetime(2027, 2, 14, 5, 0, tzinfo=dt.UTC)
END = START + dt.timedelta(days=4)
TITLE = "2027 All-Star Game | Full Game Highlights"


def video(title: str = TITLE, published_at: dt.datetime = START) -> ChannelVideo:
    return ChannelVideo(
        video_id="v1",
        title=title,
        channel="Example Channel",
        published_at=published_at,
        thumbnail_url=None,
    )


def highlight() -> Highlight:
    return Highlight.model_validate(
        {
            "title": TITLE,
            "channel": "Example Channel",
            "thumbnail_url": "https://example.com/t.jpg",
            "embed_url": "https://example.com/e/v1",
        }
    )


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    state.set_all_star_edition(2027, GAME_DATE, ["g1"])
    return state


def test_the_target_covers_the_game_day_and_the_three_days_after() -> None:
    target = EditionTarget(2027, GAME_DATE)

    assert (target.kind, target.id, target.start, target.end) == (
        "edition",
        "2027",
        START,
        END,
    )


@pytest.mark.parametrize(
    "title",
    [
        "2027 All-Star Game Highlights",
        "2027 NBA All-Star Game | FULL GAME",
        "2027 all-star game highlights",
    ],
)
def test_finds_an_upload_in_the_window_by_highlights_or_full_in_any_case(
    title: str,
) -> None:
    assert EditionTarget(2027, GAME_DATE).matches(video(title))


def test_finds_an_upload_at_the_start_of_the_window_and_just_before_its_end() -> None:
    target = EditionTarget(2027, GAME_DATE)

    assert target.matches(video(published_at=START))
    assert target.matches(video(published_at=END - dt.timedelta(seconds=1)))


def test_does_not_find_an_upload_the_day_before_or_four_days_after() -> None:
    target = EditionTarget(2027, GAME_DATE)

    assert not target.matches(video(published_at=START - dt.timedelta(days=1)))
    assert not target.matches(video(published_at=END))


@pytest.mark.parametrize(
    "title",
    [
        "2026 All-Star Game Highlights",
        "2027 All-Star Game | Recap",
        "2027 Rising Stars Highlights",
    ],
)
def test_does_not_find_another_year_or_a_title_without_highlights_or_full(
    title: str,
) -> None:
    assert not EditionTarget(2027, GAME_DATE).matches(video(title))
    assert not edition_title_matches(title, 2027)


def test_gives_no_target_while_the_window_is_open(store: StateStore) -> None:
    videos = AllStarEditionVideos(store)

    assert videos.targets(END - dt.timedelta(seconds=1)) == []
    assert [t.id for t in videos.targets(END)] == ["2027"]


def test_gives_no_target_for_an_edition_with_a_stored_video(store: StateStore) -> None:
    videos = AllStarEditionVideos(store)
    store.set_all_star_edition(2026, dt.date(2026, 2, 15), ["g0"])

    videos.store("2027", highlight())

    assert [t.id for t in videos.targets(END + dt.timedelta(days=400))] == ["2026"]


def test_stores_the_video_by_season(store: StateStore) -> None:
    AllStarEditionVideos(store).store("2027", highlight())

    assert store.all_star_edition_highlight(2027) == highlight()
    assert store.all_star_edition_highlight(2026) is None
