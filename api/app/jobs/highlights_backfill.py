# api/app/jobs/highlights_backfill.py
#
# Highlights backfill job: once a day, at the daily fetch time, finds the full
# game highlights of final games the live highlights job no longer owns (its 3
# attempts are used, or no final time is stored) and the video of each stored
# All-Star edition. It runs in its own task, a third scheduler, so its pages
# never delay the live refresh or the stars (ADR 0014, ADR 0048).
#
# Targets are the final games of the games job window, of every stored day feed
# and of the injected game sources (the Cup and the playoffs sections, which the
# core never imports), plus the injected edition source (the All-Star section).
# An All-Star game, a game with a highlight and a target already swept are left
# out. One sweep pages the channel uploads, newest first, 50 per page, with the
# adapter's one-page read (rule E of docs/source-rules.md): the state holds the
# page token to continue from and the oldest upload time reached. A target is
# ahead while the sweep reads for it: a sweep reads for the targets pending when
# it started, and a target that becomes pending during a sweep waits for the
# next one. A page holding an upload published before a target's start passes
# it, and a passed target is swept for good. A sweep ends when no target is
# ahead or the uploads run out; the next sweep starts from the newest upload. At
# most HIGHLIGHTS_BACKFILL_PAGES pages are read per step, and the step seeds its
# last run from its own job row, so the cap holds across restarts. The first
# match in channel order wins and a match is never replaced. A failed page read
# records the failure, keeps the resume point and every match stored.
#
# SEE: docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/source-rules.md, api/app/jobs/highlights.py

import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import ValidationError

from app.feeds.days import DayFeed
from app.feeds.games import GameStatus, Highlight
from app.jobs import day_feed
from app.jobs.games import EASTERN, eastern_date
from app.jobs.highlights import FinalGames, HighlightsJob
from app.settings import Settings
from app.sources import video_channel
from app.sources.http import SourceClient, SourceError
from app.sources.video_channel import ChannelVideo, UploadsPage
from app.storage.feeds import published_ids, read_by_id
from app.storage.state import StateStore

JOB = "highlights-backfill"
GAME = "game"
EDITION = "edition"

logger = logging.getLogger(__name__)


class BackfillTarget(Protocol):
    @property
    def kind(self) -> str: ...

    @property
    def id(self) -> str: ...

    # The moment before which no upload can be the target's video.
    @property
    def start(self) -> dt.datetime: ...

    def matches(self, video: ChannelVideo) -> bool: ...


@dataclass(frozen=True)
class GameTarget:
    """A final game whose full game highlights are looked up by title."""

    id: str
    away: str
    home: str
    start_time: dt.datetime

    @property
    def kind(self) -> str:
        return GAME

    @property
    def start(self) -> dt.datetime:
        return self.start_time

    def matches(self, video: ChannelVideo) -> bool:
        return video_channel.title_matches(
            video.title, self.away, self.home, eastern_date(self.start_time)
        )


GameSource = Callable[[], Sequence[GameTarget]]


class EditionSource(Protocol):
    def targets(self, now: dt.datetime) -> Sequence[BackfillTarget]: ...

    def store(self, target_id: str, highlight: Highlight) -> None: ...


ReadPage = Callable[
    [SourceClient, Settings, str | None, dt.datetime], Awaitable[UploadsPage]
]
CheckThumbnail = Callable[[SourceClient, ChannelVideo], Awaitable[ChannelVideo]]

type Key = tuple[str, str]


def _key(target: BackfillTarget) -> Key:
    return (target.kind, target.id)


class HighlightsBackfill:
    name = JOB

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        highlights: HighlightsJob,
        *,
        final_games: FinalGames,
        game_sources: Sequence[GameSource] = (),
        editions: EditionSource | None = None,
        read_page: ReadPage = video_channel.read_uploads_page,
        check_thumbnail: CheckThumbnail = video_channel.check_thumbnail,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._highlights = highlights
        self._final_games = final_games
        self._game_sources = game_sources
        self._editions = editions
        self._read_page = read_page
        self._check_thumbnail = check_thumbnail
        self._daily_fetched_at: dt.datetime | None = self._last_run()

    def _last_run(self) -> dt.datetime | None:
        for state in self._store.job_states():
            if state.name == JOB:
                times = [t for t in (state.last_success, state.last_failure) if t]
                return max(times) if times else None
        return None

    def _daily_due(self, now: dt.datetime, today: dt.date) -> bool:
        if self._daily_fetched_at is None:
            return True
        morning = dt.datetime.combine(
            today, self._settings.daily_fetch_time, tzinfo=EASTERN
        )
        return now >= morning > self._daily_fetched_at

    def _stored_day_games(self) -> list[GameTarget]:
        found: list[GameTarget] = []
        data_dir = self._settings.data_dir
        for feed_id in sorted(published_ids(data_dir, day_feed.KIND)):
            body = read_by_id(data_dir, day_feed.KIND, feed_id)
            if body is None:
                continue
            try:
                feed = DayFeed.model_validate_json(body)
            except ValidationError:
                continue
            for game in feed.day.games:
                if game.status is GameStatus.FINAL and game.all_star is None:
                    found.append(
                        GameTarget(
                            game.id, game.away.name, game.home.name, game.start_time
                        )
                    )
        return found

    def _game_targets(self) -> list[GameTarget]:
        candidates = [
            GameTarget(g.id, g.away.name, g.home.name, g.start_time)
            for g in self._final_games()
            if g.all_star is None
        ]
        candidates += self._stored_day_games()
        for source in self._game_sources:
            candidates += source()
        have = self._store.highlights()
        swept = self._store.backfill_swept(GAME)
        targets: dict[str, GameTarget] = {}
        for target in candidates:
            if (
                target.id in targets
                or target.id in have
                or target.id in swept
                or not self._highlights.attempts_over(target.id)
            ):
                continue
            targets[target.id] = target
        return list(targets.values())

    def _targets(self, now: dt.datetime) -> list[BackfillTarget]:
        targets: list[BackfillTarget] = list(self._game_targets())
        if self._editions is not None:
            swept = self._store.backfill_swept(EDITION)
            targets += [t for t in self._editions.targets(now) if t.id not in swept]
        return targets

    def _mark_swept(
        self, targets: Sequence[BackfillTarget], resolved: set[Key]
    ) -> None:
        for kind in (GAME, EDITION):
            ids = [t.id for t in targets if t.kind == kind]
            if ids:
                self._store.mark_backfill_swept(kind, ids)
        resolved.update(_key(t) for t in targets)

    def _store_highlight(self, target: BackfillTarget, highlight: Highlight) -> None:
        if target.kind == GAME:
            self._highlights.add_highlight(target.id, highlight)
        elif self._editions is not None:
            self._editions.store(target.id, highlight)

    async def run(self, now: dt.datetime) -> None:
        if not self._daily_due(now, eastern_date(now)):
            return
        self._daily_fetched_at = now
        targets = self._targets(now)
        if not targets:
            return
        if self._settings.video_embed_url is None:
            self._store.record_failure(
                JOB, now, "video_channel: video embed URL is not configured"
            )
            return
        resolved: set[Key] = set()
        failure: str | None = None
        pages = 0
        while pages < self._settings.highlights_backfill_pages:
            sweep = self._store.backfill_sweep()
            oldest = sweep.oldest if sweep else None
            members = self._store.backfill_members() if sweep else None
            ahead = [
                t
                for t in targets
                if _key(t) not in resolved and (members is None or _key(t) in members)
            ]
            if not ahead:
                if sweep is None:
                    break
                self._store.end_backfill_sweep()
                continue
            try:
                page = await self._read_page(
                    self._client,
                    self._settings,
                    sweep.page_token if sweep else None,
                    now,
                )
            except SourceError as error:
                self._store.record_failure(JOB, now, str(error))
                return
            pages += 1
            for video in page.videos:
                for target in ahead:
                    if _key(target) in resolved or not target.matches(video):
                        continue
                    try:
                        checked = await self._check_thumbnail(self._client, video)
                    except SourceError as error:
                        if error.request_failed:
                            self._store.record_failure(JOB, now, str(error))
                            return
                        self._log_failed(target, error)
                        failure = str(error)
                        self._mark_swept([target], resolved)
                        continue
                    try:
                        highlight = video_channel.to_highlight(checked, self._settings)
                    except SourceError as error:
                        self._log_failed(target, error)
                        failure = str(error)
                        self._mark_swept([target], resolved)
                        continue
                    self._store_highlight(target, highlight)
                    resolved.add(_key(target))
            unmatched = [t for t in ahead if _key(t) not in resolved]
            if not page.videos or page.next_page_token is None:
                self._mark_swept(unmatched, resolved)
                self._store.end_backfill_sweep()
                continue
            page_oldest = min(v.published_at for v in page.videos)
            self._mark_swept([t for t in unmatched if t.start > page_oldest], resolved)
            self._store.set_backfill_sweep(
                page.next_page_token,
                page_oldest if oldest is None else min(oldest, page_oldest),
                [_key(t) for t in unmatched if _key(t) not in resolved],
            )
        if failure is not None:
            self._store.record_failure(JOB, now, failure)
        else:
            self._store.record_success(JOB, now)

    @staticmethod
    def _log_failed(target: BackfillTarget, error: SourceError) -> None:
        logger.warning(
            "highlights backfill: %s %s: %s", target.kind, target.id, error.reason
        )
