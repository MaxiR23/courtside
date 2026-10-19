# api/app/jobs/past_game_detail_feed.py
#
# Past game detail builder and kind: the detail of a final game of a stored day
# feed (ADR 0041). The builder is a pure function from the stored day feed's
# game and the game detail sections the adapter returned; it reads no clock and
# no source. The game gives the id, status, time, broadcast, line score, score,
# winner, marks, sides and highlights search link. The sections give the venue,
# box score, team stats, win probability and the season. Every block that would
# describe today is null: injuries, last games, standings, stars, season
# series and both records. The highlights are null in the built feed: the stored
# highlight of the game is added when served, and a game served with none starts one
# on-demand search (ADR 0065).
#
# PastGameDetailFeeds is the feed kind of the on-demand cache: the id is the
# game id, the feed is stored at feeds/past-games/{id}.json only when requested.
# An id is known when it is a final game of a stored day feed, or a game a past
# team or player feed registered with its date (ADR 0053); the day feed of that
# date is then built first. The kind never answers not ready and reads no source
# to answer. A feed is built once
# and kept (rule D): it is never refreshed by the games job, the live refresh
# or the highlights job; it is deleted with its build row when not served in 90
# days and rebuilt on its next request (ADR 0063), and rebuilt otherwise only
# when its build version is not the current one, from a day feed of the current
# version (ADR 0053). A built game is registered in past_games with its date, so
# its id stays known when its day feed is deleted. The build declares a read budget of READ_BUDGET source read: the
# game summary (ADR 0059).
#
# SEE: docs/api/game-detail.md, docs/adr/0041-past-game-detail.md,
# docs/adr/0048-highlights-backfill-and-edition-video.md,
# docs/adr/0065-background-work-limited-to-games-highlights-and-stars.md,
# docs/adr/0063-bounded-state-and-kept-feeds.md,
# docs/source-rules.md, api/app/jobs/day_feed.py

import datetime as dt
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.feeds.days import DayFeed, PastGame
from app.feeds.game_detail import PastGameDetailFeed
from app.feeds.games import GameStatus
from app.jobs.day_feed import KIND as DAY_KIND
from app.jobs.highlights_search import HighlightsSearch
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.team_feed import season_label
from app.settings import Settings
from app.sources import game_detail
from app.sources.game_detail import GameDetailSections
from app.sources.http import Freshness, ReadBudget, SourceClient, within_budget
from app.storage.feeds import GAME_ID, published_ids, read_by_id
from app.storage.state import StateStore

KIND = "past-games"
READ_BUDGET = 1
# The source cache's freshness of rule A for everything else: the one summary read.
PAST_FRESH = dt.timedelta(hours=1)

FetchPastSections = Callable[
    [SourceClient, str, Settings, Freshness], Awaitable[GameDetailSections]
]


class PastDetailBuildError(Exception):
    """The past game detail built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_past_game_detail_feed(
    game: PastGame, sections: GameDetailSections
) -> PastGameDetailFeed:
    """Build the past game detail; raise PastDetailBuildError when the game is
    not final, the summary gave no season or the feed is not valid."""
    if game.status is not GameStatus.FINAL:
        raise PastDetailBuildError(f"game {game.id} is not final")
    if sections.season is None:
        raise PastDetailBuildError(f"game {game.id} has no season")
    data: dict[str, Any] = {
        "id": game.id,
        "status": game.status,
        "start_time": game.start_time,
        "broadcast": game.broadcast,
        "period": game.period,
        "clock": game.clock,
        "line_score": game.line_score,
        "score": game.score,
        "winner": game.winner,
        "cup": game.cup,
        "postseason": game.postseason,
        "all_star": game.all_star,
        "venue": sections.venue,
        "team_stats": sections.team_stats,
        "box_score": sections.box_score,
        "leaders": sections.leaders,
        "win_probability": sections.win_probability,
        "win_probability_leader": sections.win_probability_leader,
        "win_probability_periods": sections.win_probability_periods,
        "away": {**game.away.model_dump(by_alias=False), "record": None},
        "home": {**game.home.model_dump(by_alias=False), "record": None},
        "standings": None,
        "injuries": None,
        "last_games": None,
        "season_series": None,
        "stars": None,
        "highlights": None,
        "highlights_search_url": game.highlights_search_url,
        "season_label": season_label(sections.season),
    }
    try:
        return PastGameDetailFeed.model_validate(data)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise PastDetailBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class PastGameDetailFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        *,
        fetch_sections: FetchPastSections = game_detail.fetch_past_game_detail_sections,
        search: HighlightsSearch | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._fetch_sections = fetch_sections
        self._search = search
        # Game id to the id of the stored day feed that lists it as final.
        self._days: dict[str, str] = {}
        # Day ids whose stored feed had every game final: kept by rule G and
        # never rebuilt, so they are read once.
        self._settled: set[str] = set()
        cache.register(self.kind())

    def _day_of(self, game_id: str) -> str | None:
        day_id = self._days.get(game_id)
        if day_id is not None:
            return day_id
        data_dir = self._settings.data_dir
        for candidate in sorted(published_ids(data_dir, DAY_KIND) - self._settled):
            body = read_by_id(data_dir, DAY_KIND, candidate)
            if body is None:
                continue
            try:
                feed = DayFeed.model_validate_json(body)
            except ValidationError:
                continue
            games = feed.day.games
            for stored in games:
                if stored.status is GameStatus.FINAL:
                    self._days[stored.id] = candidate
            if all(stored.status is GameStatus.FINAL for stored in games):
                self._settled.add(candidate)
        return self._days.get(game_id)

    def _current_day(self, day_id: str) -> DayFeed | None:
        body = read_by_id(self._settings.data_dir, DAY_KIND, day_id)
        if body is None:
            return None
        try:
            feed = DayFeed.model_validate_json(body)
        except ValidationError:
            return None
        return feed if is_current_build(feed) else None

    def _past_game(self, game_id: str) -> PastGame | None:
        day_id = self._day_of(game_id)
        if day_id is None:
            return None
        feed = self._current_day(day_id)
        if feed is None:
            # Not stored or not built by the current rules: building from it
            # would keep today's names for good (ADR 0053).
            return None
        return next(
            (
                stored
                for stored in feed.day.games
                if stored.id == game_id and stored.status is GameStatus.FINAL
            ),
            None,
        )

    def check(self, game_id: str) -> IdStatus:
        if GAME_ID.fullmatch(game_id) is None:
            return IdStatus.UNKNOWN
        if (
            self._store.past_game_date(game_id, at=self._client.clock()) is None
            and self._day_of(game_id) is None
        ):
            return IdStatus.UNKNOWN
        return IdStatus.KNOWN

    def depends_on(self, game_id: str) -> tuple[str, str] | None:
        # The day feed is made current first, so a rebuilt detail reads the names
        # of the current rules (ADR 0053).
        day_id = self._day_of(game_id)
        if day_id is not None:
            return None if self._current_day(day_id) else (DAY_KIND, day_id)
        registered = self._store.past_game_date(game_id, at=self._client.clock())
        return None if registered is None else (DAY_KIND, registered.isoformat())

    async def build(self, game_id: str) -> PastGameDetailFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET),
            f"past game detail: {game_id}",
            lambda: self._build(game_id),
        )

    async def _build(self, game_id: str) -> PastGameDetailFeed:
        game = self._past_game(game_id)
        if game is None:
            raise PastDetailBuildError(
                f"game {game_id} is not a final game of a stored day"
            )
        day_id = self._day_of(game_id)
        if day_id is not None:
            self._store.set_past_game_dates(
                {game_id: dt.date.fromisoformat(day_id)}, at=self._client.clock()
            )
        sections = await self._fetch_sections(
            self._client, game_id, self._settings, PAST_FRESH
        )
        return with_build_version(build_past_game_detail_feed(game, sections))

    def is_fresh(
        self, feed: PastGameDetailFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        # ADR 0057: a stored feed without the leaders key predates the field and
        # is rebuilt on its next request; a stored null is fresh.
        return is_current_build(feed) and "leaders" in feed.model_fields_set

    def wait_when_stale(self, game_id: str) -> bool:
        # ADR 0057: a stored detail without the leaders key is rebuilt before it
        # is served, so the day card's first read carries the leaders. Any other
        # stale reason is served as stored while it is rebuilt.
        body = read_by_id(self._settings.data_dir, KIND, game_id)
        if body is None:
            return False
        try:
            feed = PastGameDetailFeed.model_validate_json(body)
        except ValidationError:
            return False
        return "leaders" not in feed.model_fields_set

    def serve_with(self, game_id: str, feed: PastGameDetailFeed) -> PastGameDetailFeed:
        found = self._store.highlights_for([game_id]).get(game_id)
        if found is None and feed.all_star is None and self._search is not None:
            self._search.request_game(
                feed.id, feed.away.name, feed.home.name, feed.start_time
            )
        if found is None or feed.all_star is not None:
            return feed
        return PastGameDetailFeed.model_validate(
            {**feed.model_dump(by_alias=False), "highlights": [found]}
        )

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[PastGameDetailFeed]:
        return FeedKind(
            KIND,
            PastGameDetailFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            wait_when_stale=self.wait_when_stale,
            serve_with=self.serve_with,
            depends_on=self.depends_on,
        )
