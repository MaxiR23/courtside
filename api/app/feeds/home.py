# api/app/feeds/home.py
#
# Feed models for the home feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# The scenario, the dates, the statuses and the titles are decided by the backend.
# The game sides, score, winner and accent are the games feed's shapes (Opponent,
# Score, Side, GameAccent); the logo and colors of a side and the accent of a game are
# added when the feed is served, never stored (ADR 0068).
#
# SEE: docs/api/home.md, docs/adr/0074-home-feed.md

import datetime as dt
from enum import StrEnum
from typing import Annotated

from pydantic import Field, PositiveInt, model_validator

from app.feeds.base import FeedModel, NonEmptyStr, SeasonLabel, UtcDatetime
from app.feeds.games import GameAccent, Score
from app.feeds.opponent import Opponent, Side


class HomeScenario(StrEnum):
    OFF_DAY = "offDay"
    ALL_STAR_BREAK = "allStarBreak"
    FINALS_PREVIEW = "finalsPreview"
    OFFSEASON = "offseason"


# The order of the members is the tie order of items on the same start date.
class ComingUpKey(StrEnum):
    OPENING_NIGHT = "openingNight"
    CUP_GROUP_STAGE = "cupGroupStage"
    CUP_KNOCKOUT = "cupKnockout"
    CUP_FINAL = "cupFinal"
    ALL_STAR = "allStar"
    PLAY_IN = "playIn"
    PLAYOFFS = "playoffs"
    FINALS = "finals"
    PRESEASON = "preseason"


class ComingUpStatus(StrEnum):
    DONE = "done"
    NOW = "now"
    UPCOMING = "upcoming"


class ComingUpItem(FeedModel):
    key: ComingUpKey
    start_date: dt.date
    # Null for a single day.
    end_date: dt.date | None
    status: ComingUpStatus

    @model_validator(mode="after")
    def _require_an_end_after_the_start(self) -> ComingUpItem:
        if self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("the end date must be after the start date")
        return self


class NextGame(FeedModel):
    date: dt.date
    first_tip_off: UtcDatetime
    broadcast: NonEmptyStr | None
    game_count: PositiveInt
    # The day is inside the games feed window, so the page can select it.
    in_games_window: bool


class LastGamesTitleKey(StrEnum):
    LAST_NIGHT = "lastNight"
    DAYS_AGO = "daysAgo"
    BEFORE_THE_BREAK = "beforeTheBreak"
    CONFERENCE_FINALS = "conferenceFinals"
    LAST_GAMES_PLAYED = "lastGamesPlayed"


class LastGamesTitle(FeedModel):
    key: LastGamesTitleKey
    days: Annotated[int, Field(ge=2)] | None

    @model_validator(mode="after")
    def _require_days_exactly_for_days_ago(self) -> LastGamesTitle:
        if (self.days is not None) != (self.key is LastGamesTitleKey.DAYS_AGO):
            raise ValueError("days is set exactly when the key is daysAgo")
        return self


class LastGameLabel(StrEnum):
    FINAL = "final"
    FINAL_OVERTIME = "finalOvertime"
    PLAY_IN = "playIn"
    FIRST_ROUND = "firstRound"
    CONFERENCE_SEMIFINALS = "conferenceSemifinals"
    CONFERENCE_FINALS = "conferenceFinals"
    FINALS = "finals"


NUMBERED_LABELS = (
    LastGameLabel.FIRST_ROUND,
    LastGameLabel.CONFERENCE_SEMIFINALS,
    LastGameLabel.CONFERENCE_FINALS,
    LastGameLabel.FINALS,
)


class LastGame(FeedModel):
    id: NonEmptyStr
    away: Opponent
    home: Opponent
    score: Score
    winner: Side | None
    label: LastGameLabel
    game_number: Annotated[int, Field(ge=1, le=7)] | None
    # The resolved color of each side (ADR 0068, ADR 0072), added when served; null in
    # the stored file.
    accent: GameAccent | None = None

    @model_validator(mode="after")
    def _require_a_game_number_only_in_a_playoff_series(self) -> LastGame:
        if self.game_number is not None and self.label not in NUMBERED_LABELS:
            raise ValueError("only a playoff round or the Finals has a game number")
        return self


class LastGames(FeedModel):
    date: dt.date
    title: LastGamesTitle
    games: Annotated[list[LastGame], Field(min_length=1)]


class HomeFeed(FeedModel):
    season: SeasonLabel
    date: dt.date
    scenario: HomeScenario
    coming_up: Annotated[list[ComingUpItem], Field(min_length=1)] | None
    next_game: NextGame | None
    last_games: LastGames | None
    # Filled by part 2 (issue 4); always null here.
    leaders: None
    finals_path: None
