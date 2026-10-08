# api/app/sources/team_info.py
#
# Team info adapter: fetches one team's name, colors and arena from the provider
# and maps them to an internal team info. Colors come without the leading "#".
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/team.md, api/app/sources/team_schedule.py

import datetime as dt
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import TEAM_CODES

SOURCE = "team_info"
FRESH_FOR = dt.timedelta(hours=1)
PROVIDER_CODES: dict[str, str] = {
    code: provider for provider, code in TEAM_CODES.items()
}

HexDigits = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{6}$")]


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderAddress(_ProviderModel):
    city: str | None = None


class _ProviderImage(_ProviderModel):
    href: str


class _ProviderVenue(_ProviderModel):
    full_name: str
    address: _ProviderAddress | None = None
    images: list[_ProviderImage] = []


class _ProviderFranchise(_ProviderModel):
    venue: _ProviderVenue


class _ProviderTeam(_ProviderModel):
    location: str
    name: str
    color: HexDigits
    alternate_color: HexDigits
    franchise: _ProviderFranchise


class _ProviderTeamInfo(_ProviderModel):
    team: _ProviderTeam


class TeamInfo(FeedModel):
    """A team's identity, colors without "#", and arena. Never reaches a feed."""

    location: NonEmptyStr
    name: NonEmptyStr
    color: HexDigits
    alternate_color: HexDigits
    venue_name: NonEmptyStr
    venue_city: NonEmptyStr | None = None
    venue_photo_url: NonEmptyStr | None = None


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _provider_code(team_code: str) -> str:
    try:
        return PROVIDER_CODES[team_code]
    except KeyError:
        raise SourceError(SOURCE, f"unknown team code {team_code!r}") from None


async def fetch_team_info(
    client: SourceClient, team_code: str, settings: Settings
) -> TeamInfo:
    """Return the identity, colors and arena of one team, or raise SourceError."""
    if settings.team_info_url is None:
        raise SourceError(SOURCE, "team info URL is not configured")
    provider_code = _provider_code(team_code)
    url = settings.team_info_url.format(team=provider_code)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderTeamInfo.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None

    team = provider.team
    venue = team.franchise.venue
    try:
        return TeamInfo.model_validate(
            {
                "location": team.location,
                "name": team.name,
                "color": team.color,
                "alternate_color": team.alternate_color,
                "venue_name": venue.full_name,
                "venue_city": venue.address.city if venue.address else None,
                "venue_photo_url": venue.images[0].href if venue.images else None,
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team {team_code} is invalid: {first['type']} at {_location(error)}",
        ) from None
