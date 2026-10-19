# api/tests/jobs/test_all_star_edition_videos.py
#
# Tests for the All-Star edition video provider of the on-demand highlights search.
#
# Tested:
# - A title is the edition video when it has All-Star, the year and Highlight or Full, in any letter case
# - A title of another year, or without Highlight or Full, is not accepted
# - request_for asks for the shown editions past their window without a video
# - request_for asks nothing inside the window, with a video, or for an edition not yet after
# - The edition query is All-Star Game, the year and full game highlights
# - The target stores the video by season
#
# What is covered:
# - Pure logic: the title rule and the window; the targets handed to a recording search over a state store in a temporary directory
#
# Fixtures are invented titles; no test reads a source or the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_all_star_edition_videos.py
#
# SEE: api/app/jobs/all_star_edition_videos.py

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from app.feeds.all_star import AllStarFeed, AllStarState
from app.feeds.games import Highlight
from app.jobs.all_star_edition_videos import (
    EDITION,
    WINDOW,
    AllStarEditionVideos,
    edition_title_matches,
)
from app.jobs.highlights_search import HighlightsSearch, SearchTarget
from app.storage.state import StateStore

GAME_DATE = dt.date(2027, 2, 14)
PREVIOUS_DATE = dt.date(2026, 2, 15)
# Midnight US Eastern of the game day, in UTC.
START = dt.datetime(2027, 2, 14, 5, 0, tzinfo=dt.UTC)
END = START + WINDOW
TITLE = "2027 All-Star Game | Full Game Highlights"


def highlight() -> Highlight:
    return Highlight.model_validate(
        {
            "title": TITLE,
            "channel": "Example Channel",
            "thumbnail_url": "https://example.com/t.jpg",
            "embed_url": "https://example.com/e/v1",
        }
    )


class Recorder:
    """Stands in for the core search and records the targets it is handed."""

    def __init__(self) -> None:
        self.targets: list[SearchTarget] = []

    def request(self, target: SearchTarget) -> None:
        self.targets.append(target)


def shown(
    state: AllStarState = AllStarState.AFTER,
    date: dt.date | None = GAME_DATE,
    previous: bool = True,
) -> AllStarFeed:
    return cast(
        AllStarFeed,
        SimpleNamespace(
            year=2027,
            state=state,
            edition=SimpleNamespace(date=date),
            previous=SimpleNamespace(year=2026, date=PREVIOUS_DATE)
            if previous
            else None,
        ),
    )


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    state = StateStore(tmp_path)
    state.migrate()
    return state


def make(store: StateStore, now: dt.datetime) -> tuple[AllStarEditionVideos, Recorder]:
    recorder = Recorder()
    return (
        AllStarEditionVideos(store, cast(HighlightsSearch, recorder), lambda: now),
        recorder,
    )


@pytest.mark.parametrize(
    "title",
    [
        "2027 All-Star Game Highlights",
        "2027 NBA All-Star Game | FULL GAME",
        "2027 all-star game highlights",
    ],
)
def test_accepts_a_title_by_highlights_or_full_in_any_case(title: str) -> None:
    assert edition_title_matches(title, 2027)


@pytest.mark.parametrize(
    "title",
    [
        "2026 All-Star Game Highlights",
        "2027 All-Star Game | Recap",
        "2027 Rising Stars Highlights",
    ],
)
def test_does_not_accept_another_year_or_a_title_without_highlights_or_full(
    title: str,
) -> None:
    assert not edition_title_matches(title, 2027)


def test_request_for_asks_for_the_shown_editions_past_their_window_without_a_video(
    store: StateStore,
) -> None:
    videos, recorder = make(store, END)

    videos.request_for(shown())

    assert [(t.kind, t.id) for t in recorder.targets] == [
        (EDITION, "2027"),
        (EDITION, "2026"),
    ]


def test_request_for_asks_nothing_inside_the_window_with_a_video_or_before_after(
    store: StateStore,
) -> None:
    inside, inside_recorder = make(store, END - dt.timedelta(seconds=1))
    inside.request_for(shown(previous=False))
    assert inside_recorder.targets == []

    store.set_all_star_edition_highlight(2027, highlight())
    store.set_all_star_edition_highlight(2026, highlight())
    stored, stored_recorder = make(store, END + dt.timedelta(days=400))
    stored.request_for(shown())
    assert stored_recorder.targets == []

    before, before_recorder = make(store, END + dt.timedelta(days=400))
    before.request_for(shown(AllStarState.BEFORE, None, previous=False))
    before.request_for(shown(AllStarState.LIVE, GAME_DATE, previous=False))
    assert before_recorder.targets == []


def test_the_edition_query_is_all_star_game_year_full_game_highlights(
    store: StateStore,
) -> None:
    videos, recorder = make(store, END)

    videos.request_for(shown(previous=False))

    (target,) = recorder.targets
    assert target.query == "All-Star Game 2027 full game highlights"
    assert target.matches(TITLE)
    assert not target.matches("2026 All-Star Game Highlights")


def test_the_target_stores_the_video_by_season(store: StateStore) -> None:
    videos, recorder = make(store, END)
    videos.request_for(shown(previous=False))

    recorder.targets[0].save(highlight())

    assert store.all_star_edition_highlight(2027) == highlight()
    assert store.all_star_edition_highlight(2026) is None
