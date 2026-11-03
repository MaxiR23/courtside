# api/app/jobs/news_recap_feed.py
#
# News game recap kind of the on-demand cache: the recap of one game in one
# language, or none, with the site's own game (sides and score) when there is one
# (ADR 0085). The id is "{lang}-{gameId}".
#
# A build looks the recap up in the archive first: a recap a list stored is served
# without a read. Otherwise it reads the game summary, only for a final game the
# site holds (a loaded game of the games job or a final game of a stored day feed)
# and only when the game is not marked as having no recap in that language. A recap
# read is stored; a summary with none marks the game for that language, for good. A
# failed read is logged and marks nothing. Spanish tries the Spanish summary and
# then the English one, so it can serve the English recap; English tries English
# only.
#
# A game is known when the archive holds a recap of it, the games job holds it or a
# stored day feed has it as a final game; not ready before the days shown are
# loaded. With News off every id is unknown and no request is sent (rule I).
#
# A feed is kept for good once its recap cannot change: a Spanish recap, or an English
# one when the Spanish side of the game is settled (its recap archived or the game
# marked as having none). Any other feed, empty or holding the English fallback, is
# rebuilt 15 minutes after its build: the archive is checked again with no read for a
# marked game, and a failed or skipped Spanish read is tried again.
#
# SEE: docs/api/news.md, docs/adr/0085-news-archive-and-feeds.md, docs/source-rules.md

import datetime as dt
import logging
import re
from collections.abc import Awaitable, Callable

from app.feeds.games import GameStatus
from app.feeds.news import NewsLanguage, NewsNote
from app.feeds.news_article import NewsArticleFeed
from app.jobs.games import GamesJob
from app.jobs.news_article_feed import held_game, news_game
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.past_game_detail_feed import KIND as PAST_KIND
from app.jobs.past_game_detail_feed import PastGameDetailFeeds
from app.settings import Settings
from app.sources import news
from app.sources.http import ReadBudget, SourceClient, SourceError, within_budget
from app.storage.feeds import GAME_ID
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

KIND = "news-recaps"
# The summary reads one build sends (ADR 0085): the Spanish one, then the English
# one as its fallback.
READ_BUDGET = 2
FRESH_FOR = dt.timedelta(minutes=15)

_ID = re.compile(r"^(en|es)-(.+)$")

FetchRecap = Callable[..., Awaitable[NewsNote | None]]


def parse_id(feed_id: str) -> tuple[NewsLanguage, str] | None:
    """The language and game id of a feed id, or None when it is not one."""
    found = _ID.fullmatch(feed_id)
    if found is None or GAME_ID.fullmatch(found.group(2)) is None:
        return None
    return NewsLanguage(found.group(1)), found.group(2)


class NewsRecapFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        past: PastGameDetailFeeds,
        *,
        fetch_recap: FetchRecap = news.fetch_game_recap,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._cache = cache
        self._games = games
        self._past = past
        self._fetch_recap = fetch_recap
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        parsed = parse_id(feed_id)
        if not self._settings.news_enabled or parsed is None:
            return IdStatus.UNKNOWN
        game_id = parsed[1]
        if (
            any(
                self._store.news_recap(game_id, language) is not None
                for language in NewsLanguage
            )
            or self._games.loaded_game(game_id) is not None
            or self._cache.status(PAST_KIND, game_id) is IdStatus.KNOWN
        ):
            return IdStatus.KNOWN
        if self._games.shown_games() is None:
            return IdStatus.NOT_READY
        return IdStatus.UNKNOWN

    async def _recap(self, language: NewsLanguage, game_id: str) -> NewsNote | None:
        game = held_game(self._games, self._past, game_id)
        languages = (
            [NewsLanguage.ES, NewsLanguage.EN]
            if language is NewsLanguage.ES
            else [NewsLanguage.EN]
        )
        for read_language in languages:
            stored = self._store.news_recap(game_id, read_language)
            if stored is not None:
                return stored
            if (
                game is None
                or game.status is not GameStatus.FINAL
                or self._store.news_recap_missing(game_id, read_language)
            ):
                continue
            teams = [
                side.code
                for side in (game.away, game.home)
                if not side.guest and side.code is not None
            ]
            try:
                note = await self._fetch_recap(
                    self._client,
                    self._settings,
                    game_id,
                    read_language,
                    published=game.start_time,
                    teams=teams,
                )
            except SourceError as error:
                # The reason never carries the URL. Nothing is marked.
                logger.warning(
                    "News recap of game %s not read: %s", game_id, error.reason
                )
                continue
            now = self._client.clock()
            if note is None:
                self._store.mark_news_recap_missing(game_id, read_language, now)
                continue
            self._store.add_news_notes([note], now)
            # The first recap stored wins, so read the archive back.
            stored = self._store.news_recap(game_id, read_language)
            if stored is not None:
                return stored
        return None

    async def build(self, feed_id: str) -> NewsArticleFeed:
        parsed = parse_id(feed_id)
        if parsed is None:
            raise ValueError(f"not a news recap id: {feed_id}")
        language, game_id = parsed
        note = await within_budget(
            ReadBudget(READ_BUDGET, stop_on_rate_limit=False),
            f"news recap: {feed_id}",
            lambda: self._recap(language, game_id),
        )
        game = held_game(self._games, self._past, game_id)
        return NewsArticleFeed(
            note=note, game=news_game(game) if game and note else None
        )

    def is_fresh(
        self, feed: NewsArticleFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        if now - built_at < FRESH_FOR:
            return True
        note = feed.note
        if note is None:
            return False
        if note.language is NewsLanguage.ES or note.game_id is None:
            return True
        return self._store.news_recap(
            note.game_id, NewsLanguage.ES
        ) is not None or self._store.news_recap_missing(note.game_id, NewsLanguage.ES)

    def keep(self, feed_id: str) -> bool:
        return parse_id(feed_id) is not None

    def kind(self) -> FeedKind[NewsArticleFeed]:
        return FeedKind(
            KIND,
            NewsArticleFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
