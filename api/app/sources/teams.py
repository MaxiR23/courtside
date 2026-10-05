# api/app/sources/teams.py
#
# The one table that maps the provider's team codes to the standard codes.
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


def to_team_code(provider_code: str, *, source: str) -> str:
    """Return the standard code of a provider team code, or raise SourceError."""
    try:
        return TEAM_CODES[provider_code]
    except KeyError:
        raise SourceError(source, f"unknown team code {provider_code!r}") from None
