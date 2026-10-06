# api/app/sources/scoreboard.py
#
# Scoreboard adapter: fetches the games of one US Eastern day from the
# provider and maps them to contract types. The provider URL comes from
# Settings. Provider data never leaves this module.
#
# SEE: docs/api/games.md, docs/adr/0007-backend-runtime-and-data-pipeline.md

import datetime as dt
import re
from typing import Any

import httpx
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    PositiveInt,
    ValidationError,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import (
    REQUIRED_BY_STATUS,
    FeedModel,
    GameStatus,
    LineScore,
    NonEmptyStr,
    Score,
    Team,
    UtcDatetime,
)
from app.settings import Settings
from app.sources.http import SourceError, get_json
from app.sources.teams import to_team_code

SOURCE = "scoreboard"
DATE_FORMAT = "%Y%m%d"

STATUSES: dict[str, GameStatus] = {
    "STATUS_SCHEDULED": GameStatus.SCHEDULED,
    "STATUS_IN_PROGRESS": GameStatus.LIVE,
    "STATUS_HALFTIME": GameStatus.LIVE,
    "STATUS_END_PERIOD": GameStatus.LIVE,
    "STATUS_FINAL": GameStatus.FINAL,
    "STATUS_DELAYED": GameStatus.DELAYED,
    "STATUS_POSTPONED": GameStatus.POSTPONED,
    "STATUS_CANCELED": GameStatus.CANCELED,
}

_CLOCK = re.compile(r"^\d{1,2}:\d{2}$")
_SECONDS = re.compile(r"^(\d{1,2})(?:\.\d)?$")


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeam(_ProviderModel):
    abbreviation: str
    name: str
    location: str


class _ProviderPeriod(_ProviderModel):
    period: int
    value: float


class _ProviderCompetitor(_ProviderModel):
    home_away: str
    score: str | None = None
    linescores: list[_ProviderPeriod] | None = None
    team: _ProviderTeam


class _ProviderVenue(_ProviderModel):
    full_name: str | None = None


class _ProviderType(_ProviderModel):
    name: str


class _ProviderStatus(_ProviderModel):
    period: int = 0
    display_clock: str | None = None
    type: _ProviderType


class _ProviderCompetition(_ProviderModel):
    venue: _ProviderVenue | None = None
    broadcast: str | None = None
    competitors: list[_ProviderCompetitor]


class _ProviderEvent(_ProviderModel):
    id: str
    date: AwareDatetime
    status: _ProviderStatus
    competitions: list[_ProviderCompetition]


class _ProviderScoreboard(_ProviderModel):
    events: list[_ProviderEvent]


class ScoreboardGame(FeedModel):
    """A game as the scoreboard knows it: a `Game` without stars and detail."""

    id: NonEmptyStr
    away: Team
    home: Team
    status: GameStatus
    start_time: UtcDatetime
    venue: NonEmptyStr
    broadcast: NonEmptyStr | None = None
    period: PositiveInt | None = None
    clock: NonEmptyStr | None = None
    line_score: LineScore | None = None
    score: Score | None = None

    @model_validator(mode="after")
    def _require_fields_of_status(self) -> ScoreboardGame:
        required = REQUIRED_BY_STATUS.get(self.status, ())
        missing = [
            to_camel(name)
            for name in required
            if name in type(self).model_fields and getattr(self, name) is None
        ]
        if missing:
            raise ValueError(f"a {self.status} game requires {', '.join(missing)}")
        return self


def _normalize_clock(display_clock: str | None) -> str | None:
    """Return the clock as M:SS: the provider sends 4:12, or seconds under a minute."""
    if display_clock is None:
        return None
    value = display_clock.strip()
    if _CLOCK.match(value):
        return value
    seconds = _SECONDS.match(value)
    if seconds:
        return f"0:{int(seconds.group(1)):02d}"
    return None


def _team(competitor: _ProviderCompetitor) -> dict[str, Any]:
    team = competitor.team
    return {
        "code": to_team_code(team.abbreviation, source=SOURCE),
        "name": team.name,
        "city": team.location,
    }


def _points(competitor: _ProviderCompetitor) -> list[int]:
    periods = sorted(competitor.linescores or [], key=lambda p: p.period)
    return [int(p.value) for p in periods]


def _map_event(event: _ProviderEvent) -> ScoreboardGame:
    if not event.competitions:
        raise SourceError(SOURCE, f"game {event.id} has no competition")
    competition = event.competitions[0]
    sides = {c.home_away: c for c in competition.competitors}
    if set(sides) != {"home", "away"} or len(competition.competitors) != 2:
        raise SourceError(SOURCE, f"game {event.id} needs one home and one away team")
    away, home = sides["away"], sides["home"]

    provider_status = event.status.type.name
    if provider_status not in STATUSES:
        raise SourceError(SOURCE, f"unknown game status {provider_status!r}")
    status = STATUSES[provider_status]

    data: dict[str, Any] = {
        "id": event.id,
        "away": _team(away),
        "home": _team(home),
        "status": status,
        "start_time": event.date.astimezone(dt.UTC),
        "venue": competition.venue.full_name if competition.venue else None,
        "broadcast": competition.broadcast or None,
    }
    if status is GameStatus.LIVE:
        data["period"] = event.status.period or None
        data["clock"] = _normalize_clock(event.status.display_clock)
    if status in (GameStatus.LIVE, GameStatus.FINAL):
        away_points, home_points = _points(away), _points(home)
        if away_points and home_points:
            data["line_score"] = {"away": away_points, "home": home_points}
        if away.score is not None and home.score is not None:
            data["score"] = {"away": away.score, "home": home.score}
    try:
        game = ScoreboardGame.model_validate(data)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {event.id} is invalid: {first['type']} at {location}"
        ) from None
    return game


async def fetch_games(
    client: httpx.AsyncClient, day: dt.date, settings: Settings
) -> list[ScoreboardGame]:
    """Return the games of a US Eastern day in provider order, or raise SourceError."""
    if settings.scoreboard_url is None:
        raise SourceError(SOURCE, "scoreboard URL is not configured")
    url = settings.scoreboard_url.format(date=day.strftime(DATE_FORMAT))
    body = await get_json(client, url, source=SOURCE)
    try:
        scoreboard = _ProviderScoreboard.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
    return [_map_event(event) for event in scoreboard.events]
