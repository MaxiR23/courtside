# api/app/feeds/player.py
#
# Feed models for the player feed, and the objects the team feed shares
# with it: the single source of truth for their shape. The JSON Schema and
# the TypeScript types are generated from these models.
#
# SEE: docs/api/player.md, docs/design-profiles.md,
# docs/adr/0021-player-and-team-pages.md

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated

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
    BoxScorePlayer,
    Conference,
    GameResult,
    InjuryStatus,
)
from app.feeds.games import (
    FeedModel,
    NonEmptyStr,
    Percentage,
    Team,
    TeamCode,
    UtcDatetime,
)

SeasonLabel = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}$")]
JerseyNumber = Annotated[str, StringConstraints(pattern=r"^\d{1,2}$")]


class TagKind(StrEnum):
    CUP = "cup"
    PLAYOFFS = "playoffs"
    ALLSTAR = "allstar"


class GameKind(StrEnum):
    REGULAR = "regular"
    CUP = "cup"
    PLAYOFFS = "playoffs"
    ALLSTAR = "allstar"


class GameTag(FeedModel):
    kind: TagKind
    conference: Conference | None = None
    round: Annotated[int, Field(ge=1, le=4)] | None = None
    game: PositiveInt | None = None


class NextGame(FeedModel):
    game_id: NonEmptyStr
    start_time: UtcDatetime
    opponent: TeamCode
    is_home: bool
    tag: GameTag | None = None
    arena: NonEmptyStr
    city: NonEmptyStr | None = None
    broadcast: NonEmptyStr | None = None
    detail_available: bool


class ShootingLine(FeedModel):
    """Base of every stat line with shooting splits: made is within attempted."""

    @model_validator(mode="after")
    def _require_made_within_attempted(self) -> ShootingLine:
        for kind in ("field_goals", "three_points", "free_throws"):
            made = getattr(self, f"{kind}_made")
            attempted = getattr(self, f"{kind}_attempted")
            if made > attempted:
                raise ValueError("made must not be above attempted")
        return self


class PlayerInjury(FeedModel):
    status: InjuryStatus
    comment: NonEmptyStr | None = None
    updated_at: UtcDatetime


class Height(FeedModel):
    display: NonEmptyStr
    cm: PositiveInt


class Weight(FeedModel):
    lb: PositiveInt
    kg: PositiveInt


class Birthplace(FeedModel):
    place: NonEmptyStr
    country: NonEmptyStr | None = None


class Draft(FeedModel):
    year: PositiveInt
    round: PositiveInt
    pick: PositiveInt
    team_name: NonEmptyStr


class Profile(FeedModel):
    height: Height | None = None
    weight: Weight | None = None
    birth_date: dt.date | None = None
    age: NonNegativeInt | None = None
    birthplace: Birthplace | None = None
    college: NonEmptyStr | None = None
    draft: Draft | None = None
    seasons: NonNegativeInt | None = None
    debut_season: SeasonLabel | None = None


class RankedStat(FeedModel):
    value: NonNegativeFloat
    rank: PositiveInt | None = None


class RankedPercentage(FeedModel):
    value: Percentage
    rank: PositiveInt | None = None


class Summary(FeedModel):
    season: SeasonLabel
    points: RankedStat
    rebounds: RankedStat
    assists: RankedStat
    field_goal_pct: RankedPercentage


class PlayerLive(FeedModel):
    game_id: NonEmptyStr
    opponent: TeamCode
    is_home: bool
    period: PositiveInt
    clock: NonEmptyStr
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt
    line: BoxScorePlayer | None = None


class GameLogEntry(ShootingLine):
    game_id: NonEmptyStr
    date: dt.date
    opponent: TeamCode | None = None
    is_home: bool
    kind: GameKind
    tag: GameTag | None = None
    result: GameResult
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt
    minutes: NonNegativeInt
    field_goals_made: NonNegativeInt
    field_goals_attempted: NonNegativeInt
    field_goal_pct: Percentage
    three_points_made: NonNegativeInt
    three_points_attempted: NonNegativeInt
    three_point_pct: Percentage
    free_throws_made: NonNegativeInt
    free_throws_attempted: NonNegativeInt
    free_throw_pct: Percentage
    rebounds: NonNegativeInt
    assists: NonNegativeInt
    blocks: NonNegativeInt
    steals: NonNegativeInt
    fouls: NonNegativeInt
    turnovers: NonNegativeInt
    points: NonNegativeInt
    detail_available: bool

    @model_validator(mode="after")
    def _require_an_opponent_outside_all_star(self) -> GameLogEntry:
        if self.opponent is None and self.kind is not GameKind.ALLSTAR:
            raise ValueError("only an All-Star game has a null opponent")
        return self


class GameLog(FeedModel):
    season: SeasonLabel
    entries: list[GameLogEntry]

    @model_validator(mode="after")
    def _require_newest_first(self) -> GameLog:
        dates = [entry.date for entry in self.entries]
        if any(a < b for a, b in pairwise(dates)):
            raise ValueError("game log entries must be listed newest first")
        return self


class AverageRow(FeedModel):
    games_played: PositiveInt
    minutes: NonNegativeFloat
    field_goal_pct: Percentage
    three_point_pct: Percentage
    free_throw_pct: Percentage
    rebounds: NonNegativeFloat
    assists: NonNegativeFloat
    blocks: NonNegativeFloat
    steals: NonNegativeFloat
    fouls: NonNegativeFloat
    turnovers: NonNegativeFloat
    points: NonNegativeFloat


class SeasonAverageRow(AverageRow):
    season: SeasonLabel


class Averages(FeedModel):
    regular: SeasonAverageRow | None = None
    playoffs: SeasonAverageRow | None = None
    career: AverageRow | None = None


class StatRow(ShootingLine):
    games_played: NonNegativeInt
    games_started: NonNegativeInt
    minutes: NonNegativeFloat | None = None
    field_goals_made: NonNegativeFloat
    field_goals_attempted: NonNegativeFloat
    field_goal_pct: Percentage
    three_points_made: NonNegativeFloat
    three_points_attempted: NonNegativeFloat
    three_point_pct: Percentage
    free_throws_made: NonNegativeFloat
    free_throws_attempted: NonNegativeFloat
    free_throw_pct: Percentage
    offensive_rebounds: NonNegativeFloat
    defensive_rebounds: NonNegativeFloat
    rebounds: NonNegativeFloat
    assists: NonNegativeFloat
    blocks: NonNegativeFloat
    steals: NonNegativeFloat
    fouls: NonNegativeFloat
    turnovers: NonNegativeFloat
    points: NonNegativeFloat


class SeasonRow(StatRow):
    season: SeasonLabel
    teams: Annotated[list[TeamCode], Field(min_length=1)]


class CareerRows(FeedModel):
    per_game: StatRow
    totals: StatRow


class SeasonSplit(FeedModel):
    per_game: list[SeasonRow]
    totals: list[SeasonRow]
    career: CareerRows | None = None

    @model_validator(mode="after")
    def _require_newest_first(self) -> SeasonSplit:
        for rows in (self.per_game, self.totals):
            seasons = [row.season for row in rows]
            if any(later >= earlier for earlier, later in pairwise(seasons)):
                raise ValueError("season rows must be listed newest first")
        return self

    @model_validator(mode="after")
    def _require_minutes_only_per_game(self) -> SeasonSplit:
        per_game: list[StatRow] = list(self.per_game)
        totals: list[StatRow] = list(self.totals)
        if self.career is not None:
            per_game.append(self.career.per_game)
            totals.append(self.career.totals)
        if any(row.minutes is None for row in per_game) or any(
            row.minutes is not None for row in totals
        ):
            raise ValueError(
                "totals rows have null minutes and per game rows have minutes"
            )
        return self


class Seasons(FeedModel):
    regular: SeasonSplit
    playoffs: SeasonSplit


class MilestoneCounts(FeedModel):
    double_doubles: NonNegativeInt
    triple_doubles: NonNegativeInt
    disqualifications: NonNegativeInt
    ejections: NonNegativeInt
    technicals: NonNegativeInt
    flagrants: NonNegativeInt
    assist_turnover_ratio: NonNegativeFloat
    steal_turnover_ratio: NonNegativeFloat


class Milestones(FeedModel):
    season: SeasonLabel
    current: MilestoneCounts
    career: MilestoneCounts


class Award(FeedModel):
    name: NonEmptyStr
    count: PositiveInt
    seasons: Annotated[list[SeasonLabel], Field(min_length=1)]


class PlayerFeed(FeedModel):
    id: NonEmptyStr
    first_name: NonEmptyStr
    last_name: NonEmptyStr
    number: JerseyNumber | None = None
    position: NonEmptyStr
    team: Team
    photo_url: HttpUrl | None = None
    injury: PlayerInjury | None = None
    profile: Profile
    summary: Summary | None = None
    next_game: NextGame | None = None
    live: PlayerLive | None = None
    last_games: Annotated[list[GameLogEntry], Field(max_length=5)]
    averages: Averages
    seasons: Seasons
    milestones: Milestones | None = None
    game_log: GameLog | None = None
    awards: list[Award]

    @model_validator(mode="after")
    def _require_recent_games_newest_first_without_all_star(self) -> PlayerFeed:
        dates = [game.date for game in self.last_games]
        if any(a < b for a, b in pairwise(dates)):
            raise ValueError("last games must be listed newest first")
        if any(game.kind is GameKind.ALLSTAR for game in self.last_games):
            raise ValueError("last games must not include an All-Star game")
        return self

    @model_validator(mode="after")
    def _require_the_live_line_of_the_player(self) -> PlayerFeed:
        line = None if self.live is None else self.live.line
        if line is not None and line.player_id != self.id:
            raise ValueError("the live line must be the line of this player")
        return self

    @model_validator(mode="after")
    def _require_the_career_span_of_the_regular_seasons(self) -> PlayerFeed:
        rows = self.seasons.regular.per_game
        if self.profile.seasons is not None and self.profile.seasons != len(rows):
            raise ValueError(
                "profile.seasons must be the number of regular season rows"
            )
        debut = self.profile.debut_season
        if debut is not None and (not rows or rows[-1].season != debut):
            raise ValueError(
                "profile.debutSeason must be the oldest regular season row"
            )
        return self
