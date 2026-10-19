# api/app/jobs/day_feed.py
#
# Day feed builder and kind: the games of one past US Eastern day. The builder
# is a pure function from the games the scoreboard adapter returned to the feed;
# it reads no clock and no source. A game is the games feed's Game with the
# past-day rules: no star, no stored highlight, and for a final game stats available,
# read from its game detail (ADR 0054); leaders and team stats stay null, with the
# search link as in the games feed. A game that is not a valid PastGame is skipped with a log line
# by event id. A day with no game is a valid day with an empty list. The feed
# carries the season the scoreboard gave for the day and its label (ADR 0042).
#
# DayFeeds is the feed kind of the on-demand cache: the id is the date
# (YYYY-MM-DD), the feed is stored at feeds/days/{date}.json only when requested.
# The date is unknown (404) when it is not a real date, is before 1993-10-01,
# is after today (US Eastern) or is a day of the games feed: the days the games
# job shows, from its memory (ADR 0066); before its first run the stored window,
# or with none stored the days the games job would show. It expires (rule G)
# 6 hours after the build when a game is not final, and is kept when every game
# is final or there is no game. It is deleted with its build row when not served in 90 days and rebuilt on its
# next request (ADR 0063), and it never enters the
# games job, the hero, the highlights job or the live refresh (ADR 0040). The
# stored highlight of a final game is added when served, never stored (ADR
# 0048); an All-Star game gets none. The league sides of a day are named from the
# scoreboard payload with the season code of the stored franchise names (ADR
# 0059); a guest side keeps its name. A published feed is passed to on_publish
# (ADR 0066). The build declares a read budget of
# READ_BUDGET source read: the scoreboard.
#
# SEE: docs/api/days.md, docs/adr/0040-calendar-and-day-feeds.md,
# docs/adr/0048-highlights-backfill-and-edition-video.md,
# api/app/jobs/standings_feed.py

import datetime as dt
import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.feeds.days import DayFeed, PastGame
from app.feeds.games import GamesFeed, GameStatus, StatsAvailability
from app.jobs.games import GamesJob, days_shown, eastern_date, final_winner
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.team_feed import season_label
from app.jobs.team_names import TeamNamesFeeds, payload_names, season_named
from app.settings import Settings
from app.sources import scoreboard, video_channel
from app.sources.http import ReadBudget, SourceClient, within_budget
from app.sources.scoreboard import PastScoreboardDay, ScoreboardGame
from app.storage.feeds import read_feed
from app.storage.state import StateStore

logger = logging.getLogger(__name__)

KIND = "days"
READ_BUDGET = 1
FIRST_DAY = dt.date(1993, 10, 1)
REBUILD_AFTER = dt.timedelta(hours=6)
_DAY_ID = re.compile(r"\d{4}-\d{2}-\d{2}")

FetchPastDay = Callable[[SourceClient, dt.date, Settings], Awaitable[PastScoreboardDay]]
SearchUrl = Callable[[ScoreboardGame], str | None]


class DayBuildError(Exception):
    """The day feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def stored_window_days(data_dir: Path) -> list[dt.date] | None:
    """The days of the stored games feed, or None when none is stored or valid."""
    body = read_feed(data_dir, "games")
    if body is None:
        return None
    try:
        feed = GamesFeed.model_validate_json(body)
    except ValidationError:
        return None
    return [day.date for day in feed.days]


def parse_day(feed_id: str) -> dt.date | None:
    """The date of a YYYY-MM-DD id, or None when it is not a real date."""
    if _DAY_ID.fullmatch(feed_id) is None:
        return None
    try:
        return dt.date.fromisoformat(feed_id)
    except ValueError:
        return None


def build_day_feed(
    generated_at: dt.datetime,
    day: dt.date,
    season: int,
    games: Sequence[ScoreboardGame],
    highlights_search_url: SearchUrl,
) -> DayFeed:
    """Build the day feed; raise DayBuildError when it is not valid."""
    built: list[dict[str, Any]] = []
    for game in games:
        final = game.status is GameStatus.FINAL
        data = game.model_dump(by_alias=False)
        data["stars"] = {"away": None, "home": None}
        data["highlights"] = []
        data["winner"] = final_winner(game)
        data["highlights_search_url"] = highlights_search_url(game) if final else None
        data["stats_availability"] = StatsAvailability.AVAILABLE if final else None
        data["leaders"] = None
        data["team_stats"] = None
        try:
            PastGame.model_validate(data)
        except ValidationError as error:
            first = error.errors()[0]
            location = ".".join(str(part) for part in first["loc"])
            logger.warning(
                "days: game %s skipped: %s at %s", game.id, first["type"], location
            )
            continue
        built.append(data)
    try:
        return DayFeed.model_validate(
            {
                "generated_at": generated_at,
                "season": season,
                "season_label": season_label(season),
                "day": {"date": day, "games": built},
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise DayBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class DayFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        names: TeamNamesFeeds,
        *,
        fetch_past_day: FetchPastDay = scoreboard.fetch_past_day,
        on_publish: Callable[[str, DayFeed], None] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._games = games
        self._names = names
        self._on_publish = on_publish
        self._fetch_past_day = fetch_past_day
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        day = parse_day(feed_id)
        if day is None or day < FIRST_DAY:
            return IdStatus.UNKNOWN
        today = eastern_date(self._client.clock())
        if day > today:
            return IdStatus.UNKNOWN
        window = self._games.shown_days()
        if window is None:
            window = stored_window_days(self._settings.data_dir)
        if window is None:
            window = days_shown(today)
        return IdStatus.UNKNOWN if day in window else IdStatus.KNOWN

    def _search_url(self, game: ScoreboardGame) -> str | None:
        return video_channel.search_url(
            game, eastern_date(game.start_time), self._settings
        )

    async def build(self, feed_id: str) -> DayFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET), f"day: {feed_id}", lambda: self._build(feed_id)
        )

    async def _build(self, feed_id: str) -> DayFeed:
        day = parse_day(feed_id)
        if day is None:
            raise DayBuildError(f"{feed_id!r} is not a day")
        past = await self._fetch_past_day(self._client, day, self._settings)
        runs = {
            code: found for code in past.teams if (found := self._names.stored(code))
        }
        names = payload_names(past.teams, runs)
        games = [
            game.model_copy(
                update={
                    "away": season_named(game.away, names),
                    "home": season_named(game.home, names),
                }
            )
            for game in past.games
        ]
        return with_build_version(
            build_day_feed(
                self._client.clock(), day, past.season, games, self._search_url
            )
        )

    def is_fresh(self, feed: DayFeed, built_at: dt.datetime, now: dt.datetime) -> bool:
        if all(game.status is GameStatus.FINAL for game in feed.day.games):
            return is_current_build(feed)
        return now - built_at < REBUILD_AFTER

    def serve_with(self, feed_id: str, feed: DayFeed) -> DayFeed:
        highlights = self._store.highlights_for(game.id for game in feed.day.games)
        data = feed.model_dump(by_alias=False)
        for game in data["day"]["games"]:
            found = highlights.get(game["id"])
            if found is not None and game["all_star"] is None:
                game["highlights"] = [found.model_dump(by_alias=False)]
        return DayFeed.model_validate(data)

    def _after_publish(self, feed_id: str, feed: DayFeed) -> None:
        if self._on_publish is not None:
            self._on_publish(feed_id, feed)

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[DayFeed]:
        return FeedKind(
            KIND,
            DayFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            after_publish=self._after_publish,
        )
