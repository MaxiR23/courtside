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
    Field,
    HttpUrl,
    NonNegativeInt,
    PositiveInt,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.feeds.base import (
    FeedModel,
    NonEmptyStr,
    Percentage,
    SideCode,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import Opponent, Side

# The base definitions live in app.feeds.base; the other feed modules import
# them from here.
__all__ = [
    "FeedModel",
    "NonEmptyStr",
    "Percentage",
    "SideCode",
    "TeamCode",
    "UtcDatetime",
]


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


class GameTeam(Opponent):
    """A side of a game: one of the 30 teams, or a guest team outside the league."""

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
    team_code: SideCode | None
    photo_url: HttpUrl | None
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
    away: Star | None
    home: Star | None


def stars_match_sides(stars: Stars, away: GameTeam, home: GameTeam) -> bool:
    """True when a side has no star exactly when it is a guest."""
    return (stars.away is None) == away.guest and (stars.home is None) == home.guest


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
    away: GameTeam
    home: GameTeam
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
    winner: Side | None = None
    leaders: Leaders | None = None
    team_stats: GameTeamStats | None = None
    stats_availability: StatsAvailability | None = None
    highlights_search_url: HttpUrl | None = None

    @model_validator(mode="after")
    def _require_fields_of_status(self) -> Game:
        required = REQUIRED_BY_STATUS.get(self.status, ())
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            aliases = ", ".join(to_camel(name) for name in missing)
            raise ValueError(f"a {self.status} game requires {aliases}")
        return self

    @model_validator(mode="after")
    def _require_a_winner_of_the_game(self) -> Game:
        if self.winner is None:
            return self
        if self.status is not GameStatus.FINAL:
            raise ValueError(f"a {self.status} game has no winner")
        return self

    @model_validator(mode="after")
    def _require_two_different_teams(self) -> Game:
        if self.away.code is not None and self.away.code == self.home.code:
            raise ValueError("a game has two different teams")
        return self

    @model_validator(mode="after")
    def _require_stars_of_the_league_sides(self) -> Game:
        if not stars_match_sides(self.stars, self.away, self.home):
            raise ValueError("a guest side has no star and a league side has one")
        return self

    @model_validator(mode="after")
    def _require_photos_of_league_players(self) -> Game:
        if self.leaders is None:
            return self
        for leader, team in (
            (self.leaders.away, self.away),
            (self.leaders.home, self.home),
        ):
            if leader.photo_url is None and not team.guest:
                raise ValueError("a league leader has a photo")
        return self

    @model_validator(mode="after")
    def _require_stats_of_their_availability(self) -> Game:
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
