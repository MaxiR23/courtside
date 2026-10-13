# api/app/feeds/cup.py
#
# Feed models for the Cup feed: the single source of truth for its shape. The
# JSON Schema and the TypeScript types are generated from these models. The
# feed has the draw (six groups of five), the group tables, the wild card
# standings, the knockout bracket with its seeding rules, every Cup game by day
# and the stage of the competition. Labels are keys and parts, never prose: the
# page writes the words. Every team is an Opponent.
#
# SEE: docs/api/cup.md, docs/adr/0028-cup-feed.md

import datetime as dt
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, NonNegativeInt, PositiveInt, model_validator

from app.feeds.game_detail import Conference
from app.feeds.games import (
    CupRound,
    FeedModel,
    GameStatus,
    NonEmptyStr,
    Score,
    UtcDatetime,
)
from app.feeds.opponent import Opponent, Side
from app.feeds.player import SeasonLabel
from app.feeds.standings import (
    GamesBehindText,
    PerGameDifferential,
    RecordText,
    TotalDifferential,
)
from app.feeds.team import CupGroupName, GroupLetter, Streak

__all__ = ["CupGroupName", "GroupLetter"]

GROUP_GAMES = 10
GROUP_GAMES_TOTAL = 60
ROUNDS = [
    CupRound.GROUP,
    CupRound.QUARTERFINALS,
    CupRound.SEMIFINALS,
    CupRound.CHAMPIONSHIP,
]


class CupStage(StrEnum):
    DRAW = "draw"
    GROUP = "group"
    QUARTERFINALS = "quarterfinals"
    SEMIFINALS = "semifinals"
    CHAMPIONSHIP = "championship"
    COMPLETE = "complete"


class StageStatus(StrEnum):
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    NEXT = "next"
    UPCOMING = "upcoming"


class StageEntry(FeedModel):
    stage: CupRound
    status: StageStatus
    first_date: dt.date | None
    last_date: dt.date | None

    @model_validator(mode="after")
    def _require_both_dates_or_none(self) -> StageEntry:
        if (self.first_date is None) != (self.last_date is None):
            raise ValueError("a stage has both dates or none")
        return self


class CupTag(StrEnum):
    WON_GROUP = "won_group"
    WILD_CARD = "wild_card"
    ELIMINATED = "eliminated"


class GroupRow(FeedModel):
    position: Annotated[int, Field(ge=1, le=5)] | None
    team: Opponent
    wins: NonNegativeInt
    losses: NonNegativeInt
    games_behind: GamesBehindText | None
    differential: PerGameDifferential | None
    total: TotalDifferential | None
    streak: Streak | None
    points_for: NonNegativeInt | None
    points_against: NonNegativeInt | None
    home: RecordText | None
    away: RecordText | None
    overtime: RecordText | None
    tag: CupTag | None


class CupGroup(FeedModel):
    name: CupGroupName
    teams: Annotated[list[Opponent], Field(max_length=5)]
    rows: Annotated[list[GroupRow], Field(max_length=5)]
    games_final: Annotated[int, Field(ge=0, le=GROUP_GAMES)]
    final: bool

    @model_validator(mode="after")
    def _require_final_with_all_games(self) -> CupGroup:
        if self.final != (self.games_final == GROUP_GAMES):
            raise ValueError("a group is final exactly when its 10 games are final")
        return self


class WildCardRow(FeedModel):
    rank: PositiveInt
    team: Opponent
    group: CupGroupName | None
    wins: NonNegativeInt
    losses: NonNegativeInt
    total: TotalDifferential | None
    points_for: NonNegativeInt | None
    tag: CupTag | None


class WildCardTable(FeedModel):
    conference: Conference
    rows: list[WildCardRow]


class CupGame(FeedModel):
    id: NonEmptyStr
    stage: CupRound
    date: dt.date
    start_time: UtcDatetime
    away: Opponent
    home: Opponent
    status: GameStatus
    score: Score | None
    winner: Side | None
    broadcast: NonEmptyStr | None
    venue: NonEmptyStr
    city: NonEmptyStr | None
    neutral_site: bool
    counts_in_standings: bool
    detail_available: bool

    @model_validator(mode="after")
    def _require_the_result_of_a_final_game(self) -> CupGame:
        final = self.status is GameStatus.FINAL
        if self.winner is not None and not final:
            raise ValueError(f"a {self.status} game has no winner")
        if final and self.score is None:
            raise ValueError("a final game requires score")
        return self

    @model_validator(mode="after")
    def _require_the_rules_of_the_round(self) -> CupGame:
        championship = self.stage is CupRound.CHAMPIONSHIP
        if self.counts_in_standings == championship:
            raise ValueError("only the championship is outside the standings")
        neutral = self.stage in (CupRound.SEMIFINALS, CupRound.CHAMPIONSHIP)
        if self.neutral_site != neutral:
            raise ValueError("only the semifinals and the championship are neutral")
        return self


class CupDay(FeedModel):
    date: dt.date
    games: Annotated[list[CupGame], Field(min_length=1)]


class StageCounts(FeedModel):
    all: NonNegativeInt
    group: NonNegativeInt
    quarterfinals: NonNegativeInt
    semifinals: NonNegativeInt
    championship: NonNegativeInt

    @model_validator(mode="after")
    def _require_all_as_the_sum(self) -> StageCounts:
        total = self.group + self.quarterfinals + self.semifinals + self.championship
        if self.all != total:
            raise ValueError("all must be the sum of the rounds")
        return self


class CupGames(FeedModel):
    days: list[CupDay]
    counts: StageCounts


class SlotId(StrEnum):
    EAST_QF_1 = "east-qf-1"
    EAST_QF_2 = "east-qf-2"
    EAST_SF = "east-sf"
    FINAL = "final"
    WEST_SF = "west-sf"
    WEST_QF_1 = "west-qf-1"
    WEST_QF_2 = "west-qf-2"


class SlotLabelKey(StrEnum):
    SEED = "seed"
    WILD_CARD = "wild_card"
    QUARTERFINAL_WINNER = "quarterfinal_winner"
    SEMIFINAL_WINNER = "semifinal_winner"


class SlotLabel(FeedModel):
    key: SlotLabelKey
    conference: Conference
    seed: Annotated[int, Field(ge=1, le=3)] | None
    quarterfinal: Annotated[int, Field(ge=1, le=2)] | None


class SlotRule(StrEnum):
    BEST_GROUP_WINNER = "best_group_winner"
    SECOND_BEST_GROUP_WINNER = "second_best_group_winner"
    THIRD_BEST_GROUP_WINNER = "third_best_group_winner"
    BEST_NON_WINNER = "best_non_winner"
    QUARTERFINAL_WINNER = "quarterfinal_winner"
    SEMIFINAL_WINNER = "semifinal_winner"


class Projection(FeedModel):
    team: Opponent
    wins: NonNegativeInt
    losses: NonNegativeInt


class SlotSide(FeedModel):
    label: SlotLabel
    rule: SlotRule
    known: bool
    team: Opponent | None
    projected: Projection | None

    @model_validator(mode="after")
    def _require_a_team_or_a_projection(self) -> SlotSide:
        if self.team is not None and self.projected is not None:
            raise ValueError("a side has a team or a projection, not both")
        return self


class BracketSlot(FeedModel):
    id: SlotId
    round: CupRound
    conference: Conference | None
    top: SlotSide
    bottom: SlotSide
    game: CupGame | None

    @model_validator(mode="after")
    def _require_no_conference_for_the_final(self) -> BracketSlot:
        if (self.conference is None) != (self.id is SlotId.FINAL):
            raise ValueError("only the final has no conference")
        return self


class CupFeed(FeedModel):
    season: SeasonLabel
    drawn: bool
    stage: CupStage
    first_game_date: dt.date | None
    group_games_played: Annotated[int, Field(ge=0, le=GROUP_GAMES_TOTAL)]
    group_games_total: Literal[60]
    champion: Opponent | None
    stages: Annotated[list[StageEntry], Field(min_length=4, max_length=4)]
    groups: Annotated[list[CupGroup], Field(min_length=6, max_length=6)]
    wild_card: Annotated[list[WildCardTable], Field(min_length=2, max_length=2)]
    bracket: Annotated[list[BracketSlot], Field(min_length=7, max_length=7)]
    games: CupGames

    @model_validator(mode="after")
    def _require_the_champion_when_complete(self) -> CupFeed:
        if (self.champion is not None) != (self.stage is CupStage.COMPLETE):
            raise ValueError("the champion is set exactly when the Cup is complete")
        return self

    @model_validator(mode="after")
    def _require_the_order_of_the_lists(self) -> CupFeed:
        if [entry.stage for entry in self.stages] != ROUNDS:
            raise ValueError("stages must follow the order of the rounds")
        names = [(g.name.conference, g.name.letter) for g in self.groups]
        expected = [(c, letter) for c in Conference for letter in ("A", "B", "C")]
        if names != expected:
            raise ValueError("groups must be east A to C, then west A to C")
        if [table.conference for table in self.wild_card] != [
            Conference.EAST,
            Conference.WEST,
        ]:
            raise ValueError("wild card tables must be east then west")
        if [slot.id for slot in self.bracket] != list(SlotId):
            raise ValueError("bracket slots must follow the order of the slot ids")
        return self
