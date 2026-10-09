# api/app/sources/teams.py
#
# The tables that map the provider's team codes and team ids to the standard codes.
#
# SEE: docs/api/games.md, api/app/sources/http.py

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
