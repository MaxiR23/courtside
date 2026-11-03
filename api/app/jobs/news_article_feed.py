# api/app/jobs/news_article_feed.py
#
# News article kind of the on-demand cache: one archived note by its id and
# language, with the site's own game (sides and score) when the site holds the game
# the note is about (ADR 0085). The id is "{lang}-{articleId}". The Spanish path
# also serves an English recap while no Spanish recap of its game is archived, as the
# Spanish pages list it. It reads no source:
# the note is already in the archive. A note not archived in that language, or with
# News off, is unknown (rule I).
#
# news_game and held_game are shared with the game recap kind: the game is the one
# the games job holds, else a final game of a stored day feed.
#
# A feed expires 15 minutes after its build, so a game the site gets later is
# picked up; a stale feed is served at once and rebuilt in the background.
#
# SEE: docs/api/news.md, docs/adr/0085-news-archive-and-feeds.md, docs/source-rules.md

import datetime as dt
import re

from app.feeds.days import PastGame
from app.feeds.news import NewsKind, NewsLanguage, NewsNote
from app.feeds.news_article import NewsArticleFeed, NewsGame
from app.jobs.games import GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus, UnknownFeedError
from app.jobs.past_game_detail_feed import PastGameDetailFeeds
from app.jobs.team_identity import without_identity
from app.settings import Settings
from app.sources.scoreboard import ScoreboardGame
from app.storage.state import StateStore

KIND = "news-articles"
FRESH_FOR = dt.timedelta(minutes=15)

_ID = re.compile(r"^(en|es)-([A-Za-z0-9-]+)$")


def news_game(game: ScoreboardGame | PastGame) -> NewsGame:
    """The site's game as a note shows it, without the team identities."""
    return NewsGame(
        id=game.id,
        away=without_identity(game.away),
        home=without_identity(game.home),
        score=game.score,
    )


def held_game(
    games: GamesJob, past: PastGameDetailFeeds, game_id: str
) -> ScoreboardGame | PastGame | None:
    """The game a day of the games job holds, else the final game of a stored day
    feed, else None. Reads no source."""
    return games.loaded_game(game_id) or past.past_game(game_id)


class NewsArticleFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        cache: FeedCache,
        games: GamesJob,
        past: PastGameDetailFeeds,
    ) -> None:
        self._settings = settings
        self._store = store
        self._games = games
        self._past = past
        cache.register(self.kind())

    def _note(self, feed_id: str) -> NewsNote | None:
        found = _ID.fullmatch(feed_id)
        if not self._settings.news_enabled or found is None:
            return None
        language, article_id = NewsLanguage(found.group(1)), found.group(2)
        note = self._store.news_note(article_id, language)
        if note is None and language is NewsLanguage.ES:
            english = self._store.news_note(article_id, NewsLanguage.EN)
            if (
                english is not None
                and english.kind is NewsKind.RECAP
                and (
                    english.game_id is None
                    or self._store.news_recap(english.game_id, NewsLanguage.ES) is None
                )
            ):
                return english
        return note

    def check(self, feed_id: str) -> IdStatus:
        return IdStatus.UNKNOWN if self._note(feed_id) is None else IdStatus.KNOWN

    async def build(self, feed_id: str) -> NewsArticleFeed:
        note = self._note(feed_id)
        if note is None:
            raise UnknownFeedError(f"{KIND} {feed_id}")
        game = None if note.game_id is None else self._held(note.game_id)
        return NewsArticleFeed(note=note, game=game)

    def _held(self, game_id: str) -> NewsGame | None:
        game = held_game(self._games, self._past, game_id)
        return None if game is None else news_game(game)

    def is_fresh(
        self, feed: NewsArticleFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return now - built_at < FRESH_FOR

    def keep(self, feed_id: str) -> bool:
        return _ID.fullmatch(feed_id) is not None

    def kind(self) -> FeedKind[NewsArticleFeed]:
        return FeedKind(
            KIND,
            NewsArticleFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
