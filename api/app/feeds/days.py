# api/app/feeds/days.py
#
# Feed models for the day feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# A day is a past US Eastern day with the games feed's Game shape, except that
# no star of a past season exists and a final game's stats are available without
# leaders or team stats (ADR 0054). It carries the end year of the day's season
# and its label.
#
# SEE: docs/api/days.md, docs/adr/0040-calendar-and-day-feeds.md

import datetime as dt
from typing import Annotated

from pydantic import Field, PositiveInt, model_validator

from app.feeds.calendar import FIRST_SEASON
from app.feeds.games import FeedModel, Game, GameStatus, UtcDatetime
from app.feeds.player import SeasonLabel


# A game of a past day: the games feed's Game, but no star of a past season
# exists, so both stars are null. No highlight is stored; the stored one is
# added when the feed is served (ADR 0048). The leaders and team stats of a final
# past game are in its game detail (ADR 0041, ADR 0053), so its stats are
# available and the day feed carries neither (ADR 0054).
class PastGame(Game):
    @model_validator(mode="after")
    def _require_stars_of_the_league_sides(self) -> PastGame:
        # Same name as Game's validator: it replaces that rule.
        if self.stars.away is not None or self.stars.home is not None:
            raise ValueError("a game of a past day has no star")
        return self

    @model_validator(mode="after")
    def _require_stats_of_their_availability(self) -> PastGame:
        # Same name as Game's validator: it replaces that rule.
        if self.stats_availability is not None and self.status is not GameStatus.FINAL:
            raise ValueError(f"a {self.status} game has no statsAvailability")
        if self.leaders is not None or self.team_stats is not None:
            raise ValueError("a game of a past day has no leaders or teamStats")
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
