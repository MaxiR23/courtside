# api/app/sources/season_calendar.py
#
# Calendar view of the scoreboard (ADR 0040).
#
# Reads the scoreboard day of February 1 of a season's end year, from the same
# URL with the same freshness as app.sources.scoreboard, and returns the season
# calendar: one UTC time per day with games. An entry that is not a readable
# time is skipped with a log line; a missing or empty calendar, or one with no
# readable entry, fails the read. Events are ignored.
#
# The shape is assumed, not recorded: leagues[0].calendar is a list of UTC
# timestamps such as "1999-02-05T08:00Z". The keys live in the two provider
# models below, so a different real shape is a one-line fix.
#
# SEE: docs/api/calendar.md, docs/adr/0040-calendar-and-day-feeds.md

import datetime as dt
import logging
from typing import Any

from pydantic import Field, ValidationError

from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.scoreboard import DATE_FORMAT, FRESH_FOR, SOURCE, _ProviderModel

logger = logging.getLogger(__name__)

CALENDAR_DAY = (2, 1)  # month, day


class _ProviderLeague(_ProviderModel):
    calendar: list[Any] | None = None


class _CalendarScoreboard(_ProviderModel):
    leagues: list[_ProviderLeague] = Field(default_factory=list)


def _moment(entry: Any) -> dt.datetime | None:
    """The entry as an aware UTC time, or None when it is not one."""
    if not isinstance(entry, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(entry)
    except ValueError:
        return None
    if moment.utcoffset() is None:
        return None
    return moment.astimezone(dt.UTC)


async def fetch_season_calendar(
    client: SourceClient, season: int, settings: Settings
) -> list[dt.datetime]:
    """Return the UTC times of the season's calendar in provider order, or raise
    SourceError."""
    if settings.scoreboard_url is None:
        raise SourceError(SOURCE, "scoreboard URL is not configured")
    day = dt.date(season, *CALENDAR_DAY)
    url = settings.scoreboard_url.format(date=day.strftime(DATE_FORMAT))
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        scoreboard = _CalendarScoreboard.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
    if not scoreboard.leagues:
        raise SourceError(SOURCE, f"season {season} has no league")
    entries = scoreboard.leagues[0].calendar
    if not entries:
        raise SourceError(SOURCE, f"season {season} has no calendar")
    moments: list[dt.datetime] = []
    for index, entry in enumerate(entries):
        moment = _moment(entry)
        if moment is None:
            logger.warning(
                "scoreboard: calendar entry %d of season %d skipped", index, season
            )
            continue
        moments.append(moment)
    if not moments:
        raise SourceError(SOURCE, f"season {season} has no readable calendar entry")
    return moments
