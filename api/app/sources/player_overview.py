# api/app/sources/player_overview.py
#
# Player overview adapter: fetches one player's overview from the provider and
# maps its awards to a name, a count text such as "3x" and the season end years.
# An overview with no awards gives an empty list.
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/player.md, api/app/sources/player_draft.py

import datetime as dt
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json

SOURCE = "player_overview"
FRESH_FOR = dt.timedelta(hours=1)

DisplayCount = Annotated[str, StringConstraints(pattern=r"^\d+x$")]
EndYear = Annotated[str, StringConstraints(pattern=r"^\d{4}$")]


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderAward(_ProviderModel):
    name: NonEmptyStr
    display_count: DisplayCount
    seasons: list[EndYear]


class _ProviderOverview(_ProviderModel):
    awards: list[_ProviderAward] = []


class ProviderAward(FeedModel):
    """An award with its count text and the end years of its seasons. Never
    reaches a feed."""

    name: NonEmptyStr
    display_count: DisplayCount
    seasons: list[int]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


async def fetch_player_awards(
    client: SourceClient, player_id: str, settings: Settings
) -> list[ProviderAward]:
    """Return a player's awards, or raise SourceError."""
    if settings.player_overview_url is None:
        raise SourceError(SOURCE, "player overview URL is not configured")
    url = settings.player_overview_url.format(player_id=player_id)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderOverview.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    return [
        ProviderAward(
            name=award.name,
            display_count=award.display_count,
            seasons=[int(year) for year in award.seasons],
        )
        for award in provider.awards
    ]
