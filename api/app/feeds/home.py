# api/app/feeds/home.py
#
# Feed models for the home feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# The scenario, the dates, the statuses and the titles are decided by the backend.
# The game sides, score, winner and accent are the games feed's shapes (Opponent,
# Score, Side, GameAccent); the logo and colors of a side and the accent of a game are
# added when the feed is served, never stored (ADR 0068).
# The leaders (one per per-game category) and the Finals path (the way each finalist
# reached the Finals) are the home's own shapes; their teams are the feed's Opponent.
#
# SEE: docs/api/home.md, docs/adr/0074-home-feed.md

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated

from pydantic import Field, HttpUrl, PositiveInt, StringConstraints, model_validator

from app.feeds.base import (
    FeedModel,
    HexColor,
    NonEmptyStr,
    SeasonLabel,
    TeamCode,
    UtcDatetime,
)
from app.feeds.games import GameAccent, Score
from app.feeds.opponent import Opponent, Side, TeamColors, TeamLogo


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


class HomeLeadersTitle(StrEnum):
    SEASON = "season"
    PLAYOFFS = "playoffs"
    PREVIOUS_SEASON = "previousSeason"


# Per-game only, in display order; the values equal app.feeds.playoffs.LeaderCategory's.
class HomeLeaderCategory(StrEnum):
    POINTS = "points"
    REBOUNDS = "rebounds"
    ASSISTS = "assists"
    BLOCKS = "blocks"


class HomeLeaderTeam(FeedModel):
    code: TeamCode
    # The logo and colors (ADR 0068) and the resolved color (ADR 0072), added when
    # served; null in the stored file.
    logo: TeamLogo | None = None
    colors: TeamColors | None = None
    accent: HexColor | None = None


class HomeLeader(FeedModel):
    category: HomeLeaderCategory
    player_id: NonEmptyStr
    # A dash when the identity was not read.
    name: NonEmptyStr
    photo_url: HttpUrl | None
    team: HomeLeaderTeam | None
    value: NonEmptyStr


class HomeLeaders(FeedModel):
    title: HomeLeadersTitle
    season_label: SeasonLabel | None
    categories: Annotated[list[HomeLeader], Field(min_length=1, max_length=4)]

    @model_validator(mode="after")
    def _require_the_label_exactly_for_the_previous_season(self) -> HomeLeaders:
        if (self.season_label is not None) != (
            self.title is HomeLeadersTitle.PREVIOUS_SEASON
        ):
            raise ValueError(
                "the season label is set exactly when the title is previousSeason"
            )
        return self

    @model_validator(mode="after")
    def _require_the_categories_in_order(self) -> HomeLeaders:
        order = list(HomeLeaderCategory)
        positions = [order.index(leader.category) for leader in self.categories]
        if any(a >= b for a, b in pairwise(positions)):
            raise ValueError("the categories follow the display order, with no repeat")
        return self


class PathRound(StrEnum):
    FIRST_ROUND = "firstRound"
    CONFERENCE_SEMIFINALS = "conferenceSemifinals"
    CONFERENCE_FINALS = "conferenceFinals"


# Own wins, an en dash (U+2013), then the opponent's wins.
SeriesResult = Annotated[str, StringConstraints(pattern=r"^[0-4]–[0-4]$")]


class PathSeries(FeedModel):
    round: PathRound
    opponent: Opponent
    result: SeriesResult
    won: bool
    # The opponent's resolved color (ADR 0072), added when served; null when stored.
    accent: HexColor | None = None


class FinalistPath(FeedModel):
    team: Opponent
    # The finalist's resolved color (ADR 0072), added when served; null when stored.
    accent: HexColor | None = None
    series: Annotated[list[PathSeries], Field(min_length=3, max_length=3)]

    @model_validator(mode="after")
    def _require_the_rounds_in_order(self) -> FinalistPath:
        if [s.round for s in self.series] != list(PathRound):
            raise ValueError("the series follow the round order")
        return self


class FinalsPath(FeedModel):
    finalists: Annotated[list[FinalistPath], Field(min_length=2, max_length=2)]


class HomeFeed(FeedModel):
    season: SeasonLabel
    date: dt.date
    scenario: HomeScenario
    coming_up: Annotated[list[ComingUpItem], Field(min_length=1)] | None
    next_game: NextGame | None
    last_games: LastGames | None
    leaders: HomeLeaders | None
    finals_path: FinalsPath | None
