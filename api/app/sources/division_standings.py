# api/app/sources/division_standings.py
#
# Division standings adapter: fetches the regular season standings by
# conference and division from the provider and maps each team to its record,
# splits, seed, streak, games behind and points, in the provider's units and
# text forms (the builders convert them). The entry order of the provider is
# kept: the order of a team inside its division and inside its conference. The
# URL is requested as configured, its own query selects the regular season; the
# adapter rejects any other season type. The provider URL comes from Settings.
# Provider data never leaves this module.
#
# SEE: docs/api/team.md, api/app/sources/standings.py

import datetime as dt

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import Conference
from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import to_team_code

SOURCE = "division_standings"
FRESH_FOR = dt.timedelta(hours=1)
REGULAR_SEASON = 2
CONFERENCES = {"East": Conference.EAST, "West": Conference.WEST}
# The provider sends no last ten record before a team's first game.
NO_LAST_TEN = "0-0"


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeam(_ProviderModel):
    abbreviation: str
    location: str
    name: str
    display_name: str


class _ProviderStat(_ProviderModel):
    type: str
    value: float | None = None
    display_value: str | None = None


class _ProviderEntry(_ProviderModel):
    team: _ProviderTeam
    stats: list[_ProviderStat]


class _ProviderStandings(_ProviderModel):
    season_type: int
    entries: list[_ProviderEntry]


class _ProviderDivision(_ProviderModel):
    name: str
    standings: _ProviderStandings


class _ProviderConference(_ProviderModel):
    abbreviation: str
    children: list[_ProviderDivision]


class _ProviderLeague(_ProviderModel):
    children: list[_ProviderConference]


class DivisionEntry(FeedModel):
    """One team's line of the division standings. Text forms stay as the
    provider sends them: "W2", "30-11", "-". Never reaches a feed."""

    code: TeamCode
    location: NonEmptyStr
    name: NonEmptyStr
    display_name: NonEmptyStr
    conference: Conference
    division: NonEmptyStr
    division_order: PositiveInt
    conference_order: PositiveInt
    wins: int
    losses: int
    playoff_seed: int
    streak: str
    games_behind: str
    home: str
    road: str
    last_ten: str
    avg_points_for: float
    avg_points_against: float
    points_for: float
    points_against: float
    differential: float
    point_differential: float


class DivisionStandings(FeedModel):
    """The regular season standings of every team, by team code."""

    teams: dict[TeamCode, DivisionEntry]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _number(stats: dict[str, _ProviderStat], key: str, code: str) -> float:
    stat = stats.get(key)
    if stat is None or stat.value is None:
        raise SourceError(SOURCE, f"team {code} has no {key} stat")
    return stat.value


def _text(
    stats: dict[str, _ProviderStat], key: str, code: str, default: str | None = None
) -> str:
    stat = stats.get(key)
    if stat is None or stat.display_value is None:
        if default is not None:
            return default
        raise SourceError(SOURCE, f"team {code} has no {key} stat")
    return stat.display_value


def _entry(
    entry: _ProviderEntry,
    conference: Conference,
    division: str,
    division_order: int,
    conference_order: int,
) -> dict[str, object]:
    code = to_team_code(entry.team.abbreviation, source=SOURCE)
    stats = {stat.type: stat for stat in entry.stats}
    return {
        "code": code,
        "location": entry.team.location,
        "name": entry.team.name,
        "display_name": entry.team.display_name,
        "conference": conference,
        "division": division,
        "division_order": division_order,
        "conference_order": conference_order,
        "wins": int(_number(stats, "wins", code)),
        "losses": int(_number(stats, "losses", code)),
        "playoff_seed": int(_number(stats, "playoffseed", code)),
        "streak": _text(stats, "streak", code),
        "games_behind": _text(stats, "gamesbehind", code),
        "home": _text(stats, "home", code),
        "road": _text(stats, "road", code),
        "last_ten": _text(stats, "lasttengames", code, NO_LAST_TEN),
        "avg_points_for": _number(stats, "avgpointsfor", code),
        "avg_points_against": _number(stats, "avgpointsagainst", code),
        "points_for": _number(stats, "pointsfor", code),
        "points_against": _number(stats, "pointsagainst", code),
        "differential": _number(stats, "differential", code),
        "point_differential": _number(stats, "pointdifferential", code),
    }


async def fetch_division_standings(
    client: SourceClient, settings: Settings
) -> DivisionStandings:
    """Return the regular season standings of every team, or raise SourceError."""
    if settings.division_standings_url is None:
        raise SourceError(SOURCE, "division standings URL is not configured")
    body = await get_json(
        client, settings.division_standings_url, source=SOURCE, fresh=FRESH_FOR
    )
    try:
        provider = _ProviderLeague.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None

    teams: dict[str, dict[str, object]] = {}
    seen: set[Conference] = set()
    for provider_conference in provider.children:
        conference = CONFERENCES.get(provider_conference.abbreviation)
        if conference is None:
            raise SourceError(
                SOURCE, f"unknown conference {provider_conference.abbreviation!r}"
            )
        seen.add(conference)
        conference_order = 0
        for division in provider_conference.children:
            if division.standings.season_type != REGULAR_SEASON:
                raise SourceError(SOURCE, "standings are not of the regular season")
            for division_order, entry in enumerate(division.standings.entries, 1):
                conference_order += 1
                mapped = _entry(
                    entry, conference, division.name, division_order, conference_order
                )
                teams[str(mapped["code"])] = mapped
    if seen != set(Conference):
        raise SourceError(SOURCE, "standings do not have both conferences")

    try:
        return DivisionStandings.model_validate({"teams": teams})
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE, f"standings are invalid: {first['type']} at {_location(error)}"
        ) from None
