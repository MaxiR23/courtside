# api/app/sources/season_team.py
#
# Season team adapter: fetches the team object of one team in one season and
# maps its abbreviation, display name, name, location and active state to an
# internal season team. A 404 means the team has no object that season.
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/team.md, docs/adr/0043-season-feeds-and-franchise-names.md

import datetime as dt

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import PROVIDER_IDS

SOURCE = "season_team"
FRESH_FOR = dt.timedelta(hours=1)


class _ProviderSeasonTeam(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )

    id: str
    abbreviation: str
    display_name: str
    name: str
    location: str
    is_active: bool


class SeasonTeam(FeedModel):
    """A team as it was named in one season. Never reaches a feed."""

    team_id: NonEmptyStr
    abbreviation: NonEmptyStr
    display_name: NonEmptyStr
    name: NonEmptyStr
    location: NonEmptyStr
    active: bool


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


async def fetch_season_team(
    client: SourceClient, team_code: str, season: int, settings: Settings
) -> SeasonTeam | None:
    """Return the team of one season, None when the season has no such team, or
    raise SourceError."""
    if settings.season_team_url is None:
        raise SourceError(SOURCE, "season team URL is not configured")
    try:
        team_id = PROVIDER_IDS[team_code]
    except KeyError:
        raise SourceError(SOURCE, f"unknown team code {team_code!r}") from None
    url = settings.season_team_url.format(season=season, team_id=team_id)
    try:
        body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    except SourceError as error:
        if error.status_code == 404:
            return None
        raise
    try:
        provider = _ProviderSeasonTeam.model_validate(body)
        return SeasonTeam.model_validate(
            {
                "team_id": provider.id,
                "abbreviation": provider.abbreviation,
                "display_name": provider.display_name,
                "name": provider.name,
                "location": provider.location,
                "active": provider.is_active,
            }
        )
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
