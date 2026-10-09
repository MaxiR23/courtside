# api/app/sources/teams.py
#
# The tables that map the provider's team codes and team ids to the standard codes,
# and the one resolver that maps a side or an opponent for every adapter (ADR 0026).
#
# SEE: docs/api/games.md, api/app/sources/http.py

from typing import Any

from app.sources.http import SourceError

TEAM_CODES: dict[str, str] = {
    "ATL": "ATL",
    "BOS": "BOS",
    "BKN": "BKN",
    "CHA": "CHA",
    "CHI": "CHI",
    "CLE": "CLE",
    "DAL": "DAL",
    "DEN": "DEN",
    "DET": "DET",
    "GS": "GSW",
    "HOU": "HOU",
    "IND": "IND",
    "LAC": "LAC",
    "LAL": "LAL",
    "MEM": "MEM",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NO": "NOP",
    "NY": "NYK",
    "OKC": "OKC",
    "ORL": "ORL",
    "PHI": "PHI",
    "PHX": "PHX",
    "POR": "POR",
    "SAC": "SAC",
    "SA": "SAS",
    "TOR": "TOR",
    "UTAH": "UTA",
    "WSH": "WAS",
}

# The provider's team id of each provider team code.
TEAM_IDS: dict[str, str] = {
    "1": "ATL",
    "2": "BOS",
    "3": "NO",
    "4": "CHI",
    "5": "CLE",
    "6": "DAL",
    "7": "DEN",
    "8": "DET",
    "9": "GS",
    "10": "HOU",
    "11": "IND",
    "12": "LAC",
    "13": "LAL",
    "14": "MIA",
    "15": "MIL",
    "16": "MIN",
    "17": "BKN",
    "18": "NY",
    "19": "ORL",
    "20": "PHI",
    "21": "PHX",
    "22": "POR",
    "23": "SAC",
    "24": "SA",
    "25": "OKC",
    "26": "UTAH",
    "27": "WSH",
    "28": "TOR",
    "29": "MEM",
    "30": "CHA",
}


def to_team_code(provider_code: str, *, source: str) -> str:
    """Return the standard code of a provider team code, or raise SourceError."""
    try:
        return TEAM_CODES[provider_code]
    except KeyError:
        raise SourceError(source, f"unknown team code {provider_code!r}") from None


LEAGUE_CODES = frozenset(TEAM_CODES.values())


def to_side(provider_code: str, *, source: str) -> tuple[str, bool]:
    """Return the standard code and False for one of the 30 teams, or the
    provider's own code and True for a guest team.

    Raises SourceError for a provider code that is not a league key but equals
    a league standard code.
    """
    if provider_code in TEAM_CODES:
        return TEAM_CODES[provider_code], False
    if provider_code in LEAGUE_CODES:
        raise SourceError(
            source, f"guest team code {provider_code!r} is a league team code"
        )
    return provider_code, True


def team_code_of_id(provider_id: str, *, source: str) -> str:
    """Return the standard code of a provider team id, or raise SourceError."""
    try:
        return TEAM_CODES[TEAM_IDS[provider_id]]
    except KeyError:
        raise SourceError(source, f"unknown team id {provider_id!r}") from None


def side_of(
    abbreviation: str | None, team_id: str | None, *, source: str
) -> tuple[str | None, bool]:
    """Return the code and guest flag of a provider team: by abbreviation
    (to_side), else a league team by its provider id, else a guest without a code.

    An empty abbreviation or id counts as absent.
    """
    if abbreviation:
        return to_side(abbreviation, source=source)
    if team_id and team_id in TEAM_IDS:
        return TEAM_CODES[TEAM_IDS[team_id]], False
    return None, True


def to_opponent(
    abbreviation: str | None,
    team_id: str | None,
    name: str | None,
    location: str | None,
    *,
    source: str,
) -> dict[str, Any] | None:
    """Return the Opponent fields of a provider team, or None when it has neither
    a code nor a name: the caller skips that game (ADR 0026)."""
    code, guest = side_of(abbreviation, team_id, source=source)
    name = name or None
    if code is None and name is None:
        return None
    return {"code": code, "name": name, "city": location or None, "guest": guest}
