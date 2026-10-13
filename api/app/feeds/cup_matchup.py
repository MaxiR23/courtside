# api/app/feeds/cup_matchup.py
#
# Feed models for the Cup matchup feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models. One
# feed per bracket slot: the slot's game as the Cup feed stores it, and per side
# its label, its rule and, when the team is known or projected, the team's path
# in the Cup, its injuries and its roster with per game averages, starters and
# stat leaders. Labels are keys and parts, never prose: the page writes the
# words. Every team is an Opponent.
#
# SEE: docs/api/cup-matchup.md, docs/adr/0029-cup-matchup-feed.md

from pydantic import NonNegativeFloat, NonNegativeInt, model_validator

from app.feeds.cup import CupGame, SlotId, SlotLabel, SlotRule
from app.feeds.game_detail import Conference, GameResult
from app.feeds.games import (
    CupRound,
    FeedModel,
    GameStatus,
    NonEmptyStr,
    UtcDatetime,
)
from app.feeds.opponent import Opponent
from app.feeds.player import SeasonLabel
from app.feeds.team import RosterPlayer, TeamInjury

STARTERS = 5


class PerGameAverages(FeedModel):
    points: NonNegativeFloat
    rebounds: NonNegativeFloat
    assists: NonNegativeFloat


class StatLeaders(FeedModel):
    points: bool
    rebounds: bool
    assists: bool


class MatchupPlayer(RosterPlayer):
    averages: PerGameAverages | None
    starter: bool
    leader: StatLeaders

    @model_validator(mode="after")
    def _require_averages_to_lead(self) -> MatchupPlayer:
        leads = self.leader.points or self.leader.rebounds or self.leader.assists
        if self.averages is None and leads:
            raise ValueError("a player with no averages leads no stat")
        return self


class PathGame(FeedModel):
    game_id: NonEmptyStr
    stage: CupRound
    start_time: UtcDatetime
    opponent: Opponent
    is_home: bool
    status: GameStatus
    result: GameResult | None
    team_score: NonNegativeInt | None
    opponent_score: NonNegativeInt | None
    detail_available: bool

    @model_validator(mode="after")
    def _require_the_result_exactly_when_final(self) -> PathGame:
        final = self.status is GameStatus.FINAL
        result = (self.result, self.team_score, self.opponent_score)
        if any(value is not None for value in result) != final or (
            final and any(value is None for value in result)
        ):
            raise ValueError("a path game has its result and scores exactly when final")
        return self


class MatchupTeam(FeedModel):
    path: list[PathGame]
    injuries: list[TeamInjury]
    roster: list[MatchupPlayer]

    @model_validator(mode="after")
    def _require_the_path_in_start_order(self) -> MatchupTeam:
        times = [game.start_time for game in self.path]
        if times != sorted(times):
            raise ValueError("path must be in start order")
        return self

    @model_validator(mode="after")
    def _require_at_most_five_starters(self) -> MatchupTeam:
        if sum(player.starter for player in self.roster) > STARTERS:
            raise ValueError("a team has at most 5 starters")
        return self


class MatchupSide(FeedModel):
    label: SlotLabel
    rule: SlotRule
    known: bool
    projected: bool
    team: Opponent | None
    details: MatchupTeam | None

    @model_validator(mode="after")
    def _require_details_exactly_with_a_team(self) -> MatchupSide:
        if (self.details is None) != (self.team is None):
            raise ValueError("details are set exactly when the team is set")
        return self

    @model_validator(mode="after")
    def _require_a_team_to_be_projected(self) -> MatchupSide:
        if self.projected and self.team is None:
            raise ValueError("a projected side has a team")
        return self


class CupMatchupFeed(FeedModel):
    season: SeasonLabel
    id: SlotId
    round: CupRound
    conference: Conference | None
    game: CupGame | None
    top: MatchupSide
    bottom: MatchupSide

    @model_validator(mode="after")
    def _require_no_conference_for_the_final(self) -> CupMatchupFeed:
        if (self.conference is None) != (self.id is SlotId.FINAL):
            raise ValueError("only the final has no conference")
        return self
