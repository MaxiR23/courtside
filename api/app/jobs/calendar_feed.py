# api/app/jobs/calendar_feed.py
#
# Calendar feed builder and kind: the days with games of one season. The builder
# is a pure function from the calendar times the adapter returned and the days of
# the stored games feed to the feed; it reads no clock and no source. Each time
# becomes its US Eastern date; the days are sorted and unique, firstDay and
# lastDay are the first and last of them, and windowDays are the days of the
# games feed stored at build time (empty when none was stored).
#
# CalendarFeeds is the feed kind of the on-demand cache: the id is the season's
# end year, the feed is stored at feeds/calendars/{season}.json only when
# requested. A season before 1994, after the current season or not four digits
# is unknown (404); while the stars job does not know the current season the
# answer is not ready (503). It expires (rule G) 24 hours after the build, and is
# kept once its season is past and it was built after the season's last day (the
# last day guard keeps a calendar stored while its season was current from being
# frozen at the season change). It is never deleted (ADR 0040). The id current
# resolves to the current season's end year before the cache, so it serves the
# same stored file (503 while the season is unknown). The feed's seasons run from
# the current season down to 1994 and are set again at serve time (ADR 0042).
#
# SEE: docs/api/calendar.md, docs/adr/0040-calendar-and-day-feeds.md,
# api/app/jobs/standings_feed.py

import datetime as dt
import re
from collections.abc import Awaitable, Callable, Sequence

from pydantic import ValidationError

from app.feeds.calendar import FIRST_SEASON, CalendarFeed
from app.jobs.day_feed import stored_window_days
from app.jobs.games import eastern_date
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.stars import StarsJob
from app.jobs.team_feed import season_label
from app.settings import Settings
from app.sources import season_calendar
from app.sources.http import SourceClient
from app.storage.state import StateStore

KIND = "calendars"
CURRENT_ID = "current"
CURRENT_FRESH_FOR = dt.timedelta(hours=24)
_SEASON_ID = re.compile(r"\d{4}")

FetchSeasonCalendar = Callable[
    [SourceClient, int, Settings], Awaitable[list[dt.datetime]]
]


class CalendarBuildError(Exception):
    """The calendar feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def seasons_until(current_season: int) -> list[dict[str, object]]:
    """The seasons from the current one down to 1994, newest first."""
    return [
        {"season": s, "season_label": season_label(s)}
        for s in range(current_season, FIRST_SEASON - 1, -1)
    ]


def build_calendar_feed(
    generated_at: dt.datetime,
    season: int,
    moments: Sequence[dt.datetime],
    window_days: Sequence[dt.date],
    current_season: int,
) -> CalendarFeed:
    """Build the calendar feed; raise CalendarBuildError when it is not valid."""
    days = sorted({eastern_date(moment) for moment in moments})
    try:
        return CalendarFeed.model_validate(
            {
                "generated_at": generated_at,
                "season": season,
                "season_label": season_label(season),
                "first_day": days[0] if days else None,
                "last_day": days[-1] if days else None,
                "days": days,
                "window_days": sorted(window_days),
                "seasons": seasons_until(current_season),
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise CalendarBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class CalendarFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        *,
        fetch_season_calendar: FetchSeasonCalendar = (
            season_calendar.fetch_season_calendar
        ),
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._fetch_season_calendar = fetch_season_calendar
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if _SEASON_ID.fullmatch(feed_id) is None or int(feed_id) < FIRST_SEASON:
            return IdStatus.UNKNOWN
        current = self._stars.current_season()
        if current is None:
            return IdStatus.NOT_READY
        return IdStatus.UNKNOWN if int(feed_id) > current else IdStatus.KNOWN

    async def build(self, feed_id: str) -> CalendarFeed:
        season = int(feed_id)
        moments = await self._fetch_season_calendar(
            self._client, season, self._settings
        )
        window = stored_window_days(self._settings.data_dir) or []
        current = self._stars.current_season()
        if current is None:
            raise CalendarBuildError("current season is not known")
        return build_calendar_feed(
            self._client.clock(), season, moments, window, current
        )

    def feed_id(self, season: str) -> str | None:
        """The id a route season maps to: current resolves to the current
        season's end year, or None while it is not known."""
        if season != CURRENT_ID:
            return season
        current = self._stars.current_season()
        return None if current is None else str(current)

    def serve_with(self, feed_id: str, feed: CalendarFeed) -> CalendarFeed:
        current = self._stars.current_season()
        if current is None:
            return feed
        return CalendarFeed.model_validate(
            {**feed.model_dump(by_alias=False), "seasons": seasons_until(current)}
        )

    def is_fresh(
        self, feed: CalendarFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        current = self._stars.current_season()
        if (
            current is not None
            and feed.season < current
            and eastern_date(built_at) > feed.last_day
        ):
            return True
        return now - built_at < CURRENT_FRESH_FOR

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[CalendarFeed]:
        return FeedKind(
            KIND,
            CalendarFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
        )
