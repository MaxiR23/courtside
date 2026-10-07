# api/tests/sources/test_teams.py
#
# Tests for the team code mapping.
#
# Tested:
# - Every provider team code maps to a standard code
# - The 30 standard codes are each reached exactly once
# - An unknown provider code raises the source error
# - Every recorded provider team id maps to its team's standard code
# - An unknown provider team id raises the source error
#
# What is covered:
# - Happy path for all 30 teams, edge case of the codes that differ, error case of an unknown code
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_teams.py
#
# SEE: api/app/sources/teams.py

import pytest
from pydantic import TypeAdapter

from app.feeds.games import TeamCode
from app.sources.http import SourceError
from app.sources.teams import TEAM_CODES, TEAM_IDS, team_code_of_id, to_team_code

# The provider's teams list, as recorded: provider code and the standard code.
RECORDED_TEAMS = {
    "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "CHA": "CHA", "CHI": "CHI",
    "CLE": "CLE", "DAL": "DAL", "DEN": "DEN", "DET": "DET", "GS": "GSW",
    "HOU": "HOU", "IND": "IND", "LAC": "LAC", "LAL": "LAL", "MEM": "MEM",
    "MIA": "MIA", "MIL": "MIL", "MIN": "MIN", "NO": "NOP", "NY": "NYK",
    "OKC": "OKC", "ORL": "ORL", "PHI": "PHI", "PHX": "PHX", "POR": "POR",
    "SAC": "SAC", "SA": "SAS", "TOR": "TOR", "UTAH": "UTA", "WSH": "WAS",
}  # fmt: skip

# The provider's team ids, as recorded in the standings: id and provider code.
RECORDED_TEAM_IDS = {
    "1": "ATL", "2": "BOS", "3": "NO", "4": "CHI", "5": "CLE",
    "6": "DAL", "7": "DEN", "8": "DET", "9": "GS", "10": "HOU",
    "11": "IND", "12": "LAC", "13": "LAL", "14": "MIA", "15": "MIL",
    "16": "MIN", "17": "BKN", "18": "NY", "19": "ORL", "20": "PHI",
    "21": "PHX", "22": "POR", "23": "SAC", "24": "SA", "25": "OKC",
    "26": "UTAH", "27": "WSH", "28": "TOR", "29": "MEM", "30": "CHA",
}  # fmt: skip


def test_maps_every_provider_code_to_a_standard_code() -> None:
    for provider_code, standard_code in RECORDED_TEAMS.items():
        assert to_team_code(provider_code, source="test") == standard_code


def test_the_table_has_exactly_the_recorded_codes() -> None:
    assert TEAM_CODES == RECORDED_TEAMS


def test_reaches_each_of_the_30_standard_codes_once() -> None:
    values = list(TEAM_CODES.values())

    assert len(values) == 30
    assert len(set(values)) == 30
    for code in values:
        TypeAdapter(TeamCode).validate_python(code)


def test_maps_the_codes_that_differ() -> None:
    assert to_team_code("UTAH", source="test") == "UTA"
    assert to_team_code("WSH", source="test") == "WAS"


@pytest.mark.parametrize("code", ["ZZZ", "", "gs", "GSW"])
def test_raises_the_source_error_on_an_unknown_code(code: str) -> None:
    with pytest.raises(SourceError) as raised:
        to_team_code(code, source="test")

    assert raised.value.reason == f"unknown team code {code!r}"


def test_the_id_table_has_exactly_the_recorded_ids() -> None:
    assert TEAM_IDS == RECORDED_TEAM_IDS


def test_every_team_id_reaches_one_of_the_30_standard_codes_once() -> None:
    codes = {team_code_of_id(i, source="test") for i in RECORDED_TEAM_IDS}

    assert len(codes) == 30
    assert codes == set(TEAM_CODES.values())


def test_maps_team_ids_of_codes_that_differ() -> None:
    assert team_code_of_id("9", source="test") == "GSW"
    assert team_code_of_id("26", source="test") == "UTA"
    assert team_code_of_id("27", source="test") == "WAS"


@pytest.mark.parametrize("provider_id", ["0", "31", "", "GS"])
def test_raises_the_source_error_on_an_unknown_team_id(provider_id: str) -> None:
    with pytest.raises(SourceError) as raised:
        team_code_of_id(provider_id, source="test")

    assert raised.value.reason == f"unknown team id {provider_id!r}"
