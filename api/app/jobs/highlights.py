# api/app/jobs/highlights.py
#
# Highlights job: for each final game, looks up its full game highlights on
# the video channel, one lookup per due game, 1, 2 and 3 hours after the final
# time (right away, 1 and 2 hours later for a game first seen final), never
# after the third attempt. A failed request (timeout, transport failure or
# error status) uses up no attempt; the same attempt is retried no sooner than
# 10 minutes later.
# Matches are kept in the job state. The games job reads the
# highlights through highlights_of and the search URL through search_url_of.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md,
# docs/adr/0010-final-game-attempts.md,
# docs/adr/0015-highlights-source.md,
# docs/adr/0018-highlight-request-failures.md

import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Sequence

import httpx

from app.feeds.games import Highlight
from app.jobs.games import eastern_date
from app.jobs.scheduler import utc_now
from app.settings import Settings
from app.sources import video_channel
from app.sources.http import SourceError
from app.sources.scoreboard import ScoreboardGame
from app.sources.video_channel import ChannelVideo
from app.storage.state import StateStore

JOB = "highlights"
ATTEMPT_DELAYS = (
    dt.timedelta(hours=1),
    dt.timedelta(hours=2),
    dt.timedelta(hours=3),
)
FIRST_SEEN_ATTEMPT_DELAYS = (
    dt.timedelta(0),
    dt.timedelta(hours=1),
    dt.timedelta(hours=2),
)
MAX_ATTEMPTS = len(ATTEMPT_DELAYS)
RETRY = dt.timedelta(minutes=10)

FinalGames = Callable[[], Sequence[ScoreboardGame]]
LookupVideo = Callable[
    [httpx.AsyncClient, ScoreboardGame, dt.date, Settings],
    Awaitable[ChannelVideo | None],
]

logger = logging.getLogger(__name__)


class HighlightsJob:
    name = JOB

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: httpx.AsyncClient,
        *,
        final_games: FinalGames,
        lookup_video: LookupVideo = video_channel.lookup_video,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._final_games = final_games
        self._lookup_video = lookup_video
        self._clock = clock
        self._failed_at: dict[str, dt.datetime] = {}
        self._highlights: dict[str, Highlight] = store.highlights()

    def _due(self, game: ScoreboardGame, now: dt.datetime) -> bool:
        if game.id in self._highlights:
            return False
        final_time = self._store.final_time(game.id)
        if final_time is None:
            return False
        attempts = self._store.highlight_attempts(game.id)
        if attempts >= MAX_ATTEMPTS:
            return False
        failed_at = self._failed_at.get(game.id)
        if failed_at is not None and now - failed_at < RETRY:
            return False
        first_seen = self._store.first_seen_final(game.id)
        delays = FIRST_SEEN_ATTEMPT_DELAYS if first_seen else ATTEMPT_DELAYS
        return now >= final_time + delays[attempts]

    @staticmethod
    def _log_failed(game: ScoreboardGame, number: int, reason: str) -> None:
        logger.warning(
            "highlights for game %s: attempt %d of %d failed: %s",
            game.id,
            number,
            MAX_ATTEMPTS,
            reason,
        )

    def _spend_attempt(self, game: ScoreboardGame, day: dt.date) -> int:
        self._failed_at.pop(game.id, None)
        return self._store.record_highlight_attempt(game.id, day)

    async def run(self, now: dt.datetime) -> None:
        due = [game for game in self._final_games() if self._due(game, now)]
        if not due:
            return
        started = self._clock()
        failure: str | None = None
        for game in due:
            day = eastern_date(game.start_time)
            try:
                video = await self._lookup_video(
                    self._client, game, day, self._settings
                )
            except SourceError as error:
                if error.request_failed:
                    logger.warning(
                        "highlights for game %s: attempt %d of %d not counted, "
                        "retrying in %d minutes: %s",
                        game.id,
                        self._store.highlight_attempts(game.id) + 1,
                        MAX_ATTEMPTS,
                        RETRY // dt.timedelta(minutes=1),
                        str(error),
                    )
                    self._failed_at[game.id] = now + (self._clock() - started)
                    failure = str(error)
                    continue
                number = self._spend_attempt(game, day)
                self._log_failed(game, number, str(error))
                failure = str(error)
                continue
            number = self._spend_attempt(game, day)
            if video is None:
                self._log_failed(game, number, "no video matched")
                continue
            try:
                highlight = video_channel.to_highlight(video, self._settings)
            except SourceError as error:
                self._log_failed(game, number, error.reason)
                failure = str(error)
                continue
            self._store.set_highlight(game.id, highlight)
            self._highlights[game.id] = highlight
        if failure is not None:
            self._store.record_failure(JOB, now, failure)
        else:
            self._store.record_success(JOB, now)

    def highlights_of(self, game: ScoreboardGame) -> list[Highlight]:
        found = self._highlights.get(game.id)
        return [] if found is None else [found]

    def search_url_of(self, game: ScoreboardGame) -> str | None:
        return video_channel.search_url(
            game, eastern_date(game.start_time), self._settings
        )
