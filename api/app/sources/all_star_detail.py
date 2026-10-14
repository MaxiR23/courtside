# api/app/sources/all_star_detail.py
#
# All-Star view of the game detail (ADR 0036). Reads the same game from the same
# URL with the freshness the caller passes, so it shares one cached response with
# app.sources.game_detail. It maps what the core adapter does not carry: the
# regulation format (periods and seconds), the attendance, the TV and streaming
# broadcasts and the jersey and position of each box score player, by player id.
# Everything beyond the format is read leniently by key: a missing key only
# leaves that field null or empty, and a broadcast of another type or with no
# name is skipped. A value of the wrong type fails the whole extras read, which
# the feed turns into null extras for that game. An attendance of zero is no attendance. Its results never
# reach a core feed, and removing the All-Star section removes this module.
# Provider data never leaves this module.
#
# SEE: docs/api/all-star.md, docs/adr/0036-all-star-feed.md,
# api/app/sources/finals_plays.py

from pydantic import Field, PositiveFloat, PositiveInt, ValidationError

from app.feeds.all_star import Broadcast, BroadcastKind
from app.feeds.games import FeedModel, NonEmptyStr
from app.settings import Settings
from app.sources.game_detail import SOURCE, _ProviderModel, _SummaryFormat
from app.sources.http import Freshness, SourceClient, SourceError, get_json

BROADCAST_KINDS = {"tv": BroadcastKind.TV, "streaming": BroadcastKind.STREAMING}


class _ExtrasPosition(_ProviderModel):
    abbreviation: str | None = None


class _ExtrasAthlete(_ProviderModel):
    id: str
    jersey: str | None = None
    position: _ExtrasPosition | None = None


class _ExtrasLine(_ProviderModel):
    athlete: _ExtrasAthlete


class _ExtrasGroup(_ProviderModel):
    athletes: list[_ExtrasLine] = Field(default_factory=list)


class _ExtrasTeamPlayers(_ProviderModel):
    statistics: list[_ExtrasGroup] = Field(default_factory=list)


class _ExtrasBoxscore(_ProviderModel):
    players: list[_ExtrasTeamPlayers] = Field(default_factory=list)


class _ExtrasGameInfo(_ProviderModel):
    attendance: int | None = None


class _ExtrasName(_ProviderModel):
    short_name: str | None = None


class _ExtrasBroadcast(_ProviderModel):
    type: _ExtrasName | None = None
    media: _ExtrasName | None = None


class _ExtrasSummary(_ProviderModel):
    format: _SummaryFormat | None = None
    game_info: _ExtrasGameInfo | None = None
    broadcasts: list[_ExtrasBroadcast] = Field(default_factory=list)
    boxscore: _ExtrasBoxscore | None = None


class AllStarDetailExtras(FeedModel):
    """What the All-Star feed reads of a game detail beyond the core adapter.
    Never reaches a feed."""

    regulation_periods: PositiveInt | None
    regulation_seconds: PositiveFloat | None
    attendance: int | None
    broadcasts: list[Broadcast]
    jerseys: dict[str, NonEmptyStr]
    positions: dict[str, NonEmptyStr]


def _broadcasts(summary: _ExtrasSummary) -> list[Broadcast]:
    found: list[Broadcast] = []
    for entry in summary.broadcasts:
        kind = BROADCAST_KINDS.get(
            ((entry.type.short_name if entry.type else None) or "").casefold()
        )
        name = (entry.media.short_name if entry.media else None) or None
        if kind is None or name is None:
            continue
        found.append(Broadcast(name=name, kind=kind))
    return found


async def fetch_all_star_extras(
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> AllStarDetailExtras:
    """Return the format, attendance, broadcasts, jerseys and positions of one
    game, or raise SourceError."""
    if settings.game_detail_url is None:
        raise SourceError(SOURCE, "game detail URL is not configured")
    url = settings.game_detail_url.format(game_id=game_id)
    body = await get_json(client, url, source=SOURCE, fresh=fresh)
    try:
        summary = _ExtrasSummary.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
    jerseys: dict[str, str] = {}
    positions: dict[str, str] = {}
    for team in summary.boxscore.players if summary.boxscore else []:
        for group in team.statistics[:1]:
            for line in group.athletes:
                athlete = line.athlete
                if athlete.jersey:
                    jerseys[athlete.id] = athlete.jersey
                if athlete.position and athlete.position.abbreviation:
                    positions[athlete.id] = athlete.position.abbreviation
    attendance = summary.game_info.attendance if summary.game_info else None
    regulation = summary.format.regulation if summary.format else None
    return AllStarDetailExtras(
        regulation_periods=regulation.periods if regulation else None,
        regulation_seconds=regulation.clock
        if regulation and regulation.clock > 0
        else None,
        attendance=attendance if attendance is not None and attendance > 0 else None,
        broadcasts=_broadcasts(summary),
        jerseys=jerseys,
        positions=positions,
    )
