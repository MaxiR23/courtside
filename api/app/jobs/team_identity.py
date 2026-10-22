# api/app/jobs/team_identity.py
#
# The team identities of the feeds and the hero accent rule (ADR 0068).
#
# identity_of makes a team's identity (logo and colors with their "#") from its team
# info. with_identities puts the identities on every league team object of a feed:
# an Opponent, or any feed model that declares a logo field (a standings row, a
# search team, the root of a team feed, a player's team, an All-Star league team).
# It finds them by their fields, so no section's model is imported here. It runs
# when a feed is served, never when it is built, so a kept feed picks up a new logo
# with no rebuild.
#
# identified applies the rules to one object, by its code. A guest, an object with
# no code, an unknown code and a historical object get no logo. An object with a
# season code and no historical flag (a past player's team) cannot tell whether
# the team was renamed, so it is treated as historical. Colors are set only on a
# model whose colors field is optional (an Opponent, a player's team, a search
# player's team); a model that requires colors keeps the colors it was built with,
# and the identity's logo is the only thing it gains.
#
# game_accent gives the color each side of a game shows in the hero. A side shows
# its primary color unless that color is too dark, then its secondary. If the
# away color is then too close to the home color, away shows its secondary. The
# distance is measured in OKLab. A side with no colors has no accent.
#
# SEE: docs/design-team-identity.md, docs/adr/0068-shared-team-identity-and-hero-accents.md,
# api/app/jobs/team_names.py

import math
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from app.feeds.games import GameAccent
from app.feeds.opponent import Opponent, TeamColors
from app.sources.team_info import TeamInfo, secondary_color
from app.storage.state import TeamIdentity

# A color darker than this lightness (OKLab L) is replaced by the secondary.
LIGHTNESS_FLOOR = 0.36
# Two sides closer than this distance (OKLab) are told apart by the secondary.
DISTANCE_FLOOR = 0.12

Lab = tuple[float, float, float]


def identity_of(code: str, info: TeamInfo) -> TeamIdentity:
    """The identity of a team: its logo and its colors with their "#"."""
    return TeamIdentity(
        code=code,
        logo=info.logo,
        colors=TeamColors(primary=f"#{info.color}", secondary=secondary_color(info)),
    )


def _is_team_object(value: object) -> bool:
    return isinstance(value, Opponent) or (
        isinstance(value, BaseModel) and "logo" in type(value).model_fields
    )


def _is_historical(team: BaseModel) -> bool:
    fields = type(team).model_fields
    if "historical" in fields:
        return bool(getattr(team, "historical", False))
    return getattr(team, "season_code", None) is not None


def identified[T: BaseModel](team: T, identities: Mapping[str, TeamIdentity]) -> T:
    """The team object with the logo (and the colors, where its model leaves them
    optional) of its identity; null for a guest, a historical object and a code
    with no identity."""
    fields = type(team).model_fields
    code = getattr(team, "code", None)
    identity = (
        None
        if getattr(team, "guest", False) or code is None or _is_historical(team)
        else identities.get(str(code))
    )
    update: dict[str, Any] = {"logo": None if identity is None else identity.logo}
    if "colors" in fields and not fields["colors"].is_required():
        update["colors"] = None if identity is None else identity.colors
    return team.model_copy(update=update)


def _stamped(value: Any, identities: Mapping[str, TeamIdentity]) -> Any:
    if isinstance(value, BaseModel):
        if _is_team_object(value):
            value = identified(value, identities)
        return value.model_copy(
            update={
                name: _stamped(getattr(value, name), identities)
                for name in type(value).model_fields
            }
        )
    if isinstance(value, list):
        return [_stamped(item, identities) for item in value]
    return value


def with_identities[M: BaseModel](
    model: M, identities: Mapping[str, TeamIdentity]
) -> M:
    """The model with the identity put on every league team object in it, the root
    included, validated again."""
    stamped = _stamped(model, identities)
    return type(model).model_validate(stamped.model_dump(by_alias=False))


def oklab(color: str) -> Lab:
    """The OKLab coordinates (L, a, b) of a color written "#rrggbb"."""

    def linear(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(int(color[i : i + 2], 16)) for i in (1, 3, 5))
    cone_l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    cone_m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    cone_s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * cone_l + 0.7936177850 * cone_m - 0.0040720468 * cone_s,
        1.9779984951 * cone_l - 2.4285922050 * cone_m + 0.4505937099 * cone_s,
        0.0259040371 * cone_l + 0.7827717662 * cone_m - 0.8086757660 * cone_s,
    )


def _resolved(colors: TeamColors) -> str:
    """The primary color, or the secondary when the primary is too dark."""
    if colors.secondary is not None and oklab(colors.primary)[0] < LIGHTNESS_FLOOR:
        return colors.secondary
    return colors.primary


def game_accent(away: Opponent, home: Opponent) -> GameAccent:
    """The hero color of each side of a game."""
    home_color = None if home.colors is None else _resolved(home.colors)
    away_color = None if away.colors is None else _resolved(away.colors)
    if (
        away.colors is not None
        and away.colors.secondary is not None
        and away_color == away.colors.primary
        and home_color is not None
        and away_color is not None
        and math.dist(oklab(away_color), oklab(home_color)) < DISTANCE_FLOOR
    ):
        away_color = away.colors.secondary
    return GameAccent(away=away_color, home=home_color)
