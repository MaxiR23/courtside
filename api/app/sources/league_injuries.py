# api/app/sources/league_injuries.py
#
# League injuries adapter: fetches the injuries of every team from the
# provider and maps them to the contract's injuries by standard team code. Each
# team entry is attributed by its provider team id, never by the athlete's
# team, which is the athlete's current team. The provider URL comes from
# Settings. Provider data never leaves this module.
#
# SEE: docs/api/game-detail.md, api/app/sources/standings.py

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import Injury, InjuryStatus
from app.feeds.games import FeedModel, TeamCode
from app.settings import Settings
from app.sources.http import SourceError, get_json
from app.sources.teams import team_code_of_id

SOURCE = "league_injuries"


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderAthlete(_ProviderModel):
    display_name: str


class _ProviderInjury(_ProviderModel):
    status: str
    short_comment: str | None = None
    athlete: _ProviderAthlete


class _ProviderTeamEntry(_ProviderModel):
    id: str
    injuries: list[_ProviderInjury] = []


class _ProviderLeagueInjuries(_ProviderModel):
    injuries: list[_ProviderTeamEntry]


class LeagueInjuries(FeedModel):
    """Injuries by team code. A team that is absent reported none."""

    teams: dict[TeamCode, list[Injury]]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _injury(injury: _ProviderInjury) -> dict[str, object]:
    try:
        status = InjuryStatus(injury.status.lower())
    except ValueError:
        raise SourceError(SOURCE, "unknown injury status") from None
    return {
        "display_name": injury.athlete.display_name,
        "status": status,
        "comment": injury.short_comment or None,
    }


async def fetch_league_injuries(
    client: httpx.AsyncClient, settings: Settings
) -> LeagueInjuries:
    """Return the injuries of every team, or raise SourceError."""
    if settings.league_injuries_url is None:
        raise SourceError(SOURCE, "league injuries URL is not configured")
    body = await get_json(client, settings.league_injuries_url, source=SOURCE)
    try:
        provider = _ProviderLeagueInjuries.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None

    teams: dict[str, list[dict[str, object]]] = {}
    for entry in provider.injuries:
        if not entry.injuries:
            continue
        code = team_code_of_id(entry.id, source=SOURCE)
        teams[code] = [_injury(injury) for injury in entry.injuries]

    try:
        return LeagueInjuries.model_validate({"teams": teams})
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE, f"injuries are invalid: {first['type']} at {_location(error)}"
        ) from None
