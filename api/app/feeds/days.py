# api/app/feeds/days.py
#
# Feed models for the day feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# A day is a past US Eastern day with the games feed's Game shape, except that
# no star of a past season exists. It carries the end year of the day's season
# and its label.
#
# SEE: docs/api/days.md, docs/adr/0040-calendar-and-day-feeds.md

import datetime as dt
from typing import Annotated

from pydantic import Field, PositiveInt, model_validator

from app.feeds.calendar import FIRST_SEASON
from app.feeds.games import FeedModel, Game, UtcDatetime
from app.feeds.player import SeasonLabel


# A game of a past day: the games feed's Game, but no star of a past season
# exists, so both stars are null. No highlight is stored; the stored one is
# added when the feed is served (ADR 0048).
class PastGame(Game):
    @model_validator(mode="after")
    def _require_stars_of_the_league_sides(self) -> PastGame:
        # Same name as Game's validator: it replaces that rule.
        if self.stars.away is not None or self.stars.home is not None:
            raise ValueError("a game of a past day has no star")
        return self


# A day of the day feed: the games feed's Day, with PastGame.
class PastDay(FeedModel):
    date: dt.date
    games: list[PastGame]


class DayFeed(FeedModel):
    generated_at: UtcDatetime
    season: Annotated[int, Field(ge=FIRST_SEASON)]
    season_label: SeasonLabel
    day: PastDay
    # The rules version of a kept past day (ADR 0053); null on a day not yet
    # final and on a stored feed from before the field.
    build_version: PositiveInt | None = None
