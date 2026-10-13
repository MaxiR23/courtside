# api/app/sources/depth_chart.py
#
# Depth chart adapter: fetches the current depth chart of one team from the
# provider and maps it to the athlete ids of each of the five positions (pg, sg,
# sf, pf, c) in rank order. The chart is the first item of the payload; no item
# is an empty chart and a missing position has no entry. Keys outside the five
# positions are ignored. An athlete is read from the provider athlete id in its
# link, never by following the link. The provider team id comes from the fixed
# team id table. The provider URL comes from Settings. Provider data never leaves
# this module.
#
# SEE: docs/api/cup-matchup.md, docs/adr/0029-cup-matchup-feed.md,
# api/app/sources/teams.py

import datetime as dt
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import TEAM_CODES, TEAM_IDS

SOURCE = "depth_chart"
FRESH_FOR = dt.timedelta(hours=24)
Position = Literal["pg", "sg", "sf", "pf", "c"]
POSITIONS: tuple[Position, ...] = ("pg", "sg", "sf", "pf", "c")

# The provider team id of each standard team code.
PROVIDER_IDS: dict[str, str] = {
    TEAM_CODES[provider]: team_id for team_id, provider in TEAM_IDS.items()
}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderRef(_ProviderModel):
    ref: str = Field(alias="$ref")


class _ProviderSlot(_ProviderModel):
    athlete: _ProviderRef


class _ProviderPosition(_ProviderModel):
    athletes: list[_ProviderSlot]


class _ProviderChart(_ProviderModel):
    positions: dict[str, _ProviderPosition] = {}


class _ProviderCharts(_ProviderModel):
    items: list[_ProviderChart]


class DepthChart(FeedModel):
    """The current depth chart of one team: per position, the athlete ids from
    rank 1 down. A missing position has no entry. Never reaches a feed."""

    positions: dict[Position, list[NonEmptyStr]]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _athlete_id(ref: str) -> str:
    parts = httpx.URL(ref).path.rstrip("/").split("/")
    if "athletes" not in parts[:-1]:
        raise SourceError(SOURCE, "athlete link has no athlete id")
    return parts[parts.index("athletes") + 1]


async def fetch_depth_chart(
    client: SourceClient, team_code: str, season: int, settings: Settings
) -> DepthChart:
    """Return the current depth chart of one team, or raise SourceError."""
    if not settings.depth_chart_url:
        raise SourceError(SOURCE, "depth chart URL is not configured")
    team_id = PROVIDER_IDS.get(team_code)
    if team_id is None:
        raise SourceError(SOURCE, f"unknown team code {team_code!r}")
    url = settings.depth_chart_url.format(season=season, team_id=team_id)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderCharts.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    if not provider.items:
        return DepthChart(positions={})
    chart = provider.items[0]
    try:
        return DepthChart.model_validate(
            {
                "positions": {
                    position: [_athlete_id(slot.athlete.ref) for slot in found.athletes]
                    for position, found in chart.positions.items()
                    if position in POSITIONS
                }
            }
        )
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
