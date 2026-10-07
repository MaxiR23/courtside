# api/app/sources/standings.py
#
# Standings adapter: fetches the standings of both conferences from the
# provider and maps each team to the contract's standing: conference, rank and
# the overall, home, away and last ten records. The provider URL comes from
# Settings. A team that has played no game has no last ten stat and gets 0-0.
# Provider data never leaves this module.
#
# SEE: docs/api/game-detail.md, api/app/sources/team_players.py

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import Conference, TeamStanding
from app.feeds.games import FeedModel, TeamCode
from app.settings import Settings
from app.sources.http import SourceError, get_json
from app.sources.teams import to_team_code

SOURCE = "standings"
CONFERENCES = {"East": Conference.EAST, "West": Conference.WEST}
RECORDS = {
    "record": "total",
    "home_record": "home",
    "away_record": "road",
    "last_ten": "lasttengames",
}
NO_GAMES = {"wins": 0, "losses": 0}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeam(_ProviderModel):
    abbreviation: str


class _ProviderStat(_ProviderModel):
    type: str | None = None
    value: float | None = None
    display_value: str | None = None


class _ProviderEntry(_ProviderModel):
    team: _ProviderTeam
    stats: list[_ProviderStat]


class _ProviderStandings(_ProviderModel):
    entries: list[_ProviderEntry]


class _ProviderConference(_ProviderModel):
    abbreviation: str
    standings: _ProviderStandings


class _ProviderLeague(_ProviderModel):
    children: list[_ProviderConference]


class LeagueStandings(FeedModel):
    """The standing of every team by standard team code. Never reaches the feed."""

    teams: dict[TeamCode, TeamStanding]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _record(code: str, stats: dict[str, _ProviderStat], kind: str) -> dict[str, int]:
    if kind not in stats:
        raise SourceError(SOURCE, f"team {code} has no {kind} stat")
    wins, separator, losses = (stats[kind].display_value or "").partition("-")
    if not separator or not wins.isdecimal() or not losses.isdecimal():
        raise SourceError(SOURCE, f"team {code} has a record that is not W-L")
    return {"wins": int(wins), "losses": int(losses)}


def _standing(
    code: str, conference: Conference, entry: _ProviderEntry
) -> dict[str, object]:
    stats = {stat.type: stat for stat in entry.stats if stat.type is not None}
    if "playoffseed" not in stats or stats["playoffseed"].value is None:
        raise SourceError(SOURCE, f"team {code} has no playoffseed stat")
    standing: dict[str, object] = {
        "conference": conference,
        "conference_rank": int(stats["playoffseed"].value),
    }
    for field, kind in RECORDS.items():
        if field == "last_ten" and kind not in stats and standing["record"] == NO_GAMES:
            # The provider omits it before a team's first game.
            standing[field] = dict(NO_GAMES)
        else:
            standing[field] = _record(code, stats, kind)
    return standing


async def fetch_standings(
    client: httpx.AsyncClient, settings: Settings
) -> LeagueStandings:
    """Return the standing of every team, or raise SourceError."""
    if settings.standings_url is None:
        raise SourceError(SOURCE, "standings URL is not configured")
    body = await get_json(client, settings.standings_url, source=SOURCE)
    try:
        provider = _ProviderLeague.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None

    teams: dict[str, object] = {}
    seen: set[Conference] = set()
    for child in provider.children:
        conference = CONFERENCES.get(child.abbreviation)
        if conference is None:
            raise SourceError(SOURCE, f"unknown conference {child.abbreviation!r}")
        seen.add(conference)
        for entry in child.standings.entries:
            code = to_team_code(entry.team.abbreviation, source=SOURCE)
            teams[code] = _standing(code, conference, entry)
    if seen != set(CONFERENCES.values()):
        raise SourceError(SOURCE, "standings need both conferences")

    try:
        return LeagueStandings.model_validate({"teams": teams})
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE, f"standings are invalid: {first['type']} at {_location(error)}"
        ) from None
