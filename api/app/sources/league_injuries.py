# api/app/sources/league_injuries.py
#
# League injuries adapter: fetches the injuries of every team from the
# provider and maps them to the contract's injuries by standard team code. Each
# team entry is attributed by its provider team id, never by the athlete's
# team, which is the athlete's current team. Each report keeps the athlete id,
# read from the athlete's links, and the date of the report. The provider URL
# comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/game-detail.md, api/app/sources/standings.py

import datetime as dt

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import Injury, InjuryStatus
from app.feeds.games import FeedModel, NonEmptyStr, TeamCode, UtcDatetime
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import team_code_of_id

SOURCE = "league_injuries"
FRESH_FOR = dt.timedelta(hours=1)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderLink(_ProviderModel):
    href: str


class _ProviderAthlete(_ProviderModel):
    display_name: str
    links: list[_ProviderLink] = []


class _ProviderInjury(_ProviderModel):
    status: str
    short_comment: str | None = None
    date: AwareDatetime | None = None
    athlete: _ProviderAthlete


class _ProviderTeamEntry(_ProviderModel):
    id: str
    injuries: list[_ProviderInjury] = []


class _ProviderLeagueInjuries(_ProviderModel):
    injuries: list[_ProviderTeamEntry]


class InjuryReport(FeedModel):
    """One injury with the athlete's id and the report's date. Never reaches a feed."""

    injury: Injury
    player_id: NonEmptyStr | None = None
    updated_at: UtcDatetime | None = None


class LeagueInjuries(FeedModel):
    """Injury reports by team code. A team that is absent reported none."""

    teams: dict[TeamCode, list[InjuryReport]]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _athlete_id(athlete: _ProviderAthlete) -> str | None:
    """The id that follows the `id` segment of the first link that has one."""
    for link in athlete.links:
        parts = httpx.URL(link.href).path.split("/")
        for index, part in enumerate(parts[:-1]):
            if part == "id" and parts[index + 1].isdigit():
                return parts[index + 1]
    return None


def _injury(injury: _ProviderInjury) -> dict[str, object]:
    try:
        status = InjuryStatus(injury.status.lower())
    except ValueError:
        raise SourceError(SOURCE, "unknown injury status") from None
    return {
        "injury": {
            "display_name": injury.athlete.display_name,
            "status": status,
            "comment": injury.short_comment or None,
        },
        "player_id": _athlete_id(injury.athlete),
        "updated_at": injury.date,
    }


async def fetch_league_injuries(
    client: SourceClient, settings: Settings
) -> LeagueInjuries:
    """Return the injuries of every team, or raise SourceError."""
    if settings.league_injuries_url is None:
        raise SourceError(SOURCE, "league injuries URL is not configured")
    body = await get_json(
        client, settings.league_injuries_url, source=SOURCE, fresh=FRESH_FOR
    )
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
