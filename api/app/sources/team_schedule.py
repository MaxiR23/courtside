# api/app/sources/team_schedule.py
#
# Team schedule adapter: fetches one team's schedule from the provider and
# maps its completed games to the contract's last games, newest first, and to
# the arena of each completed game by game id. The provider URL comes from
# Settings. Provider data never leaves this module.
#
# SEE: docs/api/game-detail.md, api/app/sources/team_players.py

from typing import Annotated, Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import GameResult, LastGame
from app.feeds.games import FeedModel, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceError, get_json
from app.sources.teams import TEAM_CODES, to_team_code

SOURCE = "team_schedule"
EASTERN = ZoneInfo("America/New_York")
LAST_GAMES = 5
PROVIDER_CODES: dict[str, str] = {
    code: provider for provider, code in TEAM_CODES.items()
}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeam(_ProviderModel):
    abbreviation: str


class _ProviderScore(_ProviderModel):
    value: float


class _ProviderCompetitor(_ProviderModel):
    home_away: str
    winner: bool = False
    team: _ProviderTeam
    score: _ProviderScore | None = None


class _ProviderVenue(_ProviderModel):
    full_name: str


class _ProviderStatusType(_ProviderModel):
    state: str
    completed: bool


class _ProviderStatus(_ProviderModel):
    type: _ProviderStatusType


class _ProviderCompetition(_ProviderModel):
    venue: _ProviderVenue
    status: _ProviderStatus
    competitors: list[_ProviderCompetitor]


class _ProviderEvent(_ProviderModel):
    id: str
    date: AwareDatetime
    competitions: Annotated[list[_ProviderCompetition], Field(min_length=1)]


class _ProviderSchedule(_ProviderModel):
    events: list[_ProviderEvent]


class TeamSchedule(FeedModel):
    """A team's completed games: the last five for the feed, and the arena of
    each completed game by game id, for the season series. Never reaches the feed."""

    last_games: Annotated[list[LastGame], Field(max_length=LAST_GAMES)]
    arenas: dict[NonEmptyStr, NonEmptyStr]


def _provider_code(team_code: str) -> str:
    try:
        return PROVIDER_CODES[team_code]
    except KeyError:
        raise SourceError(SOURCE, f"unknown team code {team_code!r}") from None


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _last_game(team_code: str, event: _ProviderEvent) -> dict[str, Any]:
    competitors = {
        to_team_code(c.team.abbreviation, source=SOURCE): c
        for c in event.competitions[0].competitors
    }
    team = competitors.get(team_code)
    if team is None or len(competitors) != 2:
        raise SourceError(SOURCE, f"team {team_code} is missing from game {event.id}")
    opponent_code, opponent = next(
        (code, c) for code, c in competitors.items() if code != team_code
    )
    if team.score is None or opponent.score is None:
        raise SourceError(SOURCE, f"game {event.id} has no score")
    return {
        "date": event.date.astimezone(EASTERN).date(),
        "opponent": opponent_code,
        "is_home": team.home_away == "home",
        "result": GameResult.WIN if team.winner else GameResult.LOSS,
        "team_score": int(team.score.value),
        "opponent_score": int(opponent.score.value),
    }


async def fetch_team_schedule(
    client: httpx.AsyncClient, team_code: str, settings: Settings
) -> TeamSchedule:
    """Return the completed games of one team, or raise SourceError."""
    if settings.team_schedule_url is None:
        raise SourceError(SOURCE, "team schedule URL is not configured")
    provider_code = _provider_code(team_code)
    url = settings.team_schedule_url.format(team=provider_code)
    body = await get_json(client, url, source=SOURCE)
    try:
        schedule = _ProviderSchedule.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None

    completed = [
        event
        for event in schedule.events
        if event.competitions[0].status.type.completed
        and event.competitions[0].status.type.state == "post"
    ]
    newest_first = sorted(completed, key=lambda event: event.date, reverse=True)
    try:
        return TeamSchedule.model_validate(
            {
                "last_games": [
                    _last_game(team_code, event) for event in newest_first[:LAST_GAMES]
                ],
                "arenas": {
                    event.id: event.competitions[0].venue.full_name
                    for event in completed
                },
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"team schedule is invalid: {first['type']} at {_location(error)}",
        ) from None
