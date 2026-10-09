# api/tests/feeds/test_opponent.py
#
# Tests for the shared side and opponent model.
#
# Tested:
# - A league opponent has a code of three capital letters and may have no name or city
# - A guest has a name and city and may have no code
# - A guest code may be any non-empty string
# - A league opponent without a code or with a lowercase code is rejected
# - A guest with neither a code nor a name is rejected
# - Side is away or home
#
# What is covered:
# - A valid opponent is accepted and an invalid one is rejected
#
# Run with: cd api && .venv/bin/python -m pytest tests/feeds/test_opponent.py
#
# SEE: api/app/feeds/opponent.py

from typing import Any

import pytest
from pydantic import ValidationError

from app.feeds.opponent import Opponent, Side

Payload = dict[str, Any]


def league(**overrides: object) -> Payload:
    return {"code": "DEN", "name": None, "city": None, "guest": False, **overrides}


def guest(**overrides: object) -> Payload:
    return {
        "code": None,
        "name": "Mariners",
        "city": "Harbor City",
        "guest": True,
        **overrides,
    }


def test_accepts_a_league_opponent_with_its_code_and_a_null_name_and_city() -> None:
    opponent = Opponent.model_validate(league())

    assert opponent.code == "DEN"
    assert opponent.name is None and opponent.city is None


def test_accepts_a_guest_with_a_name_and_city_and_a_null_code() -> None:
    opponent = Opponent.model_validate(guest())

    assert opponent.code is None
    assert opponent.guest


@pytest.mark.parametrize("code", ["H", "hcm", "TOOLONG1", "HC M"])
def test_accepts_a_guest_with_a_code_outside_the_usual_pattern(code: str) -> None:
    assert Opponent.model_validate(guest(code=code)).code == code


def test_accepts_a_guest_with_a_code_and_no_name() -> None:
    Opponent.model_validate(guest(code="HCM", name=None, city=None))


def test_a_team_is_a_league_team_unless_it_says_it_is_a_guest() -> None:
    opponent = Opponent.model_validate({"code": "DEN", "name": None, "city": None})

    assert opponent.guest is False


def test_rejects_a_league_opponent_without_a_code() -> None:
    with pytest.raises(ValidationError, match="three capital letters"):
        Opponent.model_validate(league(code=None))


def test_rejects_a_league_opponent_with_a_lowercase_code() -> None:
    with pytest.raises(ValidationError, match="three capital letters"):
        Opponent.model_validate(league(code="den"))


def test_rejects_a_guest_with_neither_a_code_nor_a_name() -> None:
    with pytest.raises(ValidationError, match="a code or a name"):
        Opponent.model_validate(guest(name=None, city=None))


def test_rejects_an_empty_name() -> None:
    with pytest.raises(ValidationError, match="name"):
        Opponent.model_validate(guest(name=""))


def test_rejects_an_unknown_field() -> None:
    with pytest.raises(ValidationError, match="surprise"):
        Opponent.model_validate(league(surprise=True))


def test_a_side_is_away_or_home() -> None:
    assert [side.value for side in Side] == ["away", "home"]
