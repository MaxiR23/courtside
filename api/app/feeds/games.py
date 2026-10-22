# api/app/feeds/games.py
#
# Feed models for the games feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
#
# SEE: docs/api/games.md, docs/adr/0008-contract-generation.md

import datetime as dt
from collections.abc import Mapping
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
    HexColor,
    NonEmptyStr,
    Percentage,
    SideCode,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import Opponent, Side, TeamColors, TeamLogo

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


class Conference(StrEnum):
    EAST = "east"
    WEST = "west"


class PlayInGameKind(StrEnum):
    SEVEN_EIGHT = "seven_eight"
    NINE_TEN = "nine_ten"
    EIGHTH_SEED = "eighth_seed"


class CupRound(StrEnum):
    GROUP = "group"
    QUARTERFINALS = "quarterfinals"
    SEMIFINALS = "semifinals"
    CHAMPIONSHIP = "championship"


class GameCup(FeedModel):
    """The mark of a Cup game: the round it belongs to."""

    stage: CupRound


class GameAllStar(FeedModel):
    """The mark of an All-Star game: its round as the source writes it, and
    whether it is the Championship."""

    round_label: NonEmptyStr
    championship: bool


class PostseasonStage(StrEnum):
    PLAYIN = "playin"
    PLAYOFFS = "playoffs"
    FINALS = "finals"


class Stakes(StrEnum):
    GAME_7 = "game_7"
    ELIMINATION = "elimination"
    CAN_CLINCH = "can_clinch"
    CLINCHED = "clinched"


class GamePostseason(FeedModel):
    """The mark of a play-in or playoff game: its stage, place in the bracket and stakes."""

    stage: PostseasonStage
    round: Annotated[int, Field(ge=1, le=4)] | None
    conference: Conference | None
    number: Annotated[int, Field(ge=1, le=7)] | None
    summary: NonEmptyStr | None
    play_in: PlayInGameKind | None
    stakes: Stakes | None
    # The series wins of the game's two sides and the side that won the series, from
    # the series object (ADR 0032, ADR 0055). The winner is set only when the
    # series is complete. Null on a play-in mark and when the source gives none.
    away_wins: Annotated[int, Field(ge=0, le=4)] | None = None
    home_wins: Annotated[int, Field(ge=0, le=4)] | None = None
    series_winner: Side | None = None

    @model_validator(mode="after")
    def _require_wins_for_a_series_winner(self) -> GamePostseason:
        if self.series_winner is None:
            return self
        if self.away_wins is None or self.home_wins is None:
            raise ValueError("a series winner requires the wins of both sides")
        ahead = Side.AWAY if self.away_wins > self.home_wins else Side.HOME
        if self.away_wins == self.home_wins or self.series_winner is not ahead:
            raise ValueError("the series winner is the side with more wins")
        return self

    @model_validator(mode="after")
    def _require_fields_of_stage(self) -> GamePostseason:
        if self.stage is PostseasonStage.PLAYIN:
            if self.round is not None or self.number is not None:
                raise ValueError("a play-in mark has no round or number")
            if self.summary is not None:
                raise ValueError("a play-in mark has no summary")
            if (
                self.away_wins is not None
                or self.home_wins is not None
                or self.series_winner is not None
            ):
                raise ValueError("a play-in mark has no series wins or winner")
            if self.play_in is None or self.conference is None:
                raise ValueError("a play-in mark requires playIn, conference")
            if self.stakes not in (None, Stakes.ELIMINATION):
                raise ValueError("a play-in mark has no stakes but elimination")
            return self
        if self.play_in is not None:
            raise ValueError("a series mark has no playIn")
        if self.stage is PostseasonStage.PLAYOFFS:
            if self.round is None:
                if self.conference is not None:
                    raise ValueError(
                        "a playoffs mark without a round has no conference"
                    )
            else:
                if self.round > 3:
                    raise ValueError("a playoffs mark is round 1 to 3")
                if self.conference is None:
                    raise ValueError("a playoffs mark requires conference")
        else:
            if self.round != 4:
                raise ValueError("a finals mark is round 4")
            if self.conference is not None:
                raise ValueError("a finals mark has no conference")
        if self.stakes is Stakes.GAME_7 and self.number != 7:
            raise ValueError("game_7 stakes require number 7")
        return self


class StatsAvailability(StrEnum):
    AVAILABLE = "available"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"


class Team(FeedModel):
    code: TeamCode
    name: NonEmptyStr
    city: NonEmptyStr
    # The team's abbreviation in this past season, from that season's team object
    # (ADR 0055). Null on a current feed.
    season_code: SideCode | None = None
    # The team's logo and colors (ADR 0068). Null on a past season, which cannot
    # tell whether the team was renamed, and when the identity is not known.
    logo: TeamLogo | None = None
    colors: TeamColors | None = None

    @model_validator(mode="after")
    def _require_no_identity_of_a_past_team(self) -> Team:
        if self.season_code is not None and (
            self.logo is not None or self.colors is not None
        ):
            raise ValueError("a team of a past season has no logo and no colors")
        return self


class GameTeam(Opponent):
    """A side of a game: one of the 30 teams, or a guest team outside the league.
    A guest may have no city (an All-Star team); a league team has one."""

    name: NonEmptyStr

    @model_validator(mode="after")
    def _require_a_city_of_a_league_team(self) -> GameTeam:
        if not self.guest and self.city is None:
            raise ValueError("a league team has a city")
        return self


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
    points: NonNegativeInt | None
    rebounds: NonNegativeInt | None
    assists: NonNegativeInt | None


class Star(Player):
    short_name: NonEmptyStr


class TeamStats(FeedModel):
    field_goal_pct: Percentage | None
    three_point_pct: Percentage | None
    rebounds: NonNegativeInt | None
    assists: NonNegativeInt | None
    turnovers: NonNegativeInt | None


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


class GameAccent(FeedModel):
    """The color each side of a game shows in the hero (ADR 0068); null for a
    side with no colors."""

    away: HexColor | None
    home: HexColor | None


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


def required_fields(
    table: Mapping[GameStatus, tuple[str, ...]], status: GameStatus, *, all_star: bool
) -> tuple[str, ...]:
    """The fields a game of this status requires, from a status table.

    A final All-Star game of the untimed format has a score but no line score
    (ADR 0051), so it does not require one.
    """
    required = table.get(status, ())
    if status is GameStatus.FINAL and all_star:
        return tuple(name for name in required if name != "line_score")
    return required


class Game(FeedModel):
    id: NonEmptyStr
    away: GameTeam
    home: GameTeam
    status: GameStatus
    start_time: UtcDatetime
    venue: NonEmptyStr | None
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
    cup: GameCup | None = None
    postseason: GamePostseason | None = None
    all_star: GameAllStar | None = None
    # The hero colors of the two sides (ADR 0068). Null on a day feed's game.
    accent: GameAccent | None = None

    @model_validator(mode="after")
    def _require_fields_of_status(self) -> Game:
        required = required_fields(
            REQUIRED_BY_STATUS, self.status, all_star=self.all_star is not None
        )
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
