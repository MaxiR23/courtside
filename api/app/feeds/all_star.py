# api/app/feeds/all_star.py
#
# Feed models for the All-Star feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models. The
# feed has the current edition (date, venue, format line, the teams with their
# placement and roster tiles, and the games with their box scores, team
# statistics, leaders and Top 5), the MVP with his game lines and day totals, and
# the recap of the previous edition. The number of teams and rounds changes every
# year: the feed is a list of games with a round label and N teams, never a fixed
# bracket. Labels are keys and parts, never prose: the page writes the words. The
# format line is the one text, because the page shows it as sent.
#
# SEE: docs/api/all-star.md, docs/adr/0036-all-star-feed.md

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
    model_validator,
)

from app.feeds.game_detail import BoxScorePlayer, BoxScoreTotals, GameResult, Venue
from app.feeds.games import (
    FeedModel,
    GameStatus,
    Highlight,
    Leaders,
    NonEmptyStr,
    Score,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import Opponent, Side
from app.feeds.standings import StandingsColors

MAX_TOP5 = 5


class AllStarState(StrEnum):
    BEFORE = "before"
    LIVE = "live"
    AFTER = "after"


class PlacementKind(StrEnum):
    CHAMPION = "champion"
    RUNNER_UP = "runner_up"
    ELIMINATED = "eliminated"
    SO_FAR = "so_far"
    YET_TO_PLAY = "yet_to_play"


class Placement(FeedModel):
    kind: PlacementKind
    round_label: NonEmptyStr | None

    @model_validator(mode="after")
    def _require_a_round_label_of_an_eliminated_team(self) -> Placement:
        if (self.round_label is not None) != (self.kind is PlacementKind.ELIMINATED):
            raise ValueError("only an eliminated placement has a round label")
        return self


class LeagueTeam(FeedModel):
    """The league team of a player, by its standard code, with its colors."""

    code: TeamCode
    colors: StandingsColors


class BroadcastKind(StrEnum):
    TV = "tv"
    STREAMING = "streaming"


class Broadcast(FeedModel):
    name: NonEmptyStr
    kind: BroadcastKind


class AllStarBoxPlayer(BoxScorePlayer):
    jersey: NonEmptyStr | None
    position: NonEmptyStr | None
    league_team: LeagueTeam | None


class AllStarTeamBox(FeedModel):
    players: list[AllStarBoxPlayer]
    totals: BoxScoreTotals


class AllStarBoxScore(FeedModel):
    away: AllStarTeamBox
    home: AllStarTeamBox


class TeamStatKind(StrEnum):
    FIELD_GOAL_PCT = "field_goal_pct"
    THREE_POINTS_MADE = "three_points_made"
    REBOUNDS = "rebounds"
    ASSISTS = "assists"
    STEALS = "steals"
    BLOCKS = "blocks"


class AllStarTeamStat(FeedModel):
    stat: TeamStatKind
    away: NonNegativeFloat
    home: NonNegativeFloat
    better: Side | None

    @model_validator(mode="after")
    def _require_the_higher_value_as_better(self) -> AllStarTeamStat:
        if self.away == self.home:
            expected = None
        else:
            expected = Side.AWAY if self.away > self.home else Side.HOME
        if self.better != expected:
            raise ValueError("better is the higher value, and null on a tie")
        return self


class Top5Row(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    side: Side
    league_team: LeagueTeam | None
    points: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt


def _top5_key(row: Top5Row) -> tuple[int, int]:
    return (row.points, row.rebounds + row.assists)


class AllStarGame(FeedModel):
    id: NonEmptyStr
    start_time: UtcDatetime
    status: GameStatus
    status_text: NonEmptyStr | None
    clock: NonEmptyStr | None
    period: PositiveInt | None
    score: Score | None
    overtime: bool
    winner: Side | None
    attendance: NonNegativeInt | None
    broadcasts: list[Broadcast]
    round_label: NonEmptyStr | None
    championship: bool
    away: Opponent | None
    home: Opponent | None
    to_be_determined: bool
    box_score: AllStarBoxScore | None
    team_stats: list[AllStarTeamStat] | None
    leaders: Leaders | None
    top5: Annotated[list[Top5Row], Field(max_length=MAX_TOP5)]
    highlights: list[Highlight] | None

    @model_validator(mode="after")
    def _require_to_be_determined_exactly_when_a_side_is_missing(self) -> AllStarGame:
        missing = self.away is None or self.home is None
        if self.to_be_determined != missing:
            raise ValueError("toBeDetermined is true exactly when a side is null")
        return self

    @model_validator(mode="after")
    def _require_sides_and_score_of_a_game_in_play(self) -> AllStarGame:
        if self.status in (GameStatus.LIVE, GameStatus.FINAL) and (
            self.to_be_determined or self.score is None
        ):
            raise ValueError("a live or final game has both sides and a score")
        return self

    @model_validator(mode="after")
    def _require_the_winner_of_a_final_game(self) -> AllStarGame:
        expected: Side | None = None
        if (
            self.status is GameStatus.FINAL
            and self.score is not None
            and self.score.away != self.score.home
        ):
            expected = Side.AWAY if self.score.away > self.score.home else Side.HOME
        if self.winner != expected:
            raise ValueError(
                "the winner is the side with the higher score of a final game"
            )
        return self

    @model_validator(mode="after")
    def _require_overtime_only_in_play(self) -> AllStarGame:
        if self.overtime and self.status not in (GameStatus.LIVE, GameStatus.FINAL):
            raise ValueError("only a live or final game has overtime")
        return self

    @model_validator(mode="after")
    def _require_the_top5_in_order(self) -> AllStarGame:
        keys = [_top5_key(row) for row in self.top5]
        if any(a < b for a, b in pairwise(keys)):
            raise ValueError("top5 is sorted by points, then rebounds plus assists")
        return self

    @model_validator(mode="after")
    def _require_the_six_stats_in_order(self) -> AllStarGame:
        if self.team_stats is not None and [s.stat for s in self.team_stats] != list(
            TeamStatKind
        ):
            raise ValueError("team stats are the 6 stats in order")
        return self


class RosterTile(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    league_team: LeagueTeam | None


class AllStarTeam(FeedModel):
    team: Opponent
    wins: NonNegativeInt
    losses: NonNegativeInt
    placement: Placement
    roster: list[RosterTile]


class AllStarEdition(FeedModel):
    date: dt.date | None
    venue: Venue | None
    format_line: NonEmptyStr | None
    teams: list[AllStarTeam]
    games: list[AllStarGame]

    @model_validator(mode="after")
    def _require_at_most_one_champion_and_runner_up(self) -> AllStarEdition:
        for kind in (PlacementKind.CHAMPION, PlacementKind.RUNNER_UP):
            if sum(team.placement.kind is kind for team in self.teams) > 1:
                raise ValueError(f"at most one team is the {kind}")
        return self


class MvpLine(FeedModel):
    game_id: NonEmptyStr
    round_label: NonEmptyStr | None
    result: GameResult
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt
    opponent: Opponent
    points: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt


class MvpTotals(FeedModel):
    games: PositiveInt
    points: NonNegativeInt
    rebounds: NonNegativeInt
    assists: NonNegativeInt


class AllStarMvp(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    jersey: NonEmptyStr | None
    league_team: LeagueTeam | None
    lines: Annotated[list[MvpLine], Field(min_length=1)]
    totals: MvpTotals

    @model_validator(mode="after")
    def _require_totals_that_are_the_sums_of_the_lines(self) -> AllStarMvp:
        totals = self.totals
        sums = (
            len(self.lines),
            sum(line.points for line in self.lines),
            sum(line.rebounds for line in self.lines),
            sum(line.assists for line in self.lines),
        )
        if (totals.games, totals.points, totals.rebounds, totals.assists) != sums:
            raise ValueError("totals are the sums of the lines")
        return self


class AllStarResult(FeedModel):
    game_id: NonEmptyStr
    away: Opponent
    home: Opponent
    score: Score
    winner: Side
    overtime: bool

    @model_validator(mode="after")
    def _require_the_winner_to_be_the_higher_score(self) -> AllStarResult:
        if self.score.away == self.score.home:
            raise ValueError("a result has a winner")
        expected = Side.AWAY if self.score.away > self.score.home else Side.HOME
        if self.winner != expected:
            raise ValueError("the winner is the side with the higher score")
        return self


class AllStarRecap(FeedModel):
    year: PositiveInt
    date: dt.date
    venue: Venue | None
    championship: AllStarResult
    mvp: AllStarMvp | None


class AllStarFeed(FeedModel):
    year: PositiveInt
    state: AllStarState
    edition: AllStarEdition
    mvp: AllStarMvp | None
    previous: AllStarRecap | None

    @model_validator(mode="after")
    def _require_the_games_of_the_state(self) -> AllStarFeed:
        games = self.edition.games
        in_play = [g for g in games if g.status in (GameStatus.LIVE, GameStatus.FINAL)]
        every_final = bool(games) and all(g.status is GameStatus.FINAL for g in games)
        if self.state is AllStarState.BEFORE:
            if games or self.edition.teams:
                raise ValueError("a before feed has no games and no teams")
            if self.mvp is not None:
                raise ValueError("a before feed has no MVP")
        elif self.state is AllStarState.AFTER:
            if not every_final:
                raise ValueError("an after feed has games and every game is final")
        elif not in_play or every_final:
            raise ValueError(
                "a live feed has a live or final game and not every game is final"
            )
        return self
