# api/app/jobs/highlights.py
#
# Highlights job: for each final game, looks for its full game highlights on
# the video channel 1, 2 and 3 hours after the final time (right away, 1 and 2
# hours later for a game first seen final), never after the third attempt.
# Matches are kept in the job state. The games job reads the
# highlights through highlights_of and the search URL through search_url_of.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md,
# docs/adr/0010-final-game-attempts.md

import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Sequence

import httpx

from app.feeds.games import Highlight
from app.jobs.games import eastern_date
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

FinalGames = Callable[[], Sequence[ScoreboardGame]]
FetchVideos = Callable[[httpx.AsyncClient, Settings], Awaitable[list[ChannelVideo]]]

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
        fetch_videos: FetchVideos = video_channel.fetch_videos,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._final_games = final_games
        self._fetch_videos = fetch_videos
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

    async def run(self, now: dt.datetime) -> None:
        due = [game for game in self._final_games() if self._due(game, now)]
        if not due:
            return
        numbers = {g.id: self._store.record_highlight_attempt(g.id) for g in due}
        try:
            videos = await self._fetch_videos(self._client, self._settings)
        except SourceError as error:
            for game in due:
                self._log_failed(game, numbers[game.id], str(error))
            self._store.record_failure(JOB, now, str(error))
            return
        failure: str | None = None
        for game in due:
            day = eastern_date(game.start_time)
            video = video_channel.find_video(videos, game, day)
            if video is None:
                self._log_failed(game, numbers[game.id], "no video matched")
                continue
            try:
                highlight = video_channel.to_highlight(video, self._settings)
            except SourceError as error:
                self._log_failed(game, numbers[game.id], error.reason)
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
