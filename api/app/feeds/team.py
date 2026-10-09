# api/app/feeds/team.py
#
# Feed models for the team feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
#
# SEE: docs/api/team.md, docs/design-profiles.md,
# docs/adr/0021-player-and-team-pages.md

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import (
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from app.feeds.game_detail import (
    Conference,
    GameResult,
    InjuryStatus,
    Record,
    Venue,
)
from app.feeds.games import (
    FeedModel,
    NonEmptyStr,
    Percentage,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import Opponent
from app.feeds.player import (
    GameKind,
    GameTag,
    JerseyNumber,
    NextGame,
    SeasonLabel,
)

HexColor = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]


class TeamColors(FeedModel):
    primary: HexColor
    secondary: HexColor


class Coach(FeedModel):
    name: NonEmptyStr
    seasons: NonNegativeInt | None = None


class SplitRecord(Record):
    win_pct: Percentage


class Streak(FeedModel):
    kind: GameResult
    count: PositiveInt


class PlayoffStatus(StrEnum):
    SEED = "seed"
    PLAYIN = "playin"
    OUT = "out"


SEED_RANGES: dict[PlayoffStatus, range] = {
    PlayoffStatus.SEED: range(1, 7),
    PlayoffStatus.PLAYIN: range(7, 11),
    PlayoffStatus.OUT: range(11, 16),
}


class PlayoffPosition(FeedModel):
    status: PlayoffStatus
    seed: Annotated[int, Field(ge=1, le=15)]

    @model_validator(mode="after")
    def _require_a_seed_of_the_status(self) -> PlayoffPosition:
        if self.seed not in SEED_RANGES[self.status]:
            raise ValueError("playoff seed must match its status")
        return self


class PointsTotal(FeedModel):
    per_game: NonNegativeFloat
    total: NonNegativeInt


class Differential(FeedModel):
    per_game: float
    total: int


class TeamRecord(SplitRecord):
    season: SeasonLabel
    home: SplitRecord
    away: SplitRecord
    last_ten: SplitRecord
    streak: Streak | None = None
    games_behind: NonNegativeFloat | None = None
    conference_rank: Annotated[int, Field(ge=1, le=15)]
    division_rank: Annotated[int, Field(ge=1, le=5)]
    playoff: PlayoffPosition | None = None
    points_for: PointsTotal
    points_against: PointsTotal
    differential: Differential


class TeamLeader(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    number: JerseyNumber | None = None
    position: NonEmptyStr
    photo_url: HttpUrl | None = None
    value: NonNegativeFloat


class TeamLeaders(FeedModel):
    season: SeasonLabel
    points: TeamLeader | None = None
    rebounds: TeamLeader | None = None
    assists: TeamLeader | None = None


class RosterPlayer(FeedModel):
    id: NonEmptyStr
    name: NonEmptyStr
    number: JerseyNumber | None = None
    position: NonEmptyStr | None = None
    height: NonEmptyStr | None = None
    weight: PositiveInt | None = None
    age: NonNegativeInt | None = None
    birth_date: dt.date | None = None
    birthplace: NonEmptyStr | None = None
    college: NonEmptyStr | None = None
    experience: NonNegativeInt | None = None
    photo_url: HttpUrl | None = None
    status: Literal["active"] | InjuryStatus


class TeamInjury(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    number: JerseyNumber | None = None
    position: NonEmptyStr | None = None
    status: InjuryStatus
    comment: NonEmptyStr | None = None
    updated_at: UtcDatetime


class ScheduleGame(FeedModel):
    game_id: NonEmptyStr
    start_time: UtcDatetime
    opponent: Opponent
    is_home: bool
    kind: GameKind
    tag: GameTag | None = None
    result: GameResult | None = None
    team_score: NonNegativeInt | None = None
    opponent_score: NonNegativeInt | None = None
    broadcast: NonEmptyStr | None = None
    is_next: bool
    detail_available: bool


class ScheduleGroup(FeedModel):
    key: Annotated[str, StringConstraints(pattern=r"^(\d{4}-\d{2}|playoffs)$")]
    games: Annotated[list[ScheduleGame], Field(min_length=1)]


class Schedule(FeedModel):
    groups: Annotated[list[ScheduleGroup], Field(min_length=1)]
    default_group: NonEmptyStr

    @model_validator(mode="after")
    def _require_an_existing_default_group(self) -> Schedule:
        if self.default_group not in [group.key for group in self.groups]:
            raise ValueError("default group must be the key of a group")
        return self

    @model_validator(mode="after")
    def _require_one_next_game_at_most(self) -> Schedule:
        flagged = sum(game.is_next for group in self.groups for game in group.games)
        if flagged > 1:
            raise ValueError("at most one schedule game is the next game")
        return self


def _roster_order(number: str | None) -> tuple[bool, int]:
    return (number is None, int(number or 0))


class TeamFeed(FeedModel):
    code: TeamCode
    city: NonEmptyStr
    name: NonEmptyStr
    conference: Conference
    division: NonEmptyStr
    colors: TeamColors
    arena: Venue
    coach: Coach | None = None
    season: SeasonLabel
    record: TeamRecord
    leaders: TeamLeaders
    roster: list[RosterPlayer]
    injuries: list[TeamInjury]
    next_game: NextGame | None = None
    schedule: Schedule | None = None

    @model_validator(mode="after")
    def _require_roster_by_number(self) -> TeamFeed:
        keys = [_roster_order(player.number) for player in self.roster]
        if any(later < earlier for earlier, later in pairwise(keys)):
            raise ValueError("roster must be ordered by number, unnumbered last")
        return self

    @model_validator(mode="after")
    def _require_the_next_game_of_the_schedule(self) -> TeamFeed:
        if self.schedule is None:
            return self
        flagged = [
            game.game_id
            for group in self.schedule.groups
            for game in group.games
            if game.is_next
        ]
        expected = [] if self.next_game is None else [self.next_game.game_id]
        if flagged != expected:
            raise ValueError("the schedule next game must be the next game")
        return self
