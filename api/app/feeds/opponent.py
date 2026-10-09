# api/app/feeds/opponent.py
#
# The one model of a game side or an opponent: one of the 30 league teams, or a
# guest team outside the league with the source's name and city and, when the
# source sends one, its code (ADR 0025, ADR 0026). Every feed that shows an
# opponent uses it, and future features (full calendar, brackets) reuse it.
#
# SEE: docs/adr/0026-one-guest-team-rule.md, docs/api/games.md

import re
from enum import StrEnum

from pydantic import model_validator

from app.feeds.base import FeedModel, NonEmptyStr, SideCode


class Side(StrEnum):
    AWAY = "away"
    HOME = "home"


class Opponent(FeedModel):
    """A team a game is played against: a league team or a guest."""

    code: SideCode | None
    name: NonEmptyStr | None
    city: NonEmptyStr | None
    guest: bool = False

    @model_validator(mode="after")
    def _require_a_league_code_of_a_league_team(self) -> Opponent:
        if not self.guest and (
            self.code is None or re.fullmatch(r"[A-Z]{3}", self.code) is None
        ):
            raise ValueError("a league team code is three capital letters")
        return self

    @model_validator(mode="after")
    def _require_a_code_or_a_name_of_a_guest(self) -> Opponent:
        if self.guest and self.code is None and self.name is None:
            raise ValueError("a guest team has a code or a name")
        return self
