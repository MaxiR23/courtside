# api/app/feeds/standings.py
#
# Feed models for the standings feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# Records, percentages, games behind and points are ready strings; the
# differentials carry a sign and a flag for the page to color them.
#
# SEE: docs/api/standings.md, docs/adr/0023-standings-feed.md

from enum import StrEnum
from typing import Annotated

from pydantic import (
    Field,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from app.feeds.game_detail import Conference
from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.feeds.player import SeasonLabel
from app.feeds.team import HexColor, Streak

RecordText = Annotated[str, StringConstraints(pattern=r"^\d+-\d+$")]
PctText = Annotated[str, StringConstraints(pattern=r"^(\.\d{3}|1\.000)$")]
GamesBehindText = Annotated[str, StringConstraints(pattern=r"^\d+\.\d$")]
PerGameText = Annotated[str, StringConstraints(pattern=r"^\d+\.\d$")]
# The minus sign is U+2212, not a hyphen.
SignedPerGame = Annotated[
    str, StringConstraints(pattern=r"^([+−]([1-9]\d*\.\d|0\.[1-9])|0\.0)$")
]
SignedTotal = Annotated[str, StringConstraints(pattern=r"^([+−][1-9]\d*|0)$")]


class Clinch(StrEnum):
    LEAGUE = "*"  # best record of the league; ranks above CONFERENCE
    CONFERENCE = "z"
    DIVISION = "y"
    PLAYOFFS = "x"
    PLAYIN = "xp"
    PLAYIN_POSITION = "pb"
    ELIMINATED = "e"


class StandingsState(StrEnum):
    FINAL = "final"
    REGULAR = "regular"


class StandingsColors(FeedModel):
    primary: HexColor | None
    secondary: HexColor | None


class PerGameDifferential(FeedModel):
    value: SignedPerGame
    non_negative: bool


class TotalDifferential(FeedModel):
    value: SignedTotal
    non_negative: bool


class StandingsRow(FeedModel):
    code: TeamCode
    city: NonEmptyStr
    name: NonEmptyStr
    colors: StandingsColors
    seed: Annotated[int, Field(ge=1, le=15)] | None
    clinch: Clinch | None
    wins: NonNegativeInt
    losses: NonNegativeInt
    pct: PctText | None
    games_behind: GamesBehindText | None
    streak: Streak | None
    home: RecordText
    away: RecordText
    last_ten: RecordText
    division: RecordText
    conference: RecordText
    points_for: PerGameText
    points_against: PerGameText
    differential: PerGameDifferential
    total: TotalDifferential


class ConferenceGroup(FeedModel):
    key: Conference
    name: NonEmptyStr
    team_count: PositiveInt
    teams: list[StandingsRow]

    @model_validator(mode="after")
    def _require_the_team_count(self) -> ConferenceGroup:
        if self.team_count != len(self.teams):
            raise ValueError("team count must equal the number of teams")
        return self


class DivisionGroup(FeedModel):
    name: NonEmptyStr
    conference: Conference
    teams: Annotated[list[StandingsRow], Field(min_length=1)]


class StandingsFeed(FeedModel):
    season: SeasonLabel
    state: StandingsState
    games_played: NonNegativeInt
    conferences: list[ConferenceGroup]
    divisions: list[DivisionGroup]

    @model_validator(mode="after")
    def _require_east_then_west(self) -> StandingsFeed:
        if [group.key for group in self.conferences] != [
            Conference.EAST,
            Conference.WEST,
        ]:
            raise ValueError("conferences must be east then west")
        return self
