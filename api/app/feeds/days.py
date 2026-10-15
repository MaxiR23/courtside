# api/app/feeds/days.py
#
# Feed models for the day feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# A day is a past US Eastern day with the games feed's Game shape, except that
# no star of a past season exists.
#
# SEE: docs/api/days.md, docs/adr/0040-calendar-and-day-feeds.md

import datetime as dt

from pydantic import model_validator

from app.feeds.games import FeedModel, Game, UtcDatetime


# A game of a past day: the games feed's Game, but no star of a past season
# exists, so both stars are null, and no highlight is matched.
class PastGame(Game):
    @model_validator(mode="after")
    def _require_stars_of_the_league_sides(self) -> PastGame:
        # Same name as Game's validator: it replaces that rule.
        if self.stars.away is not None or self.stars.home is not None:
            raise ValueError("a game of a past day has no star")
        if self.highlights:
            raise ValueError("a game of a past day has no highlights")
        return self


# A day of the day feed: the games feed's Day, with PastGame.
class PastDay(FeedModel):
    date: dt.date
    games: list[PastGame]


class DayFeed(FeedModel):
    generated_at: UtcDatetime
    day: PastDay
