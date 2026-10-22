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

from app.feeds.base import HexColor
from app.feeds.game_detail import Conference
from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.feeds.opponent import TeamLogo
from app.feeds.player import SeasonLabel
from app.feeds.team import Streak

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
    home: RecordText | None
    away: RecordText | None
    last_ten: RecordText
    division: RecordText
    conference: RecordText
    points_for: PerGameText | None
    points_against: PerGameText | None
    differential: PerGameDifferential | None
    total: TotalDifferential | None
    # The abbreviation the team had in the season on show and whether that season's
    # name, city or abbreviation differs from today's (ADR 0054). Null and false on a
    # current feed and on a stored feed from before the fields.
    season_code: NonEmptyStr | None = None
    historical: bool = False
    # The team's logo (ADR 0068); null on a historical row and when unknown.
    logo: TeamLogo | None = None

    @model_validator(mode="after")
    def _require_a_season_code_of_a_historical_row(self) -> StandingsRow:
        if self.historical and self.season_code is None:
            raise ValueError("a historical row has a season code")
        if self.historical and self.logo is not None:
            raise ValueError("a historical row has no logo")
        return self


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
    # The rules version of a kept season feed (ADR 0053); null on a current feed
    # and on a stored feed from before the field.
    build_version: PositiveInt | None = None

    @model_validator(mode="after")
    def _require_east_then_west(self) -> StandingsFeed:
        if [group.key for group in self.conferences] != [
            Conference.EAST,
            Conference.WEST,
        ]:
            raise ValueError("conferences must be east then west")
        return self
