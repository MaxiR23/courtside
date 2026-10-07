# api/app/feeds/game_detail.py
#
# Feed models for the game detail feed: the single source of truth for its
# shape. The JSON Schema and the TypeScript types are generated from these
# models.
#
# SEE: docs/api/game-detail.md, docs/adr/0019-game-detail-route-and-feed.md

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated

from pydantic import Field, HttpUrl, NonNegativeInt, PositiveInt, model_validator
from pydantic.alias_generators import to_camel

from app.feeds.games import (
    FeedModel,
    GameStatus,
    Highlight,
    LineScore,
    NonEmptyStr,
    Percentage,
    Score,
    Stars,
    Team,
    TeamCode,
    TeamStats,
    UtcDatetime,
)


class Record(FeedModel):
    wins: NonNegativeInt
    losses: NonNegativeInt


class DetailTeam(Team):
    record: Record


class Venue(FeedModel):
    name: NonEmptyStr
    city: NonEmptyStr
    photo_url: HttpUrl | None = None


class DetailTeamStats(TeamStats):
    free_throw_pct: Percentage
    steals: NonNegativeInt
    blocks: NonNegativeInt


class TeamStatLeaders(FeedModel):
    field_goal_pct: TeamCode | None
    three_point_pct: TeamCode | None
    free_throw_pct: TeamCode | None
    rebounds: TeamCode | None
    assists: TeamCode | None
    turnovers: TeamCode | None
    steals: TeamCode | None
    blocks: TeamCode | None


class DetailGameTeamStats(FeedModel):
    away: DetailTeamStats
    home: DetailTeamStats
    leaders: TeamStatLeaders


class BoxScoreLine(FeedModel):
    points: NonNegativeInt
    field_goals_made: NonNegativeInt
    field_goals_attempted: NonNegativeInt
    three_points_made: NonNegativeInt
    three_points_attempted: NonNegativeInt
    free_throws_made: NonNegativeInt
    free_throws_attempted: NonNegativeInt
    offensive_rebounds: NonNegativeInt
    defensive_rebounds: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt
    turnovers: NonNegativeInt
    steals: NonNegativeInt
    blocks: NonNegativeInt
    fouls: NonNegativeInt


class BoxScorePlayer(BoxScoreLine):
    player_id: NonEmptyStr
    display_name: NonEmptyStr
    starter: bool
    minutes: NonEmptyStr
    plus_minus: int
    photo_url: HttpUrl


class BoxScoreTotals(BoxScoreLine):
    field_goal_pct: Percentage
    three_point_pct: Percentage
    free_throw_pct: Percentage


class TeamBoxScore(FeedModel):
    players: list[BoxScorePlayer]
    totals: BoxScoreTotals


class BoxScore(FeedModel):
    away: TeamBoxScore
    home: TeamBoxScore


class WinProbabilityPoint(FeedModel):
    elapsed_seconds: NonNegativeInt
    home_win_probability: Percentage


class InjuryStatus(StrEnum):
    OUT = "out"
    DOUBTFUL = "doubtful"
    QUESTIONABLE = "questionable"
    PROBABLE = "probable"
    DAY_TO_DAY = "day-to-day"


class Injury(FeedModel):
    display_name: NonEmptyStr
    status: InjuryStatus
    comment: NonEmptyStr | None = None


class Injuries(FeedModel):
    away: list[Injury]
    home: list[Injury]


class GameResult(StrEnum):
    WIN = "win"
    LOSS = "loss"


class LastGame(FeedModel):
    date: dt.date
    opponent: TeamCode
    is_home: bool
    result: GameResult
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt


LastGameList = Annotated[list[LastGame], Field(max_length=5)]


class LastGames(FeedModel):
    away: LastGameList
    home: LastGameList

    @model_validator(mode="after")
    def _require_newest_first(self) -> LastGames:
        for games in (self.away, self.home):
            dates = [game.date for game in games]
            if any(a < b for a, b in pairwise(dates)):
                raise ValueError("last games must be listed newest first")
        return self


class Conference(StrEnum):
    EAST = "east"
    WEST = "west"


class TeamStanding(FeedModel):
    conference: Conference
    conference_rank: PositiveInt
    record: Record
    home_record: Record
    away_record: Record
    last_ten: Record


class Standings(FeedModel):
    away: TeamStanding
    home: TeamStanding


class SeriesGame(FeedModel):
    date: dt.date
    away: TeamCode
    home: TeamCode
    score: Score
    arena: NonEmptyStr


class SeasonSeries(FeedModel):
    total_games: PositiveInt
    away_wins: NonNegativeInt
    home_wins: NonNegativeInt
    games: list[SeriesGame]


class Video(FeedModel):
    title: NonEmptyStr
    duration: NonEmptyStr
    thumbnail_url: HttpUrl | None = None
    link_url: HttpUrl


REQUIRED_BY_STATUS: dict[GameStatus, tuple[str, ...]] = {
    GameStatus.LIVE: ("period", "clock", "line_score", "score", "team_stats"),
    GameStatus.FINAL: ("line_score", "score", "winner"),
}


class GameDetailFeed(FeedModel):
    id: NonEmptyStr
    status: GameStatus
    start_time: UtcDatetime
    venue: Venue
    away: DetailTeam
    home: DetailTeam
    broadcast: NonEmptyStr | None = None
    period: PositiveInt | None = None
    clock: NonEmptyStr | None = None
    line_score: LineScore | None = None
    score: Score | None = None
    winner: TeamCode | None = None
    team_stats: DetailGameTeamStats | None = None
    stars: Stars | None = None
    box_score: BoxScore | None = None
    win_probability: (
        Annotated[list[WinProbabilityPoint], Field(min_length=1)] | None
    ) = None
    injuries: Injuries | None = None
    last_games: LastGames | None = None
    standings: Standings | None = None
    season_series: SeasonSeries | None = None
    highlights: list[Highlight] | None = None
    highlights_search_url: HttpUrl | None = None
    videos: list[Video] | None = None

    @model_validator(mode="after")
    def _require_fields_of_status(self) -> GameDetailFeed:
        required = REQUIRED_BY_STATUS.get(self.status, ())
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            aliases = ", ".join(to_camel(name) for name in missing)
            raise ValueError(f"a {self.status} game requires {aliases}")
        return self

    @model_validator(mode="after")
    def _require_a_winner_of_the_game(self) -> GameDetailFeed:
        if self.winner is None:
            return self
        if self.status is not GameStatus.FINAL:
            raise ValueError(f"a {self.status} game has no winner")
        if self.winner not in (self.away.code, self.home.code):
            raise ValueError("winner must be the away or the home team code")
        return self

    @model_validator(mode="after")
    def _require_stat_leaders_of_the_game(self) -> GameDetailFeed:
        if self.team_stats is None:
            return self
        codes = (self.away.code, self.home.code)
        for leader in self.team_stats.leaders.model_dump().values():
            if leader is not None and leader not in codes:
                raise ValueError("a stat leader must be the away or the home team code")
        return self
