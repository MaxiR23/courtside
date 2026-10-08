# api/app/jobs/highlights.py
#
# Highlights job: for each final game, looks up its full game highlights on
# the video channel 1, 2 and 3 hours after the final time (right away, 1 and 2
# hours later for a game first seen final), never after the third attempt.
# Each run lists the channel uploads once, fetched at or after the run's start
# and paged back until every due game is matched or a video is older than the
# oldest due game, and matches every due game against that one list (rule E).
# A listing that fails (timeout, transport failure or error status) uses up no
# attempt of any due game, and each is retried no sooner than 10 minutes later;
# any other outcome counts for each due game as its own lookup did. A game
# matched on a page read before an invalid page keeps its match. A failed
# thumbnail check affects only its game.
# Matches are kept in the job state. The games job reads the
# highlights through highlights_of and the search URL through search_url_of.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md,
# docs/adr/0010-final-game-attempts.md,
# docs/adr/0015-highlights-source.md,
# docs/adr/0018-highlight-request-failures.md,
# docs/adr/0020-source-rules.md, docs/source-rules.md

import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Sequence

from app.feeds.games import Highlight
from app.jobs.games import eastern_date
from app.jobs.scheduler import utc_now
from app.settings import Settings
from app.sources import video_channel
from app.sources.http import SourceClient, SourceError
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
ListUploads = Callable[
    [
        SourceClient,
        Sequence[tuple[ScoreboardGame, dt.date]],
        Settings,
        dt.datetime,
    ],
    Awaitable[list[ChannelVideo]],
]
CheckThumbnail = Callable[[SourceClient, ChannelVideo], Awaitable[ChannelVideo]]

logger = logging.getLogger(__name__)


class HighlightsJob:
    name = JOB

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        *,
        final_games: FinalGames,
        list_uploads: ListUploads = video_channel.list_uploads,
        check_thumbnail: CheckThumbnail = video_channel.check_thumbnail,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._final_games = final_games
        self._list_uploads = list_uploads
        self._check_thumbnail = check_thumbnail
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

    def _wait_after_failed_request(
        self,
        game: ScoreboardGame,
        error: SourceError,
        now: dt.datetime,
        started: dt.datetime,
    ) -> None:
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

    async def run(self, now: dt.datetime) -> None:
        due = [game for game in self._final_games() if self._due(game, now)]
        if not due:
            return
        started = self._clock()
        days = [(game, eastern_date(game.start_time)) for game in due]
        uploads: list[ChannelVideo] = []
        listing_error: SourceError | None = None
        try:
            uploads = await self._list_uploads(self._client, days, self._settings, now)
        except SourceError as error:
            if error.request_failed:
                for game, _ in days:
                    self._wait_after_failed_request(game, error, now, started)
                self._store.record_failure(JOB, now, str(error))
                return
            listing_error = error
            if isinstance(error, video_channel.ListingError):
                uploads = error.uploads
        failure: str | None = None if listing_error is None else str(listing_error)
        for game, day in days:
            video = video_channel.find_video(uploads, game, day)
            if video is None:
                number = self._spend_attempt(game, day)
                if listing_error is not None:
                    self._log_failed(game, number, str(listing_error))
                else:
                    self._log_failed(game, number, "no video matched")
                continue
            try:
                video = await self._check_thumbnail(self._client, video)
            except SourceError as error:
                if error.request_failed:
                    self._wait_after_failed_request(game, error, now, started)
                    failure = str(error)
                    continue
                number = self._spend_attempt(game, day)
                self._log_failed(game, number, str(error))
                failure = str(error)
                continue
            number = self._spend_attempt(game, day)
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
