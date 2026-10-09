# api/app/feeds/base.py
#
# The base of every feed model and the field types the feeds share.
#
# SEE: docs/adr/0008-contract-generation.md

import datetime as dt
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
# A guest side keeps the provider's own code, whatever it looks like (ADR 0025).
SideCode = NonEmptyStr
Percentage = Annotated[float, Field(ge=0, le=1)]


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
