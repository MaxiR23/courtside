# api/app/feeds/opponent.py
#
# The one model of a game side or an opponent: one of the 30 league teams, or a
# guest team outside the league with the source's name and city and, when the
# source sends one, its code (ADR 0025, ADR 0026). Every feed that shows an
# opponent uses it, and future features (full calendar, brackets) reuse it.
#
# On a past feed a league side also carries the abbreviation it had in that season
# and whether that season's name, city or abbreviation differs from today's
# (ADR 0054); the link code stays today's.
#
# A league side also carries the team's logo and colors (ADR 0068). They are put on
# a feed when it is served, never by a builder; a guest and a historical side have no
# logo, and a guest has no colors. TeamLogo and TeamColors are the one shape of a
# logo and of a team's colors in every feed that carries them.
#
# SEE: docs/adr/0026-one-guest-team-rule.md, docs/adr/0054-historical-sides-and-past-pages.md,
# docs/adr/0068-shared-team-identity-and-hero-accents.md, docs/api/games.md

import re
from enum import StrEnum

from pydantic import HttpUrl, model_validator

from app.feeds.base import FeedModel, HexColor, NonEmptyStr, SideCode


class Side(StrEnum):
    AWAY = "away"
    HOME = "home"


class TeamLogo(FeedModel):
    """A team's logo: the one for a light background and, when the source has
    one, the one for a dark background."""

    light: HttpUrl
    dark: HttpUrl | None


class TeamColors(FeedModel):
    primary: HexColor
    secondary: HexColor | None


class Opponent(FeedModel):
    """A team a game is played against: a league team or a guest."""

    code: SideCode | None
    name: NonEmptyStr | None
    city: NonEmptyStr | None
    guest: bool = False
    # The side's abbreviation in a past season, from that season's team object, and
    # whether that season's name, city or abbreviation differs from today's (ADR 0054).
    # Null and false on a current feed and on a guest.
    season_code: SideCode | None = None
    historical: bool = False
    # The team's logo and colors (ADR 0068). Null on a guest, on a historical side
    # (logo) and when the identity is not known.
    logo: TeamLogo | None = None
    colors: TeamColors | None = None

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

    @model_validator(mode="after")
    def _require_a_season_code_of_a_historical_league_side(self) -> Opponent:
        if self.guest and (self.season_code is not None or self.historical):
            raise ValueError("a guest team has no season code and is not historical")
        if self.historical and self.season_code is None:
            raise ValueError("a historical side has a season code")
        return self

    @model_validator(mode="after")
    def _require_no_identity_of_a_guest_or_historical_side(self) -> Opponent:
        if self.guest and (self.logo is not None or self.colors is not None):
            raise ValueError("a guest team has no logo and no colors")
        if self.historical and self.logo is not None:
            raise ValueError("a historical side has no logo")
        return self
