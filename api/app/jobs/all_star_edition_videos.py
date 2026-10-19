# api/app/jobs/all_star_edition_videos.py
#
# The All-Star edition video for the on-demand highlights search (ADR 0065). It
# belongs to the All-Star section: it names the editions a feed shows whose
# video window has ended with no video stored, and hands each to the core
# search as a target that stores the video in the job state; it reads no source
# itself. The window starts at midnight US Eastern of the game day and lasts 4
# days, because the video is uploaded after the games. A title is the edition
# video when it names All-Star, the year of the game day and either
# "highlight" or "full", in any letter case. The core search receives it
# injected from main.py and imports no section.
#
# SEE: docs/adr/0065-background-work-limited-to-games-highlights-and-stars.md,
# docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0036-all-star-feed.md, api/app/jobs/highlights_search.py

import datetime as dt
from collections.abc import Callable

from app.feeds.all_star import AllStarFeed, AllStarState
from app.jobs.games import EASTERN
from app.jobs.highlights_search import HighlightsSearch, SearchTarget
from app.storage.state import StateStore

EDITION = "edition"
WINDOW = dt.timedelta(days=4)


def edition_title_matches(title: str, year: int) -> bool:
    """True when the title names the All-Star Game, the year and a highlights
    or full video, in any letter case."""
    lowered = title.lower()
    return (
        "all-star" in lowered
        and str(year) in lowered
        and ("highlight" in lowered or "full" in lowered)
    )


class AllStarEditionVideos:
    def __init__(
        self,
        store: StateStore,
        search: HighlightsSearch,
        clock: Callable[[], dt.datetime],
    ) -> None:
        self._store = store
        self._search = search
        self._clock = clock

    def _request(self, year: int, date: dt.date | None) -> None:
        if date is None:
            return
        start = dt.datetime.combine(date, dt.time(0), tzinfo=EASTERN)
        if self._clock() < start + WINDOW:
            return
        if self._store.all_star_edition_highlight(year) is not None:
            return
        self._search.request(
            SearchTarget(
                EDITION,
                str(year),
                f"All-Star Game {year} full game highlights",
                lambda title: edition_title_matches(title, year),
                lambda highlight: self._store.set_all_star_edition_highlight(
                    year, highlight
                ),
            )
        )

    def request_for(self, feed: AllStarFeed) -> None:
        """Start the search of each edition the feed shows that is past its
        window with no video. The mark and the cap are checked by the search."""
        if feed.state is AllStarState.AFTER:
            self._request(feed.year, feed.edition.date)
        if feed.previous is not None:
            self._request(feed.previous.year, feed.previous.date)
