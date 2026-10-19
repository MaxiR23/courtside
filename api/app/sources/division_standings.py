# api/app/sources/division_standings.py
#
# Division standings adapter: fetches the regular season standings by
# conference and division from the provider and maps each team to its record,
# splits, seed, streak, games behind and points, in the provider's units and
# text forms (the builders convert them). The entry order of the provider is
# kept: the order of a team inside its division, inside its conference and in
# the whole league (provider_order, which also orders the divisions). The
# URL is requested as configured; a response that is not of the regular season
# is replaced by one request for the regular season through the season query
# value (a preseason of Y reads Y - 1, a postseason of Y reads Y), per rule L.
# The division and conference records and the clinch code are mapped too: a
# missing record is 0-0 and an absent or unknown clinch code is null (an
# unknown one is logged with the team code). The result tells whether it came
# from the rule L second request (fallback). Every stat but wins and losses may
# be null (the last ten and the division and conference records are 0-0); an
# entry without wins or losses is skipped with a log line by team code
# (ADR 0064). The provider URL comes from Settings. Provider data never leaves
# this module. A past season is read once with its season query value, with no
# rule L fallback, and teams are resolved by provider id first.
#
# SEE: docs/api/team.md, docs/api/standings.md, docs/source-rules.md,
# api/app/sources/standings.py,
# docs/adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md

import datetime as dt
import logging

from pydantic import (
    BaseModel,
    ConfigDict,
    PositiveInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import Conference
from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.feeds.standings import Clinch
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json, with_query
from app.sources.teams import TEAM_CODES, TEAM_IDS, to_team_code

SOURCE = "division_standings"
FRESH_FOR = dt.timedelta(hours=1)
PRESEASON = 1
REGULAR_SEASON = 2
POSTSEASON = 3
# Offset added to the season of a response to read its regular season.
REGULAR_SEASON_OF = {PRESEASON: -1, POSTSEASON: 0}
CONFERENCES = {"East": Conference.EAST, "West": Conference.WEST}
# The provider sends no last ten, division or conference record before a team's
# first game.
NO_RECORD = "0-0"
CLINCH_CODES = {clinch.value: clinch for clinch in Clinch}

logger = logging.getLogger(__name__)


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeam(_ProviderModel):
    id: str | None = None
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
    season: int
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
    provider sends them: "W2", "30-11", "-". An empty streak, games behind or
    seed is null. Never reaches a feed."""

    code: TeamCode
    location: NonEmptyStr
    name: NonEmptyStr
    # The provider's abbreviation, as the payload names the team (ADR 0058).
    abbreviation: NonEmptyStr | None = None
    display_name: NonEmptyStr
    conference: Conference
    division: NonEmptyStr
    division_order: PositiveInt
    conference_order: PositiveInt
    provider_order: PositiveInt
    wins: int
    losses: int
    playoff_seed: int | None
    streak: str | None
    games_behind: str | None
    home: str | None
    road: str | None
    last_ten: str
    avg_points_for: float | None
    avg_points_against: float | None
    points_for: float | None
    points_against: float | None
    differential: float | None
    point_differential: float | None
    vs_division: str
    vs_conference: str
    clinch: Clinch | None


class DivisionStandings(FeedModel):
    """The regular season standings of every team, by team code. The season is
    the end year of the standings: 2026 is 2025-26."""

    season: PositiveInt
    fallback: bool
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


def _optional_number(stats: dict[str, _ProviderStat], key: str) -> float | None:
    stat = stats.get(key)
    return None if stat is None else stat.value


def _optional_text(stats: dict[str, _ProviderStat], key: str) -> str | None:
    stat = stats.get(key)
    if stat is None or stat.display_value in (None, ""):
        return None
    return stat.display_value


def _clinch(stats: dict[str, _ProviderStat], code: str) -> Clinch | None:
    text = _optional_text(stats, "clincher")
    if text is None:
        return None
    clinch = CLINCH_CODES.get(text)
    if clinch is None:
        logger.warning(
            "division standings: team %s has an unknown clinch code %r", code, text
        )
    return clinch


def _code(entry: _ProviderEntry, by_id_first: bool) -> str:
    team_id = entry.team.id
    if by_id_first and team_id is not None and team_id in TEAM_IDS:
        return TEAM_CODES[TEAM_IDS[team_id]]
    return to_team_code(entry.team.abbreviation, source=SOURCE)


def _entry(
    entry: _ProviderEntry,
    conference: Conference,
    division: str,
    division_order: int,
    conference_order: int,
    provider_order: int,
    code: str,
) -> dict[str, object]:
    stats = {stat.type: stat for stat in entry.stats}
    seed = _optional_number(stats, "playoffseed")
    return {
        "code": code,
        "location": entry.team.location,
        "name": entry.team.name,
        "abbreviation": entry.team.abbreviation or None,
        "display_name": entry.team.display_name,
        "conference": conference,
        "division": division,
        "division_order": division_order,
        "conference_order": conference_order,
        "provider_order": provider_order,
        "wins": int(_number(stats, "wins", code)),
        "losses": int(_number(stats, "losses", code)),
        "playoff_seed": None if seed is None else int(seed),
        "streak": _optional_text(stats, "streak"),
        "games_behind": _optional_text(stats, "gamesbehind"),
        "home": _optional_text(stats, "home"),
        "road": _optional_text(stats, "road"),
        "last_ten": _text(stats, "lasttengames", code, NO_RECORD),
        "avg_points_for": _optional_number(stats, "avgpointsfor"),
        "avg_points_against": _optional_number(stats, "avgpointsagainst"),
        "points_for": _optional_number(stats, "pointsfor"),
        "points_against": _optional_number(stats, "pointsagainst"),
        "differential": _optional_number(stats, "differential"),
        "point_differential": _optional_number(stats, "pointdifferential"),
        "vs_division": _text(stats, "vsdiv", code, NO_RECORD),
        "vs_conference": _text(stats, "vsconf", code, NO_RECORD),
        "clinch": _clinch(stats, code),
    }


async def _read(client: SourceClient, url: str) -> _ProviderLeague:
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        return _ProviderLeague.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None


def _season(provider: _ProviderLeague) -> tuple[int, int]:
    """The (season, season type) shared by every division."""
    found = {
        (division.standings.season, division.standings.season_type)
        for conference in provider.children
        for division in conference.children
    }
    if not found:
        raise SourceError(SOURCE, "standings have no divisions")
    if len(found) > 1:
        raise SourceError(SOURCE, "standings mix seasons")
    return next(iter(found))


async def fetch_division_standings(
    client: SourceClient, settings: Settings, *, season: int | None = None
) -> DivisionStandings:
    """Return the regular season standings of every team, or raise SourceError.

    With a season (the end year), read that past regular season once: no rule L
    fallback, and each team resolved by provider id first (ADR 0043)."""
    if settings.division_standings_url is None:
        raise SourceError(SOURCE, "division standings URL is not configured")
    requested = season
    past = season is not None
    if season is None:
        provider = await _read(client, settings.division_standings_url)
    else:
        provider = await _read(
            client, with_query(settings.division_standings_url, {"season": season})
        )
    season, season_type = _season(provider)
    fallback = False
    if past:
        if (season, season_type) != (requested, REGULAR_SEASON):
            raise SourceError(
                SOURCE, "standings are not of the requested regular season"
            )
    elif season_type != REGULAR_SEASON:
        offset = REGULAR_SEASON_OF.get(season_type)
        if offset is None:
            raise SourceError(SOURCE, "standings are not of the regular season")
        provider = await _read(
            client,
            with_query(settings.division_standings_url, {"season": season + offset}),
        )
        season, season_type = _season(provider)
        if season_type != REGULAR_SEASON:
            raise SourceError(SOURCE, "standings are not of the regular season")
        fallback = True

    teams: dict[str, dict[str, object]] = {}
    seen: set[Conference] = set()
    provider_order = 0
    for provider_conference in provider.children:
        conference = CONFERENCES.get(provider_conference.abbreviation)
        if conference is None:
            raise SourceError(
                SOURCE, f"unknown conference {provider_conference.abbreviation!r}"
            )
        seen.add(conference)
        conference_order = 0
        for division in provider_conference.children:
            for division_order, entry in enumerate(division.standings.entries, 1):
                conference_order += 1
                provider_order += 1
                code = _code(entry, past)
                try:
                    mapped = _entry(
                        entry,
                        conference,
                        division.name,
                        division_order,
                        conference_order,
                        provider_order,
                        code,
                    )
                except SourceError as error:
                    logger.warning(
                        "division standings: team %s skipped: %s", code, error.reason
                    )
                    continue
                teams[str(mapped["code"])] = mapped
    if seen != set(Conference):
        raise SourceError(SOURCE, "standings do not have both conferences")

    try:
        return DivisionStandings.model_validate(
            {"season": season, "fallback": fallback, "teams": teams}
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE, f"standings are invalid: {first['type']} at {_location(error)}"
        ) from None
