# api/app/feeds/calendar.py
#
# Feed models for the calendar feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# A season is its end year (2026 is the season 2025-26); its days are the US
# Eastern dates on which the season has games, sorted and unique. The seasons
# list runs from the current season down to 1994, newest first, for the selector.
#
# SEE: docs/api/calendar.md, docs/adr/0040-calendar-and-day-feeds.md

import datetime as dt
from itertools import pairwise
from typing import Annotated

from pydantic import Field, PositiveInt, model_validator

from app.feeds.games import FeedModel, UtcDatetime
from app.feeds.player import SeasonLabel

FIRST_SEASON = 1994


class CalendarSeason(FeedModel):
    season: Annotated[int, Field(ge=FIRST_SEASON)]
    season_label: SeasonLabel


class CalendarFeed(FeedModel):
    generated_at: UtcDatetime
    season: Annotated[int, Field(ge=FIRST_SEASON)]
    season_label: SeasonLabel
    first_day: dt.date
    last_day: dt.date
    days: Annotated[list[dt.date], Field(min_length=1)]
    window_days: list[dt.date]
    seasons: Annotated[list[CalendarSeason], Field(min_length=1)]
    # The rules version of a kept past calendar (ADR 0053, ADR 0055); null on a
    # current calendar and on a stored feed from before the field.
    build_version: PositiveInt | None = None

    @model_validator(mode="after")
    def _require_sorted_unique_days(self) -> CalendarFeed:
        if any(a >= b for a, b in zip(self.days, self.days[1:], strict=False)):
            raise ValueError("days are sorted and unique")
        return self

    @model_validator(mode="after")
    def _require_the_ends_of_the_days(self) -> CalendarFeed:
        if self.first_day != self.days[0] or self.last_day != self.days[-1]:
            raise ValueError("firstDay and lastDay are the first and last day")
        return self

    @model_validator(mode="after")
    def _require_the_seasons(self) -> CalendarFeed:
        years = [item.season for item in self.seasons]
        if (
            any(a - b != 1 for a, b in pairwise(years))
            or years[-1] != FIRST_SEASON
            or self.season not in years
        ):
            raise ValueError(
                "seasons run newest first down to 1994 and hold the season"
            )
        return self
