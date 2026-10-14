# api/app/sources/all_star_scoreboard.py
#
# All-Star view of the scoreboard (ADR 0036).
#
# Reads the same day as app.sources.scoreboard, from the same URL with the same
# freshness (30 seconds unless the caller passes another), so both share one
# cached response. It adds what the All-Star feed
# needs and a game of the games feed does not carry: the note, the status text
# and the sides of a game between All-Star teams, which have a code or a name
# and no city (their location repeats the name). It keeps only the games of the regular season (type
# 2) whose competition type is ALLSTAR. A side with neither a code nor a name
# is undecided and is left null (ADR 0039). Its
# results never reach a core feed, and removing the All-Star section removes
# this module.
#
# A live or final game with a null side or without both scores fails the read.
# The status text and the period are passed as the source sends them; the clock
# is normalized to M:SS as the games feed does.
#
# SEE: docs/api/all-star.md, docs/adr/0036-all-star-feed.md,
# api/app/sources/postseason_scoreboard.py

import datetime as dt

from pydantic import AwareDatetime, Field, PositiveInt, ValidationError

from app.feeds.games import FeedModel, GameStatus, NonEmptyStr, Score, UtcDatetime
from app.settings import Settings
from app.sources.http import Freshness, SourceClient, SourceError, get_json
from app.sources.scoreboard import (
    DATE_FORMAT,
    FRESH_FOR,
    SOURCE,
    STATUSES,
    _normalize_clock,
    _ProviderModel,
    _ProviderVenue,
)

REGULAR_SEASON = 2
COMPETITION_TYPE = "ALLSTAR"


class _AllStarTeam(_ProviderModel):
    abbreviation: str | None = None
    name: str | None = None


class _AllStarCompetitor(_ProviderModel):
    home_away: str
    score: str | None = None
    team: _AllStarTeam


class _AllStarNote(_ProviderModel):
    headline: str | None = None


class _AllStarCompetitionType(_ProviderModel):
    abbreviation: str | None = None


class _AllStarCompetition(_ProviderModel):
    type: _AllStarCompetitionType | None = None
    notes: list[_AllStarNote] = Field(default_factory=list)
    venue: _ProviderVenue | None = None
    competitors: list[_AllStarCompetitor]


class _AllStarStatusType(_ProviderModel):
    name: str
    short_detail: str | None = None


class _AllStarStatus(_ProviderModel):
    period: int = 0
    display_clock: str | None = None
    type: _AllStarStatusType


class _AllStarSeason(_ProviderModel):
    type: int | None = None


class _AllStarEvent(_ProviderModel):
    id: str
    date: AwareDatetime
    season: _AllStarSeason | None = None
    status: _AllStarStatus
    competitions: list[_AllStarCompetition] = Field(default_factory=list)


class _AllStarScoreboard(_ProviderModel):
    events: list[_AllStarEvent]


class AllStarSide(FeedModel):
    """A side of an All-Star game. Never reaches a feed."""

    code: NonEmptyStr | None
    name: NonEmptyStr | None
    city: NonEmptyStr | None


class AllStarScoreboardGame(FeedModel):
    """An All-Star game as the scoreboard knows it. Never reaches a feed."""

    id: NonEmptyStr
    start_time: UtcDatetime
    status: GameStatus
    status_text: NonEmptyStr | None
    period: PositiveInt | None
    clock: NonEmptyStr | None
    score: Score | None
    note: NonEmptyStr | None
    venue: NonEmptyStr | None
    away: AllStarSide | None
    home: AllStarSide | None


def _is_an_all_star_event(event: _AllStarEvent) -> bool:
    if (event.season.type if event.season else None) != REGULAR_SEASON:
        return False
    if not event.competitions:
        return False
    kind = event.competitions[0].type
    return kind is not None and kind.abbreviation == COMPETITION_TYPE


def _side(team: _AllStarTeam) -> AllStarSide | None:
    code, name = team.abbreviation or None, team.name or None
    if code is None and name is None:
        return None
    return AllStarSide(code=code, name=name, city=None)


def _map_event(event: _AllStarEvent) -> AllStarScoreboardGame:
    competition = event.competitions[0]
    sides = {c.home_away: c for c in competition.competitors}
    if set(sides) != {"home", "away"} or len(competition.competitors) != 2:
        raise SourceError(SOURCE, f"game {event.id} needs one home and one away team")
    away, home = sides["away"], sides["home"]

    provider_status = event.status.type.name
    if provider_status not in STATUSES:
        raise SourceError(SOURCE, f"unknown game status {provider_status!r}")
    status = STATUSES[provider_status]
    in_play = status in (GameStatus.LIVE, GameStatus.FINAL)

    away_side, home_side = _side(away.team), _side(home.team)
    if in_play and (away_side is None or home_side is None):
        raise SourceError(
            SOURCE, f"game {event.id} is in play with a side with no team"
        )
    score: dict[str, str] | None = None
    if in_play:
        if away.score is None or home.score is None:
            raise SourceError(SOURCE, f"game {event.id} is in play with no score")
        score = {"away": away.score, "home": home.score}
    note = next((n.headline for n in competition.notes if n.headline), None)
    try:
        return AllStarScoreboardGame.model_validate(
            {
                "id": event.id,
                "start_time": event.date.astimezone(dt.UTC),
                "status": status,
                "status_text": event.status.type.short_detail or None,
                "period": (event.status.period or None) if in_play else None,
                "clock": (
                    _normalize_clock(event.status.display_clock)
                    if status is GameStatus.LIVE
                    else None
                ),
                "score": score,
                "note": note,
                "venue": competition.venue.full_name if competition.venue else None,
                "away": away_side,
                "home": home_side,
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {event.id} is invalid: {first['type']} at {location}"
        ) from None


async def fetch_all_star_games(
    client: SourceClient,
    day: dt.date,
    settings: Settings,
    fresh: Freshness = FRESH_FOR,
) -> list[AllStarScoreboardGame]:
    """Return the All-Star games of a US Eastern day in provider order, or raise
    SourceError."""
    if settings.scoreboard_url is None:
        raise SourceError(SOURCE, "scoreboard URL is not configured")
    url = settings.scoreboard_url.format(date=day.strftime(DATE_FORMAT))
    body = await get_json(client, url, source=SOURCE, fresh=fresh)
    try:
        scoreboard = _AllStarScoreboard.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
    return [_map_event(e) for e in scoreboard.events if _is_an_all_star_event(e)]
