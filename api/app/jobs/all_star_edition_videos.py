# api/app/jobs/all_star_edition_videos.py
#
# The All-Star edition video for the highlights backfill (ADR 0048). It belongs
# to the All-Star section: it reads the stored editions and stores the video of
# an edition in the job state, and reads no source. An edition is a target once
# its window has ended and it has no video; the window starts at midnight US
# Eastern of the game day and lasts 4 days, because the video is uploaded after
# the games. An upload is the edition video when it is published within the
# window and its title names All-Star, the year of the game day and either
# "highlight" or "full", in any letter case. The core backfill receives it as an
# injected provider and imports no section.
#
# SEE: docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0036-all-star-feed.md

import datetime as dt
from dataclasses import dataclass

from app.feeds.games import Highlight
from app.jobs.games import EASTERN
from app.jobs.highlights_backfill import EDITION, BackfillTarget
from app.sources.video_channel import ChannelVideo
from app.storage.state import StateStore

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


@dataclass(frozen=True)
class EditionTarget:
    season: int
    game_date: dt.date

    @property
    def kind(self) -> str:
        return EDITION

    @property
    def id(self) -> str:
        return str(self.season)

    @property
    def start(self) -> dt.datetime:
        return dt.datetime.combine(
            self.game_date, dt.time(0), tzinfo=EASTERN
        ).astimezone(dt.UTC)

    @property
    def end(self) -> dt.datetime:
        return self.start + WINDOW

    def matches(self, video: ChannelVideo) -> bool:
        return self.start <= video.published_at < self.end and edition_title_matches(
            video.title, self.game_date.year
        )


class AllStarEditionVideos:
    def __init__(self, store: StateStore) -> None:
        self._store = store

    def targets(self, now: dt.datetime) -> list[BackfillTarget]:
        found: list[BackfillTarget] = []
        for edition in self._store.all_star_editions():
            target = EditionTarget(edition.season, edition.game_date)
            if now >= target.end and (
                self._store.all_star_edition_highlight(edition.season) is None
            ):
                found.append(target)
        return found

    def store(self, target_id: str, highlight: Highlight) -> None:
        self._store.set_all_star_edition_highlight(int(target_id), highlight)
