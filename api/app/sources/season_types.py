# api/app/sources/season_types.py
#
# Season type adapter: fetches the start and end of one season type (2 regular
# season, 5 play-in, 3 postseason) of a season from the provider and maps them to
# UTC instants. The window is read as the provider sends it: the playoffs feed
# turns it into US Eastern dates. A payload without both dates, or with an end
# that is not after the start, is rejected. The provider URL comes from Settings.
# Provider data never leaves this module.
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md

import datetime as dt

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    ValidationError,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, UtcDatetime
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json

SOURCE = "season_type"
FRESH_FOR = dt.timedelta(hours=1)
REGULAR_SEASON = 2
PLAY_IN = 5
POSTSEASON = 3


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderSeasonType(_ProviderModel):
    start_date: AwareDatetime
    end_date: AwareDatetime


class SeasonWindow(FeedModel):
    """The start and end of a season type. Never reaches a feed."""

    season_type: int
    start: UtcDatetime
    end: UtcDatetime

    @model_validator(mode="after")
    def _require_the_end_after_the_start(self) -> SeasonWindow:
        if self.end <= self.start:
            raise ValueError("the end must be after the start")
        return self


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


async def fetch_season_type(
    client: SourceClient, season: int, season_type: int, settings: Settings
) -> SeasonWindow:
    """Return the window of a season type of a season, or raise SourceError."""
    if not settings.season_type_url:
        raise SourceError(SOURCE, "season type URL is not configured")
    url = settings.season_type_url.format(season=season, type=season_type)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderSeasonType.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    try:
        return SeasonWindow(
            season_type=season_type,
            start=provider.start_date.astimezone(dt.UTC),
            end=provider.end_date.astimezone(dt.UTC),
        )
    except ValidationError:
        raise SourceError(SOURCE, "the end is not after the start") from None
