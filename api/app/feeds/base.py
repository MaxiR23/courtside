# api/app/feeds/base.py
#
# The base of every feed model and the field types the feeds share.
#
# SEE: docs/adr/0008-contract-generation.md

import datetime as dt
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)
from pydantic.alias_generators import to_camel


def _require_utc(value: dt.datetime) -> dt.datetime:
    if value.utcoffset() != dt.timedelta(0):
        raise ValueError("must be in UTC")
    return value


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_require_utc)]
TeamCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
SeasonLabel = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}$")]
# A guest side keeps the provider's own code, whatever it looks like (ADR 0025).
SideCode = NonEmptyStr
Percentage = Annotated[float, Field(ge=0, le=1)]


class AwardCode(StrEnum):
    """The kind of a season award, shared by the playoffs and the player feeds."""

    MVP = "mvp"
    DPOY = "dpoy"
    ROY = "roy"
    SIXTH_MAN = "sixth_man"
    MIP = "mip"
    CPOY = "cpoy"
    FINALS_MVP = "finals_mvp"
    EAST_FINALS_MVP = "east_finals_mvp"
    WEST_FINALS_MVP = "west_finals_mvp"
    ALL_STAR_MVP = "all_star_mvp"
    CUP_MVP = "cup_mvp"
    CUP_ALL_TOURNAMENT = "cup_all_tournament"
    ALL_NBA = "all_nba"
    ALL_ROOKIE = "all_rookie"
    ALL_DEFENSIVE = "all_defensive"
    TWYMAN_STOKES = "twyman_stokes"


class FeedModel(BaseModel):
    """Base of every feed model: camelCase keys, no unknown fields."""

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        json_schema_serialization_defaults_required=True,
    )
