# api/app/feeds/search.py
#
# Feed models for the search feed: the single source of truth for its shape.
# The JSON Schema and the TypeScript types are generated from these models.
# The feed is the index of the 30 teams and every roster player; matching and
# ranking belong to the page.
#
# SEE: docs/api/search.md, docs/adr/0024-search-feed.md

from typing import Annotated

from pydantic import Field, HttpUrl

from app.feeds.base import HexColor
from app.feeds.game_detail import InjuryStatus
from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.feeds.opponent import TeamColors, TeamLogo
from app.feeds.player import JerseyNumber
from app.feeds.standings import RecordText, StandingsColors

TEAM_COUNT = 30


class SearchTeam(FeedModel):
    code: TeamCode
    city: NonEmptyStr
    name: NonEmptyStr
    colors: StandingsColors
    logo: TeamLogo | None = None
    record: RecordText
    division: NonEmptyStr
    division_rank: Annotated[int, Field(ge=1, le=5)] | None


class SearchInjury(FeedModel):
    status: InjuryStatus


class SearchPlayerTeam(FeedModel):
    code: TeamCode
    primary: HexColor | None
    logo: TeamLogo | None = None
    colors: TeamColors | None = None


class SearchPlayer(FeedModel):
    id: NonEmptyStr
    name: NonEmptyStr
    short_name: NonEmptyStr
    number: JerseyNumber | None
    position: NonEmptyStr | None
    position_abbr: NonEmptyStr | None
    photo_url: HttpUrl | None
    injury: SearchInjury | None
    team: SearchPlayerTeam


class SearchFeed(FeedModel):
    teams: Annotated[
        list[SearchTeam], Field(min_length=TEAM_COUNT, max_length=TEAM_COUNT)
    ]
    players: list[SearchPlayer]
