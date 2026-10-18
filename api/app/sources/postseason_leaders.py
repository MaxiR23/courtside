# api/app/sources/postseason_leaders.py
#
# Postseason leaders adapter: fetches the postseason leaders of a season from the
# provider and maps the nine categories the playoffs feed shows (points,
# rebounds, assists, steals, blocks, field goal percentage, threes made, double
# doubles and minutes) to the athlete ids and the display values, in the
# provider's order. Any other category is ignored and a category with no leaders
# is absent. An athlete is read from the provider athlete id in its link, never
# by following the link. A leader's team code comes from its team link, null
# when the link is absent or is not a league team. The provider URL comes from Settings. Provider data
# never leaves this module.
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md,
# api/app/sources/depth_chart.py

import datetime as dt

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.feeds.playoffs import LeaderCategory
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import TEAM_IDS, team_code_of_id

SOURCE = "postseason_leaders"
FRESH_FOR = dt.timedelta(hours=1)
# The provider's category names.
CATEGORIES: dict[str, LeaderCategory] = {
    "pointsPerGame": LeaderCategory.POINTS,
    "reboundsPerGame": LeaderCategory.REBOUNDS,
    "assistsPerGame": LeaderCategory.ASSISTS,
    "stealsPerGame": LeaderCategory.STEALS,
    "blocksPerGame": LeaderCategory.BLOCKS,
    "fieldGoalPercentage": LeaderCategory.FIELD_GOAL_PCT,
    "3PointsMadePerGame": LeaderCategory.THREES_MADE,
    "doubleDouble": LeaderCategory.DOUBLE_DOUBLES,
    "minutesPerGame": LeaderCategory.MINUTES,
}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderRef(_ProviderModel):
    ref: str = Field(alias="$ref")


class _ProviderLeader(_ProviderModel):
    display_value: str
    athlete: _ProviderRef
    team: _ProviderRef | None = None


class _ProviderCategory(_ProviderModel):
    name: str
    leaders: list[_ProviderLeader] = []


class _ProviderLeaders(_ProviderModel):
    categories: list[_ProviderCategory]


class LeaderEntry(FeedModel):
    """One leader of a category. Never reaches a feed."""

    player_id: NonEmptyStr
    value: NonEmptyStr
    team_code: TeamCode | None = None


class PostseasonLeaders(FeedModel):
    """The leaders of each category in the provider's order. A category with no
    leaders is absent. Never reaches a feed."""

    categories: dict[LeaderCategory, list[LeaderEntry]]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _athlete_id(ref: str) -> str:
    parts = httpx.URL(ref).path.rstrip("/").split("/")
    if "athletes" not in parts[:-1]:
        raise SourceError(SOURCE, "athlete link has no athlete id")
    return parts[parts.index("athletes") + 1]


def _team_code(ref: str | None) -> str | None:
    if ref is None:
        return None
    parts = httpx.URL(ref).path.rstrip("/").split("/")
    if "teams" not in parts[:-1]:
        return None
    team_id = parts[parts.index("teams") + 1]
    return team_code_of_id(team_id, source=SOURCE) if team_id in TEAM_IDS else None


async def fetch_postseason_leaders(
    client: SourceClient, season: int, settings: Settings
) -> PostseasonLeaders:
    """Return the postseason leaders of a season, or raise SourceError."""
    if not settings.postseason_leaders_url:
        raise SourceError(SOURCE, "postseason leaders URL is not configured")
    url = settings.postseason_leaders_url.format(season=season)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderLeaders.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    categories: dict[LeaderCategory, list[dict[str, str | None]]] = {}
    for category in provider.categories:
        known = CATEGORIES.get(category.name)
        if known is None or not category.leaders:
            continue
        categories[known] = [
            {
                "player_id": _athlete_id(leader.athlete.ref),
                "value": leader.display_value,
                "team_code": _team_code(
                    None if leader.team is None else leader.team.ref
                ),
            }
            for leader in category.leaders
        ]
    try:
        return PostseasonLeaders.model_validate({"categories": categories})
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
