# api/app/feeds/power_ranking.py
#
# Feed models for the power ranking feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models. The
# feed lists the 30 teams by rank with every number as ready text; it is
# unavailable, with no teams, outside the regular season or when the source data is
# not complete (ADR 0075). The logo and colors of a team are added when served
# (ADR 0068) and so is its resolved color (ADR 0072); they are null in the stored
# file.
#
# SEE: docs/api/power-ranking.md, docs/adr/0075-power-ranking-feed.md

from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from app.feeds.base import HexColor, Percentage, SeasonLabel
from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.feeds.opponent import TeamColors, TeamLogo
from app.feeds.standings import RecordText

TEAM_COUNT = 30


class PowerRankingState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class PowerRankingIdentity(FeedModel):
    code: TeamCode
    # From the stored standings feed, else the cached team info; null with neither
    # (ADR 0078).
    name: NonEmptyStr | None
    city: NonEmptyStr | None
    # The logo and colors (ADR 0068) and the resolved color (ADR 0072), added when
    # served; null in the stored file.
    logo: TeamLogo | None = None
    colors: TeamColors | None = None
    accent: HexColor | None = None


class PowerRankingTeam(FeedModel):
    rank: Annotated[int, Field(ge=1, le=TEAM_COUNT)]
    tied: bool
    team: PowerRankingIdentity
    record: RecordText
    rating: NonEmptyStr
    rating_negative: bool
    offense: NonEmptyStr
    defense: NonEmptyStr
    projected: RecordText
    playoffs: NonEmptyStr
    title: NonEmptyStr
    playoffs_low: bool
    title_share: Percentage


class PowerRankingFeed(FeedModel):
    season: SeasonLabel
    state: PowerRankingState
    teams: list[PowerRankingTeam]

    @model_validator(mode="after")
    def _require_the_teams_of_the_state(self) -> PowerRankingFeed:
        expected = TEAM_COUNT if self.state is PowerRankingState.AVAILABLE else 0
        if len(self.teams) != expected:
            raise ValueError(f"the state requires {expected} teams")
        ranks = [team.rank for team in self.teams]
        if ranks != sorted(ranks):
            raise ValueError("teams must be ordered by rank")
        codes = [team.team.code for team in self.teams]
        if len(set(codes)) != len(codes):
            raise ValueError("team codes must be distinct")
        return self
