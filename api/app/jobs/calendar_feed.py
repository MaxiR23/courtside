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
# frozen at the season change). It is never deleted (ADR 0040).
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


def build_calendar_feed(
    generated_at: dt.datetime,
    season: int,
    moments: Sequence[dt.datetime],
    window_days: Sequence[dt.date],
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
        return build_calendar_feed(self._client.clock(), season, moments, window)

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
        )
