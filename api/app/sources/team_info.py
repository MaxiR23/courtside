# api/app/sources/team_info.py
#
# Team info adapter: fetches one team's name, colors and arena from the provider
# and maps them to an internal team info. Colors come without the leading "#".
# The alternate color and the franchise venue may be missing: they are null
# (ADR 0064). The logo is the entry tagged "default" (light background) and, when
# there is one, the entry tagged "dark"; an entry whose address is not an http(s)
# URL is dropped, and a team with no usable "default" logo has no logo, never an
# error (ADR 0064, ADR 0068).
# The provider URL comes from Settings. Provider data never leaves this module.
#
# A team's info is fresh for 24 hours (ADR 0066).
# cached_team_info reads the source cache only (ADR 0058).
#
# SEE: docs/api/team.md, api/app/sources/team_schedule.py, docs/adr/0058-bounded-past-competition-reads.md

import datetime as dt
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    HttpUrl,
    StringConstraints,
    TypeAdapter,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr
from app.feeds.opponent import TeamLogo
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, cached_json, get_json
from app.sources.teams import TEAM_CODES

SOURCE = "team_info"
FRESH_FOR = dt.timedelta(hours=24)
PROVIDER_CODES: dict[str, str] = {
    code: provider for provider, code in TEAM_CODES.items()
}

HexDigits = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{6}$")]
_HTTP_URL = TypeAdapter(HttpUrl)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderAddress(_ProviderModel):
    city: str | None = None


class _ProviderImage(_ProviderModel):
    href: str


class _ProviderLogo(_ProviderModel):
    href: str
    rel: list[str] = []


class _ProviderVenue(_ProviderModel):
    full_name: str
    address: _ProviderAddress | None = None
    images: list[_ProviderImage] = []


class _ProviderFranchise(_ProviderModel):
    venue: _ProviderVenue | None = None


class _ProviderTeam(_ProviderModel):
    location: str
    name: str
    color: HexDigits
    alternate_color: HexDigits | None = None
    franchise: _ProviderFranchise | None = None
    logos: list[_ProviderLogo] = []


class _ProviderTeamInfo(_ProviderModel):
    team: _ProviderTeam


class TeamInfo(FeedModel):
    """A team's identity, colors without "#", and arena. Never reaches a feed."""

    location: NonEmptyStr
    name: NonEmptyStr
    color: HexDigits
    alternate_color: HexDigits | None = None
    venue_name: NonEmptyStr | None = None
    venue_city: NonEmptyStr | None = None
    venue_photo_url: NonEmptyStr | None = None
    logo: TeamLogo | None = None


def secondary_color(info: TeamInfo) -> str | None:
    """The secondary color with its "#", or None when the team has none."""
    return None if info.alternate_color is None else f"#{info.alternate_color}"


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
    return _map(body, team_code)


def _logo_href(logos: list[_ProviderLogo], tag: str) -> str | None:
    """The address of the first logo with the tag that is an http(s) URL."""
    for logo in logos:
        if tag not in logo.rel:
            continue
        try:
            _HTTP_URL.validate_python(logo.href)
        except ValidationError:
            continue
        return logo.href
    return None


def _logo(logos: list[_ProviderLogo]) -> dict[str, str | None] | None:
    light = _logo_href(logos, "default")
    if light is None:
        return None
    return {"light": light, "dark": _logo_href(logos, "dark")}


def _map(body: object, team_code: str) -> TeamInfo:
    try:
        provider = _ProviderTeamInfo.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None

    team = provider.team
    venue = team.franchise.venue if team.franchise else None
    try:
        return TeamInfo.model_validate(
            {
                "location": team.location,
                "name": team.name,
                "color": team.color,
                "alternate_color": team.alternate_color,
                "venue_name": venue.full_name if venue else None,
                "venue_city": venue.address.city if venue and venue.address else None,
                "venue_photo_url": venue.images[0].href
                if venue and venue.images
                else None,
                "logo": _logo(team.logos),
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team {team_code} is invalid: {first['type']} at {_location(error)}",
        ) from None


def cached_team_info(
    client: SourceClient, team_code: str, settings: Settings
) -> TeamInfo | None:
    """Return a team's info from the source cache, whatever its age, or None.
    It sends no request."""
    if settings.team_info_url is None or team_code not in PROVIDER_CODES:
        return None
    body = cached_json(
        client, settings.team_info_url.format(team=PROVIDER_CODES[team_code])
    )
    if body is None:
        return None
    try:
        return _map(body, team_code)
    except SourceError:
        return None
