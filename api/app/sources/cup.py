# api/app/sources/cup.py
#
# Cup adapter: fetches the teams of a Cup group and the Cup table of a Cup group
# or of a conference from the provider, and maps them to standard team codes and
# table rows in the provider's units and text forms (the builder converts them).
# A team is read from the provider team id in its link, never by following the
# link. The table is the standings item named "inseason"; a row needs its wins
# and losses and every other stat may be missing. The clinch letter maps to the
# Cup tag: y won the group, x is the wild card, e is eliminated; an absent code
# is null and an unknown one is null and logged with the team code. The group
# ids are fixed (the provider keeps them across seasons; the teams in a group
# change each season). The note of a game maps to its Cup round. The provider
# URLs come from Settings. Provider data never leaves this module.
#
# SEE: docs/api/cup.md, docs/adr/0028-cup-feed.md, api/app/sources/teams.py

import datetime as dt
import logging

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.cup import CupTag
from app.feeds.game_detail import Conference
from app.feeds.games import CupRound, FeedModel, TeamCode
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import team_code_of_id

SOURCE_TEAMS = "cup_group"
SOURCE_TABLE = "cup_group_standings"
FRESH_FOR = dt.timedelta(hours=1)
TABLE_NAME = "inseason"

# The provider's group ids. The Cup itself is group 21 and is not read.
GROUP_IDS: dict[tuple[Conference, str], int] = {
    (Conference.EAST, "A"): 22,
    (Conference.EAST, "B"): 23,
    (Conference.EAST, "C"): 24,
    (Conference.WEST, "A"): 25,
    (Conference.WEST, "B"): 26,
    (Conference.WEST, "C"): 27,
}
CONFERENCE_IDS: dict[Conference, int] = {Conference.EAST: 28, Conference.WEST: 29}

CUP_NOTES: dict[str, CupRound] = {
    "NBA Cup - Group Play": CupRound.GROUP,
    "NBA Cup - Quarterfinals": CupRound.QUARTERFINALS,
    "NBA Cup - Semifinals": CupRound.SEMIFINALS,
    "NBA Cup Championship": CupRound.CHAMPIONSHIP,
    # The first edition (2023-24) was the In-Season Tournament.
    "NBA In-Season Tournament - Group Play": CupRound.GROUP,
    "NBA In-Season Tournament - Quarterfinals": CupRound.QUARTERFINALS,
    "NBA In-Season Tournament - Semifinals": CupRound.SEMIFINALS,
    "NBA In-Season Tournament Championship": CupRound.CHAMPIONSHIP,
}
CLINCH_TAGS: dict[str, CupTag] = {
    "y": CupTag.WON_GROUP,
    "x": CupTag.WILD_CARD,
    "e": CupTag.ELIMINATED,
}

logger = logging.getLogger(__name__)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderRef(_ProviderModel):
    ref: str = Field(alias="$ref")


class _ProviderTeams(_ProviderModel):
    items: list[_ProviderRef]


class _ProviderStat(_ProviderModel):
    name: str
    value: float | None = None
    display_value: str | None = None


class _ProviderRecord(_ProviderModel):
    type: str
    display_value: str | None = None
    stats: list[_ProviderStat] = []


class _ProviderRow(_ProviderModel):
    team: _ProviderRef
    records: list[_ProviderRecord] = []


class _ProviderTable(_ProviderModel):
    name: str
    standings: list[_ProviderRow] = []


class CupTableRow(FeedModel):
    """One team's line of a Cup table. Text forms stay as the provider sends
    them. Never reaches a feed."""

    code: TeamCode
    wins: int
    losses: int
    position: int | None
    games_behind: str | None
    differential: float | None
    point_differential: float | None
    points_for: float | None
    points_against: float | None
    streak: str | None
    ot_wins: int | None
    ot_losses: int | None
    clincher: CupTag | None
    home: str | None
    road: str | None


class CupTable(FeedModel):
    """The rows of a Cup table in the provider's order. Never reaches a feed."""

    rows: list[CupTableRow]


_CUP_NOTES_ANY_CASE = {key.casefold(): value for key, value in CUP_NOTES.items()}


def cup_round(note: str | None) -> CupRound | None:
    """The Cup round of a game note, in any letter case; none for any other note."""
    return None if note is None else _CUP_NOTES_ANY_CASE.get(note.casefold())


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _team_id(ref: str, source: str) -> str:
    parts = httpx.URL(ref).path.rstrip("/").split("/")
    if "teams" not in parts[:-1]:
        raise SourceError(source, "team link has no team id")
    return parts[parts.index("teams") + 1]


def _group_id(conference: Conference, letter: str) -> int:
    try:
        return GROUP_IDS[(conference, letter)]
    except KeyError:
        raise SourceError(SOURCE_TEAMS, f"unknown group {letter!r}") from None


async def fetch_group_teams(
    client: SourceClient,
    season: int,
    conference: Conference,
    letter: str,
    settings: Settings,
) -> list[str]:
    """Return the team codes of one Cup group in the provider's order, or raise
    SourceError."""
    if not settings.cup_group_url:
        raise SourceError(SOURCE_TEAMS, "Cup group URL is not configured")
    url = settings.cup_group_url.format(
        season=season, group=_group_id(conference, letter)
    )
    body = await get_json(client, url, source=SOURCE_TEAMS, fresh=FRESH_FOR)
    try:
        provider = _ProviderTeams.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE_TEAMS,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    return [
        team_code_of_id(_team_id(item.ref, SOURCE_TEAMS), source=SOURCE_TEAMS)
        for item in provider.items
    ]


def _stat(record: _ProviderRecord, name: str) -> _ProviderStat | None:
    return next((stat for stat in record.stats if stat.name == name), None)


def _number(record: _ProviderRecord, name: str) -> float | None:
    stat = _stat(record, name)
    return None if stat is None else stat.value


def _text(record: _ProviderRecord, name: str) -> str | None:
    stat = _stat(record, name)
    if stat is None or stat.display_value in (None, ""):
        return None
    return stat.display_value


def _record_text(row: _ProviderRow, kind: str) -> str | None:
    record = next((r for r in row.records if r.type == kind), None)
    if record is None or record.display_value in (None, ""):
        return None
    return record.display_value


def _clincher(record: _ProviderRecord, code: str) -> CupTag | None:
    text = _text(record, "clincher")
    if text is None:
        return None
    tag = CLINCH_TAGS.get(text)
    if tag is None:
        logger.warning("cup table: team %s has an unknown clinch code %r", code, text)
    return tag


def _whole(value: float | None) -> int | None:
    return None if value is None else int(value)


def _row(row: _ProviderRow) -> dict[str, object]:
    code = team_code_of_id(_team_id(row.team.ref, SOURCE_TABLE), source=SOURCE_TABLE)
    record = next((r for r in row.records if r.type == TABLE_NAME), None)
    if record is None:
        raise SourceError(SOURCE_TABLE, f"team {code} has no {TABLE_NAME} record")
    wins = _number(record, "wins")
    losses = _number(record, "losses")
    if wins is None or losses is None:
        raise SourceError(SOURCE_TABLE, f"team {code} has no wins or losses stat")
    return {
        "code": code,
        "wins": int(wins),
        "losses": int(losses),
        "position": _whole(_number(record, "playoffSeed")),
        "games_behind": _text(record, "gamesBehind"),
        "differential": _number(record, "differential"),
        "point_differential": _number(record, "pointDifferential"),
        "points_for": _number(record, "pointsFor"),
        "points_against": _number(record, "pointsAgainst"),
        "streak": _text(record, "streak"),
        "ot_wins": _whole(_number(record, "OTWins")),
        "ot_losses": _whole(_number(record, "OTLosses")),
        "clincher": _clincher(record, code),
        "home": _record_text(row, "home"),
        "road": _record_text(row, "road"),
    }


async def _table(
    client: SourceClient, season: int, group_id: int, settings: Settings
) -> CupTable:
    if not settings.cup_group_standings_url:
        raise SourceError(SOURCE_TABLE, "Cup table URL is not configured")
    url = settings.cup_group_standings_url.format(season=season, group=group_id)
    body = await get_json(client, url, source=SOURCE_TABLE, fresh=FRESH_FOR)
    try:
        provider = _ProviderTable.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE_TABLE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    if provider.name != TABLE_NAME:
        raise SourceError(SOURCE_TABLE, "table is not the Cup table")
    try:
        return CupTable.model_validate(
            {"rows": [_row(row) for row in provider.standings]}
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE_TABLE, f"table is invalid: {first['type']} at {_location(error)}"
        ) from None


async def fetch_group_table(
    client: SourceClient,
    season: int,
    conference: Conference,
    letter: str,
    settings: Settings,
) -> CupTable:
    """Return the Cup table of one group, or raise SourceError."""
    return await _table(client, season, _group_id(conference, letter), settings)


async def fetch_conference_table(
    client: SourceClient, season: int, conference: Conference, settings: Settings
) -> CupTable:
    """Return the Cup table of one conference, in seeding order, or raise
    SourceError."""
    return await _table(client, season, CONFERENCE_IDS[conference], settings)
