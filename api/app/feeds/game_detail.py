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
    GameTeam,
    Highlight,
    LineScore,
    NonEmptyStr,
    Percentage,
    Score,
    Stars,
    TeamCode,
    TeamStats,
    UtcDatetime,
    stars_match_sides,
)
from app.feeds.opponent import Opponent, Side


class Record(FeedModel):
    wins: NonNegativeInt
    losses: NonNegativeInt


class DetailTeam(GameTeam):
    record: Record | None


class Venue(FeedModel):
    name: NonEmptyStr
    city: NonEmptyStr | None = None
    photo_url: HttpUrl | None = None


class DetailTeamStats(TeamStats):
    free_throw_pct: Percentage
    steals: NonNegativeInt
    blocks: NonNegativeInt


class TeamStatLeaders(FeedModel):
    field_goal_pct: Side | None
    three_point_pct: Side | None
    free_throw_pct: Side | None
    rebounds: Side | None
    assists: Side | None
    turnovers: Side | None
    steals: Side | None
    blocks: Side | None


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
    photo_url: HttpUrl | None


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


class WinProbabilityLeader(FeedModel):
    side: Side
    win_probability: Percentage


class GamePeriod(FeedModel):
    number: PositiveInt
    start_elapsed_seconds: NonNegativeInt


class WinProbabilityPeriods(FeedModel):
    periods: Annotated[list[GamePeriod], Field(min_length=1)]
    end_elapsed_seconds: PositiveInt

    @model_validator(mode="after")
    def _require_consecutive_periods(self) -> WinProbabilityPeriods:
        numbers = [period.number for period in self.periods]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("periods must be numbered 1, 2, 3 and so on in order")
        if self.periods[0].start_elapsed_seconds != 0:
            raise ValueError("the first period must start at 0")
        for earlier, later in pairwise(self.periods):
            if later.start_elapsed_seconds <= earlier.start_elapsed_seconds:
                raise ValueError("period starts must increase")
        if self.end_elapsed_seconds <= self.periods[-1].start_elapsed_seconds:
            raise ValueError("the game end must be after the last period start")
        return self


class InjuryStatus(StrEnum):
    OUT = "out"
    DOUBTFUL = "doubtful"
    QUESTIONABLE = "questionable"
    PROBABLE = "probable"
    DAY_TO_DAY = "day-to-day"


class Injury(FeedModel):
    player_id: NonEmptyStr | None = None
    display_name: NonEmptyStr
    status: InjuryStatus
    comment: NonEmptyStr | None = None


class Injuries(FeedModel):
    away: list[Injury] | None
    home: list[Injury] | None


class GameResult(StrEnum):
    WIN = "win"
    LOSS = "loss"


class LastGame(FeedModel):
    date: dt.date
    opponent: Opponent
    is_home: bool
    result: GameResult
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt


LastGameList = Annotated[list[LastGame], Field(max_length=5)]


class LastGames(FeedModel):
    away: LastGameList | None
    home: LastGameList | None

    @model_validator(mode="after")
    def _require_newest_first(self) -> LastGames:
        for games in (self.away, self.home):
            if games is None:
                continue
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
    away: TeamStanding | None
    home: TeamStanding | None


class SeriesGame(FeedModel):
    date: dt.date
    away: TeamCode
    home: TeamCode
    is_current: bool
    score: Score | None
    winner: TeamCode | None
    arena: NonEmptyStr

    @model_validator(mode="after")
    def _require_a_winner_of_a_played_game(self) -> SeriesGame:
        if (self.score is None) != (self.winner is None):
            raise ValueError("a series game has a score and a winner, or neither")
        if self.winner is not None and self.winner not in (self.away, self.home):
            raise ValueError("series game winner must be its away or home team code")
        return self


class SeasonSeries(FeedModel):
    total_games: PositiveInt
    away_wins: NonNegativeInt
    home_wins: NonNegativeInt
    leader: TeamCode | None
    games: list[SeriesGame]

    @model_validator(mode="after")
    def _require_one_current_game(self) -> SeasonSeries:
        if sum(game.is_current for game in self.games) > 1:
            raise ValueError("at most one series game is the current game")
        return self


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
    winner: Side | None = None
    team_stats: DetailGameTeamStats | None = None
    stars: Stars | None = None
    box_score: BoxScore | None = None
    win_probability: (
        Annotated[list[WinProbabilityPoint], Field(min_length=1)] | None
    ) = None
    win_probability_leader: WinProbabilityLeader | None = None
    win_probability_periods: WinProbabilityPeriods | None = None
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
        return self

    @model_validator(mode="after")
    def _require_two_different_teams(self) -> GameDetailFeed:
        if self.away.code is not None and self.away.code == self.home.code:
            raise ValueError("a game has two different teams")
        return self

    @model_validator(mode="after")
    def _require_league_data_of_league_sides(self) -> GameDetailFeed:
        for team in (self.away, self.home):
            if (team.record is None) != team.guest:
                raise ValueError("a guest side has no record and a league side has one")
        if self.stars is not None and not stars_match_sides(
            self.stars, self.away, self.home
        ):
            raise ValueError("a guest side has no star and a league side has one")
        sections = (
            ("standings", self.standings),
            ("injuries", self.injuries),
            ("lastGames", self.last_games),
        )
        for name, section in sections:
            if section is None:
                continue
            for side, team in ((section.away, self.away), (section.home, self.home)):
                if (side is None) != team.guest:
                    raise ValueError(
                        f"{name} of a guest side is null and of a league side is set"
                    )
        return self

    @model_validator(mode="after")
    def _require_no_series_of_a_guest_game(self) -> GameDetailFeed:
        if self.season_series is not None and (self.away.guest or self.home.guest):
            raise ValueError("a guest game has no season series")
        return self

    @model_validator(mode="after")
    def _require_photos_of_league_players(self) -> GameDetailFeed:
        if self.box_score is None:
            return self
        for team_box, team in (
            (self.box_score.away, self.away),
            (self.box_score.home, self.home),
        ):
            if not team.guest and any(p.photo_url is None for p in team_box.players):
                raise ValueError("a league box score player has a photo")
        return self

    @model_validator(mode="after")
    def _require_points_within_the_periods(self) -> GameDetailFeed:
        if self.win_probability_periods is None:
            return self
        if self.win_probability is None:
            raise ValueError("win probability periods require win probability")
        end = self.win_probability_periods.end_elapsed_seconds
        if any(point.elapsed_seconds > end for point in self.win_probability):
            raise ValueError("a win probability point must not be after the game end")
        return self

    @model_validator(mode="after")
    def _require_points_in_game_time_order(self) -> GameDetailFeed:
        if self.win_probability is None:
            return self
        seconds = [point.elapsed_seconds for point in self.win_probability]
        if any(later < earlier for earlier, later in pairwise(seconds)):
            raise ValueError("win probability points must be in game time order")
        return self

    @model_validator(mode="after")
    def _require_the_leader_of_the_latest_point(self) -> GameDetailFeed:
        expected: tuple[Side, float] | None = None
        if self.win_probability is not None:
            latest = self.win_probability[-1].home_win_probability
            if latest > 0.5:
                expected = (Side.HOME, latest)
            elif latest < 0.5:
                expected = (Side.AWAY, 1 - latest)
        leader = self.win_probability_leader
        found = None if leader is None else (leader.side, leader.win_probability)
        if found != expected:
            raise ValueError(
                "win probability leader must be the side ahead at the latest"
                " point, null when even or without win probability"
            )
        return self

    @model_validator(mode="after")
    def _require_a_series_leader_of_the_game(self) -> GameDetailFeed:
        if self.season_series is None:
            return self
        series = self.season_series
        if series.leader is not None and series.leader not in (
            self.away.code,
            self.home.code,
        ):
            raise ValueError("series leader must be the away or the home team code")
        expected = (
            self.away.code
            if series.away_wins > series.home_wins
            else self.home.code
            if series.home_wins > series.away_wins
            else None
        )
        if series.leader != expected:
            raise ValueError("series leader must be the team with more wins")
        return self
