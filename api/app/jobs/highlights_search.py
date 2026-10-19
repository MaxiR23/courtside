# api/app/jobs/highlights_search.py
#
# On-demand highlights search: when a feed is served without the full game
# highlights of a final game or the video of an All-Star edition, it starts one
# search of the video channel by query, in the background, so the response is
# never delayed. It is not a job and is in no scheduler. A search runs only
# when the search API URL, the key and the embed URL are set, no search of the
# same target is in flight, the target has no mark, and fewer than
# HIGHLIGHTS_SEARCH_DAILY_CAP searches were sent this US Eastern day, a count
# kept in the state database; a query the source cache still holds sends no
# request and is not counted. The first result in the provider's order whose
# title the target accepts and whose thumbnail the image host serves is stored
# through the target's save; a search that finds none stores a mark, so the
# target is never searched again. A failed request leaves no mark. The core
# imports no seasonal section: a section hands in its own target.
#
# SEE: docs/adr/0065-background-work-limited-to-games-highlights-and-stars.md,
# api/app/jobs/highlights.py, api/app/sources/video_channel.py

import asyncio
import datetime as dt
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.feeds.games import Highlight
from app.jobs.games import eastern_date
from app.jobs.highlights import CheckThumbnail, HighlightsJob
from app.settings import Settings
from app.sources import video_channel
from app.sources.http import SourceClient, SourceError
from app.sources.video_channel import ChannelVideo
from app.storage.state import StateStore

GAME = "game"

Search = Callable[[SourceClient, Settings, str], Awaitable[list[ChannelVideo]]]
IsCached = Callable[[SourceClient, Settings, str], bool]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchTarget:
    kind: str
    id: str
    query: str
    # The title test.
    matches: Callable[[str], bool]
    save: Callable[[Highlight], None]


class HighlightsSearch:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        highlights: HighlightsJob,
        *,
        search: Search = video_channel.search_videos,
        is_cached: IsCached = video_channel.search_is_cached,
        check_thumbnail: CheckThumbnail = video_channel.check_thumbnail,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._highlights = highlights
        self._search = search
        self._is_cached = is_cached
        self._check_thumbnail = check_thumbnail
        self._in_flight: dict[tuple[str, str], asyncio.Task[None]] = {}

    def _configured(self) -> bool:
        key = self._settings.highlights_source_key
        return (
            self._settings.highlights_search_api_url is not None
            and key is not None
            and bool(key.get_secret_value())
            and self._settings.video_embed_url is not None
        )

    def request(self, target: SearchTarget) -> None:
        """Start the search of a target in the background and return at once."""
        identity = (target.kind, target.id)
        if not self._configured() or identity in self._in_flight:
            return
        if self._store.highlight_searched(target.kind, target.id):
            return
        day = eastern_date(self._client.clock())
        cap = self._settings.highlights_search_daily_cap
        if self._store.highlight_searches_on(day) >= cap:
            return
        task = asyncio.create_task(self._run(target))
        self._in_flight[identity] = task

        def done(finished: asyncio.Task[None]) -> None:
            if self._in_flight.get(identity) is finished:
                del self._in_flight[identity]
            if not finished.cancelled():
                finished.exception()  # consume it: nobody awaits the task

        task.add_done_callback(done)

    def request_game(
        self, game_id: str, away: str, home: str, start_time: dt.datetime
    ) -> None:
        day = eastern_date(start_time)
        self.request(
            SearchTarget(
                GAME,
                game_id,
                video_channel.highlights_query(away, home, day),
                lambda title: video_channel.title_matches(title, away, home, day),
                lambda highlight: self._save_game(game_id, highlight),
            )
        )

    def _save_game(self, game_id: str, highlight: Highlight) -> None:
        self._highlights.add_highlight(game_id, highlight)

    async def _run(self, target: SearchTarget) -> None:
        day = eastern_date(self._client.clock())
        if not self._is_cached(
            self._client, self._settings, target.query
        ) and not self._store.take_highlight_search(
            day, self._settings.highlights_search_daily_cap
        ):
            return
        try:
            results = await self._search(self._client, self._settings, target.query)
        except SourceError as error:
            self._log(target, error)
            return
        for video in results:
            if not target.matches(video.title):
                continue
            try:
                video = await self._check_thumbnail(self._client, video)
            except SourceError as error:
                if error.request_failed:
                    self._log(target, error)
                    return
                continue
            if video.thumbnail_url is None:
                continue
            try:
                highlight = video_channel.to_highlight(video, self._settings)
            except SourceError:
                continue
            target.save(highlight)
            return
        self._store.mark_highlight_searched(
            target.kind, target.id, self._client.clock()
        )

    @staticmethod
    def _log(target: SearchTarget, error: SourceError) -> None:
        logger.warning(
            "highlights search: %s %s: %s", target.kind, target.id, error.reason
        )
