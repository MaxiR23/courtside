# api/app/sources/player_draft.py
#
# Player draft adapter: fetches one player's draft from the provider and maps
# it to the year, round, pick and standard code of the drafting team, read from
# the provider team id in the team link. A player with no draft was not drafted.
# It also reads, from the same response, the athlete's active state and identity.
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/player.md, api/app/sources/teams.py

import datetime as dt

import httpx
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, TeamCode
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.team_players import RosterEntry
from app.sources.teams import team_code_of_id

SOURCE = "player_draft"
FRESH_FOR = dt.timedelta(hours=1)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeamRef(_ProviderModel):
    ref: str = Field(alias="$ref")


class _ProviderDraft(_ProviderModel):
    year: int
    round: int
    selection: int
    team: _ProviderTeamRef


class _ProviderPlayer(_ProviderModel):
    draft: _ProviderDraft | None = None


class _ProviderBirthPlace(_ProviderModel):
    city: str | None = None
    state: str | None = None
    country: str | None = None


class _ProviderExperience(_ProviderModel):
    years: int


class _ProviderPosition(_ProviderModel):
    name: str | None = None
    abbreviation: str | None = None


class _ProviderHref(_ProviderModel):
    href: str


class _ProviderAthlete(_ProviderModel):
    active: bool
    first_name: str
    last_name: str
    display_name: str | None = None
    jersey: str | None = None
    height: float | None = None
    display_height: str | None = None
    weight: float | None = None
    date_of_birth: AwareDatetime | None = None
    birth_place: _ProviderBirthPlace | None = None
    experience: _ProviderExperience | None = None
    position: _ProviderPosition | None = None
    headshot: _ProviderHref | None = None


class DraftPick(FeedModel):
    """A player's draft pick. Never reaches a feed."""

    year: PositiveInt
    round: PositiveInt
    pick: PositiveInt
    team_code: TeamCode


class PlayerAthlete(FeedModel):
    """A player's active state and identity from the athlete object. The college
    is null: the object carries it as a link that is not followed. Never reaches
    a feed."""

    active: bool
    entry: RosterEntry


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _team_id(ref: str) -> str:
    parts = httpx.URL(ref).path.rstrip("/").split("/")
    if "teams" not in parts[:-1]:
        raise SourceError(SOURCE, "draft link has no team id")
    return parts[parts.index("teams") + 1]


async def fetch_player_draft(
    client: SourceClient, player_id: str, settings: Settings
) -> DraftPick | None:
    """Return one player's draft pick, None when he was not drafted, or raise
    SourceError."""
    if settings.player_draft_url is None:
        raise SourceError(SOURCE, "player draft URL is not configured")
    url = settings.player_draft_url.format(player_id=player_id)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderPlayer.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    draft = provider.draft
    if draft is None:
        return None
    try:
        return DraftPick.model_validate(
            {
                "year": draft.year,
                "round": draft.round,
                "pick": draft.selection,
                "team_code": team_code_of_id(_team_id(draft.team.ref), source=SOURCE),
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"player {player_id} is invalid: {first['type']} at {_location(error)}",
        ) from None


async def fetch_player_athlete(
    client: SourceClient, player_id: str, settings: Settings
) -> PlayerAthlete:
    """Return one player's active state and identity, or raise SourceError. It
    reads the URL of the draft, so the source cache serves it after the draft."""
    if settings.player_draft_url is None:
        raise SourceError(SOURCE, "player draft URL is not configured")
    url = settings.player_draft_url.format(player_id=player_id)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        athlete = _ProviderAthlete.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    place = athlete.birth_place
    try:
        return PlayerAthlete.model_validate(
            {
                "active": athlete.active,
                "entry": {
                    "player_id": player_id,
                    "first_name": athlete.first_name,
                    "last_name": athlete.last_name,
                    "display_name": athlete.display_name,
                    "jersey": athlete.jersey,
                    "position_name": athlete.position.name
                    if athlete.position
                    else None,
                    "position_abbreviation": (
                        athlete.position.abbreviation if athlete.position else None
                    ),
                    "height_inches": athlete.height,
                    "display_height": athlete.display_height,
                    "weight_lb": athlete.weight,
                    "birth_date": (
                        athlete.date_of_birth.astimezone(dt.UTC).date()
                        if athlete.date_of_birth
                        else None
                    ),
                    "birth_city": place.city if place else None,
                    "birth_state": place.state if place else None,
                    "birth_country": place.country if place else None,
                    "college": None,
                    "experience": (
                        athlete.experience.years if athlete.experience else None
                    ),
                    "headshot_url": athlete.headshot.href if athlete.headshot else None,
                },
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"player {player_id} is invalid: {first['type']} at {_location(error)}",
        ) from None
