# api/app/sources/player_draft.py
#
# Player draft adapter: fetches one player's draft from the provider and maps
# it to the year, round, pick and standard code of the drafting team, read from
# the provider team id in the team link. A player with no draft was not drafted.
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/player.md, api/app/sources/teams.py

import datetime as dt

import httpx
from pydantic import (
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


class DraftPick(FeedModel):
    """A player's draft pick. Never reaches a feed."""

    year: PositiveInt
    round: PositiveInt
    pick: PositiveInt
    team_code: TeamCode


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
