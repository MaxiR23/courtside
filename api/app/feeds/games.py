# api/app/feeds/games.py
#
# Feed models for the games feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
#
# SEE: docs/api/games.md, docs/adr/0008-contract-generation.md

import datetime as dt
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)
from pydantic.alias_generators import to_camel


def _require_utc(value: dt.datetime) -> dt.datetime:
    if value.utcoffset() != dt.timedelta(0):
        raise ValueError("must be in UTC")
    return value


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_require_utc)]
TeamCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
Percentage = Annotated[float, Field(ge=0, le=1)]


class FeedModel(BaseModel):
    """Base of every feed model: camelCase keys, no unknown fields."""

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        json_schema_serialization_defaults_required=True,
    )


class GameStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINAL = "final"
    DELAYED = "delayed"
    POSTPONED = "postponed"
    CANCELED = "canceled"


class StatsAvailability(StrEnum):
    AVAILABLE = "available"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"


class Team(FeedModel):
    code: TeamCode
    name: NonEmptyStr
    city: NonEmptyStr


class Player(FeedModel):
    player_id: NonEmptyStr
    first_name: NonEmptyStr
    last_name: NonEmptyStr
    team_code: TeamCode
    photo_url: HttpUrl


class Leader(FeedModel):
    player_id: NonEmptyStr
    display_name: NonEmptyStr
    team_code: TeamCode
    photo_url: HttpUrl
    points: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt


class Star(Player):
    short_name: NonEmptyStr


class TeamStats(FeedModel):
    field_goal_pct: Percentage
    three_point_pct: Percentage
    rebounds: NonNegativeInt
    assists: NonNegativeInt
    turnovers: NonNegativeInt


class Highlight(FeedModel):
    title: NonEmptyStr
    channel: NonEmptyStr
    thumbnail_url: HttpUrl
    embed_url: HttpUrl


class LineScore(FeedModel):
    away: Annotated[list[NonNegativeInt], Field(min_length=1)]
    home: Annotated[list[NonNegativeInt], Field(min_length=1)]


class Score(FeedModel):
    away: NonNegativeInt
    home: NonNegativeInt


class Leaders(FeedModel):
    away: Leader
    home: Leader


class GameTeamStats(FeedModel):
    away: TeamStats
    home: TeamStats


class Stars(FeedModel):
    away: Star
    home: Star


REQUIRED_BY_STATUS: dict[GameStatus, tuple[str, ...]] = {
    GameStatus.LIVE: (
        "period",
        "clock",
        "line_score",
        "score",
        "leaders",
        "team_stats",
    ),
    GameStatus.FINAL: (
        "line_score",
        "score",
        "winner",
        "stats_availability",
        "highlights_search_url",
    ),
}


class Game(FeedModel):
    id: NonEmptyStr
    away: Team
    home: Team
    status: GameStatus
    start_time: UtcDatetime
    venue: NonEmptyStr
    stars: Stars
    highlights: list[Highlight] = Field(default_factory=list)
    broadcast: NonEmptyStr | None = None
    period: PositiveInt | None = None
    clock: NonEmptyStr | None = None
    line_score: LineScore | None = None
    score: Score | None = None
    winner: TeamCode | None = None
    leaders: Leaders | None = None
    team_stats: GameTeamStats | None = None
    stats_availability: StatsAvailability | None = None
    highlights_search_url: HttpUrl | None = None

    @model_validator(mode="after")
    def _require_fields_of_status(self) -> "Game":
        required = REQUIRED_BY_STATUS.get(self.status, ())
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            aliases = ", ".join(to_camel(name) for name in missing)
            raise ValueError(f"a {self.status} game requires {aliases}")
        return self

    @model_validator(mode="after")
    def _require_a_winner_of_the_game(self) -> "Game":
        if self.winner is None:
            return self
        if self.status is not GameStatus.FINAL:
            raise ValueError(f"a {self.status} game has no winner")
        if self.winner not in (self.away.code, self.home.code):
            raise ValueError("winner must be the away or the home team code")
        return self

    @model_validator(mode="after")
    def _require_stats_of_their_availability(self) -> "Game":
        availability = self.stats_availability
        if availability is None:
            return self
        if self.status is not GameStatus.FINAL:
            raise ValueError(f"a {self.status} game has no statsAvailability")
        held = [n for n in ("leaders", "team_stats") if getattr(self, n) is not None]
        if availability is StatsAvailability.AVAILABLE and len(held) < 2:
            raise ValueError("statsAvailability available requires leaders, teamStats")
        if availability is not StatsAvailability.AVAILABLE and held:
            raise ValueError(
                f"statsAvailability {availability} has no leaders or teamStats"
            )
        return self


class Day(FeedModel):
    date: dt.date
    games: list[Game]


class GamesFeed(FeedModel):
    generated_at: UtcDatetime
    days: list[Day]
