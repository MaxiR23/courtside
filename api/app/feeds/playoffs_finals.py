# api/app/feeds/playoffs_finals.py
#
# Feed models for the playoffs finals feed: the single source of truth for its
# shape. The JSON Schema and the TypeScript types are generated from these
# models. The feed has the Finals games that are final (with their leaders, the
# win probability curve of the curve team and its largest deficit), the Finals
# MVP with the postseason averages, the road to the title of each finalist, the
# head to head bars and the postseason averages of the finalists' rosters.
# Labels are keys and parts, never prose: the page writes the words. Every
# list that has one entry per finalist lists the Finals top side, then the
# bottom side.
#
# SEE: docs/api/playoffs.md, docs/adr/0033-playoffs-finals-feed.md,
# docs/adr/0072-resolved-team-colors-in-the-playoffs-and-cup-feeds.md

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

from app.feeds.base import HexColor
from app.feeds.game_detail import GameResult, WinProbabilityPeriods
from app.feeds.games import (
    FeedModel,
    GameStatus,
    Highlight,
    Leaders,
    NonEmptyStr,
    Percentage,
    SideCode,
    TeamCode,
)
from app.feeds.player import SeasonLabel
from app.feeds.playoffs import PlayoffTeam, SeriesGame, SeriesStatus
from app.feeds.standings import RecordText

GameNumber = Annotated[int, Field(ge=1, le=7)]
Seed = Annotated[int, Field(ge=1, le=15)]
SeriesWins = Annotated[int, Field(ge=0, le=4)]
Round = Annotated[int, Field(ge=1, le=4)]


class TeamWinProbabilityPoint(FeedModel):
    elapsed_seconds: NonNegativeInt
    win_probability: Percentage


class FinalsWinProbability(FeedModel):
    points: Annotated[list[TeamWinProbabilityPoint], Field(min_length=1)]
    periods: WinProbabilityPeriods

    @model_validator(mode="after")
    def _require_points_in_order_inside_the_game(self) -> FinalsWinProbability:
        seconds = [point.elapsed_seconds for point in self.points]
        if any(a > b for a, b in pairwise(seconds)):
            raise ValueError("points must not go back in time")
        if seconds[-1] > self.periods.end_elapsed_seconds:
            raise ValueError("points must end inside the game")
        return self


class LargestDeficit(FeedModel):
    points: PositiveInt
    elapsed_seconds: NonNegativeInt


class FinalsGame(FeedModel):
    game: SeriesGame
    leaders: Leaders | None
    win_probability: FinalsWinProbability | None
    largest_deficit: LargestDeficit | None
    highlights: list[Highlight] | None

    @model_validator(mode="after")
    def _require_a_final_game(self) -> FinalsGame:
        if self.game.status is not GameStatus.FINAL:
            raise ValueError("a Finals game of the feed is final")
        return self


class BestGame(FeedModel):
    game_id: NonEmptyStr
    number: GameNumber
    points: NonNegativeInt


class FinalsMvp(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    team_code: TeamCode | None
    # The team's abbreviation in this past season, from that season's team object
    # (ADR 0055). Null on a current feed.
    season_code: SideCode | None = None
    # The resolved team color (ADR 0072), added when served; null in the stored file.
    accent: HexColor | None = None
    games: NonNegativeInt | None
    points: NonNegativeFloat | None
    rebounds: NonNegativeFloat | None
    assists: NonNegativeFloat | None
    best_game: BestGame | None


class RoadSeries(FeedModel):
    round: Round
    opponent: PlayoffTeam
    opponent_seed: Seed | None
    wins: SeriesWins | None
    losses: SeriesWins | None
    result: GameResult | None


class RoadTeam(FeedModel):
    team: PlayoffTeam
    seed: Seed | None
    regular_season: RecordText | None
    postseason: RecordText | None
    series: Annotated[list[RoadSeries], Field(max_length=4)]

    @model_validator(mode="after")
    def _require_increasing_rounds(self) -> RoadTeam:
        rounds = [series.round for series in self.series]
        if any(a >= b for a, b in pairwise(rounds)):
            raise ValueError("rounds must strictly increase")
        return self


class FinalistRecord(FeedModel):
    team_code: TeamCode
    # The team's abbreviation in this past season, from that season's team object
    # (ADR 0055). Null on a current feed.
    season_code: SideCode | None = None
    record: RecordText | None


class HeadToHeadStat(StrEnum):
    POINTS = "points"
    FIELD_GOAL_PCT = "field_goal_pct"
    EFFECTIVE_FG_PCT = "effective_fg_pct"
    ASSISTS = "assists"
    REBOUNDS = "rebounds"
    BLOCKS = "blocks"
    STEALS = "steals"
    TECHNICAL_FOULS = "technical_fouls"


class BarValue(FeedModel):
    team_code: TeamCode
    value: NonNegativeFloat | None


class HeadToHeadBar(FeedModel):
    stat: HeadToHeadStat
    values: Annotated[list[BarValue], Field(min_length=2, max_length=2)]
    better: TeamCode | None

    @model_validator(mode="after")
    def _require_a_better_team_of_the_bar(self) -> HeadToHeadBar:
        if self.better is None:
            return self
        if self.better not in {value.team_code for value in self.values}:
            raise ValueError("better must be one of the two teams")
        if any(value.value is None for value in self.values):
            raise ValueError("better is null when a value is null")
        return self


class HeadToHead(FeedModel):
    records: Annotated[list[FinalistRecord], Field(min_length=2, max_length=2)]
    bars: Annotated[list[HeadToHeadBar], Field(min_length=8, max_length=8)]

    @model_validator(mode="after")
    def _require_the_bars_in_order(self) -> HeadToHead:
        if [bar.stat for bar in self.bars] != list(HeadToHeadStat):
            raise ValueError("bars must follow the order of the stats")
        return self


class PlayerPostseasonAverages(FeedModel):
    player_id: NonEmptyStr
    name: NonEmptyStr
    photo_url: HttpUrl | None
    points: NonNegativeFloat | None
    rebounds: NonNegativeFloat | None
    assists: NonNegativeFloat | None
    blocks: NonNegativeFloat | None
    field_goal_pct: Percentage | None


class RosterAverages(FeedModel):
    team_code: TeamCode
    # The team's abbreviation in this past season, from that season's team object
    # (ADR 0055). Null on a current feed.
    season_code: SideCode | None = None
    players: list[PlayerPostseasonAverages]


class PlayoffsFinalsFeed(FeedModel):
    season: SeasonLabel
    status: SeriesStatus
    champion: TeamCode | None
    curve_team: TeamCode
    games: Annotated[list[FinalsGame], Field(max_length=7)]
    finals_mvp: FinalsMvp | None
    road: Annotated[list[RoadTeam], Field(min_length=2, max_length=2)]
    head_to_head: HeadToHead
    # Null on a past season: no read carries the postseason averages (ADR 0058).
    averages: Annotated[list[RosterAverages], Field(min_length=2, max_length=2)] | None
    # The rules version of a kept season feed (ADR 0053); null on a current feed
    # and on a stored feed from before the field.
    build_version: PositiveInt | None = None

    @model_validator(mode="after")
    def _require_the_champion_and_the_curve_team(self) -> PlayoffsFinalsFeed:
        codes = {road.team.code for road in self.road}
        complete = self.status is SeriesStatus.COMPLETE
        if (self.champion is not None) != complete:
            raise ValueError("the champion is set exactly when the series is complete")
        if self.champion is not None and self.champion not in codes:
            raise ValueError("the champion must be one of the finalists")
        if self.curve_team not in codes:
            raise ValueError("the curve team must be one of the finalists")
        if self.champion is not None and self.curve_team != self.champion:
            raise ValueError("the curve team is the champion when there is one")
        return self

    @model_validator(mode="after")
    def _require_the_games_in_number_order(self) -> PlayoffsFinalsFeed:
        numbers = [game.game.number for game in self.games]
        if any(a >= b for a, b in pairwise(numbers)):
            raise ValueError("game numbers must strictly increase")
        return self

    @model_validator(mode="after")
    def _require_the_same_finalists_in_every_list(self) -> PlayoffsFinalsFeed:
        order = [road.team.code for road in self.road]
        if [record.team_code for record in self.head_to_head.records] != order:
            raise ValueError("records must list the finalists in the road order")
        for bar in self.head_to_head.bars:
            if [value.team_code for value in bar.values] != order:
                raise ValueError("bar values must list the finalists in the road order")
        if (
            self.averages is not None
            and [roster.team_code for roster in self.averages] != order
        ):
            raise ValueError("averages must list the finalists in the road order")
        return self
