# api/app/jobs/news_feed.py
#
# News list kind of the on-demand cache: one page of notes of the league, of a team
# or of a player, in English or Spanish, newest first, 12 to a page (ADR 0085). The
# ids are "{lang}-league-{page}", "{lang}-team-{code}-{page}" and
# "{lang}-player-{playerId}-{page}", with the team code in lower case.
#
# A build reads the scope's list (the league list; a team's list; a player's list is
# his current team's), stores the notes it reads in the archive and pages from the
# archive, so a failed read never fails the feed: it is logged and the feed is built
# from the archive. The list read goes through the shared source cache for 15
# minutes, so every page, scope and concurrent build shares one read. With News off
# every id is unknown: nothing is built and no request is sent (rule I).
#
# A team page is known when the code is one of the 30. A player page is known when
# a roster lists him or a stored note names him, and not ready before the rosters.
# A page past the first is known only when the archive holds more notes than the
# pages before it. A feed expires 15 minutes after its build; a stale feed is served
# at once and rebuilt in the background.
#
# SEE: docs/api/news.md, docs/adr/0085-news-archive-and-feeds.md, docs/source-rules.md

import datetime as dt
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.feeds.news import PAGE_SIZE, NewsFeed, NewsLanguage, NewsNote
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.stars import StarsJob
from app.jobs.team_feed import TEAM_IDS as TEAM_FEED_CODES
from app.settings import Settings
from app.sources import news
from app.sources.http import ReadBudget, SourceClient, SourceError, within_budget
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

KIND = "news"
# The list reads one build sends (ADR 0085).
READ_BUDGET = 1
FRESH_FOR = dt.timedelta(minutes=15)

_ID = re.compile(
    r"^(en|es)-(?:(league)|team-([a-z]{3})|player-([A-Za-z0-9]+))-([1-9][0-9]{0,7})$"
)

FetchList = Callable[
    [SourceClient, Settings, NewsLanguage, str | None], Awaitable[list[NewsNote]]
]


@dataclass(frozen=True)
class NewsScope:
    language: NewsLanguage
    team: str | None
    player_id: str | None
    page: int


def parse_id(feed_id: str) -> NewsScope | None:
    """The scope of a feed id, or None when it is not one."""
    found = _ID.fullmatch(feed_id)
    if found is None:
        return None
    language, _, team, player_id, page = found.groups()
    if team is not None and team not in TEAM_FEED_CODES:
        return None
    return NewsScope(
        NewsLanguage(language),
        None if team is None else team.upper(),
        player_id,
        int(page),
    )


class NewsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        *,
        fetch_list: FetchList = news.fetch_news_list,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._fetch_list = fetch_list
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        scope = parse_id(feed_id)
        if not self._settings.news_enabled or scope is None:
            return IdStatus.UNKNOWN
        if scope.player_id is not None and not (
            self._stars.player_team(scope.player_id) is not None
            or self._store.news_names_player(scope.player_id)
        ):
            if not self._stars.rosters_ready():
                return IdStatus.NOT_READY
            return IdStatus.UNKNOWN
        if scope.page > 1 and (
            self._store.count_news_notes(
                scope.language, team=scope.team, player_id=scope.player_id
            )
            <= (scope.page - 1) * PAGE_SIZE
        ):
            return IdStatus.UNKNOWN
        return IdStatus.KNOWN

    async def _read(self, feed_id: str, scope: NewsScope) -> list[NewsNote]:
        team = scope.team
        if scope.player_id is not None:
            team = self._stars.player_team(scope.player_id)
            if team is None:
                return []
        try:
            return await self._fetch_list(
                self._client, self._settings, scope.language, team
            )
        except SourceError as error:
            # The reason never carries the URL. The feed is built from the archive.
            logger.warning("News list of %s not read: %s", feed_id, error.reason)
            return []

    async def build(self, feed_id: str) -> NewsFeed:
        scope = parse_id(feed_id)
        if scope is None:
            raise ValueError(f"not a news id: {feed_id}")
        notes = await within_budget(
            ReadBudget(READ_BUDGET, stop_on_rate_limit=False),
            f"news: {feed_id}",
            lambda: self._read(feed_id, scope),
        )
        self._store.add_news_notes(notes, self._client.clock())
        count = self._store.count_news_notes(
            scope.language, team=scope.team, player_id=scope.player_id
        )
        return NewsFeed(
            page=scope.page,
            has_more=count > scope.page * PAGE_SIZE,
            notes=self._store.news_notes(
                scope.language,
                team=scope.team,
                player_id=scope.player_id,
                offset=(scope.page - 1) * PAGE_SIZE,
                limit=PAGE_SIZE,
            ),
        )

    def is_fresh(self, feed: NewsFeed, built_at: dt.datetime, now: dt.datetime) -> bool:
        return now - built_at < FRESH_FOR

    def keep(self, feed_id: str) -> bool:
        # The daily cleanup deletes the ones not served in 90 days (ADR 0085).
        return parse_id(feed_id) is not None

    def kind(self) -> FeedKind[NewsFeed]:
        return FeedKind(
            KIND,
            NewsFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
