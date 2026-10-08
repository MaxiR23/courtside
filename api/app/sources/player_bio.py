# api/app/sources/player_bio.py
#
# Player bio adapter: fetches one player's bio from the provider and maps the
# season summary (points, rebounds, assists and field goal percentage, each with
# its league rank) to an internal bio. The season is the one the summary names,
# not the provider's current season. A bio with no summary gives no bio.
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/player.md, api/app/sources/player_draft.py

import datetime as dt
import re

from pydantic import (
    BaseModel,
    ConfigDict,
    NonNegativeFloat,
    PositiveInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json

SOURCE = "player_bio"
FRESH_FOR = dt.timedelta(hours=1)
STATISTICS = ("avgPoints", "avgRebounds", "avgAssists", "fieldGoalPct")

_SEASON = re.compile(r"^(\d{4}-\d{2})\b")


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderStatistic(_ProviderModel):
    name: str
    value: float
    rank: int | None = None


class _ProviderSummary(_ProviderModel):
    display_name: str
    statistics: list[_ProviderStatistic] = []


class _ProviderAthlete(_ProviderModel):
    stats_summary: _ProviderSummary | None = None


class _ProviderBio(_ProviderModel):
    athlete: _ProviderAthlete


class RankedValue(FeedModel):
    """A season statistic and its league rank, as the provider sends them."""

    value: NonNegativeFloat
    rank: PositiveInt | None = None


class PlayerBio(FeedModel):
    """The season summary of a player's bio. Field goal percentage is 0 to 100.
    Never reaches a feed."""

    season: str
    points: RankedValue
    rebounds: RankedValue
    assists: RankedValue
    field_goal_pct: RankedValue


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _invalid(reason: str) -> SourceError:
    return SourceError(SOURCE, f"invalid payload: {reason}")


async def fetch_player_bio(
    client: SourceClient, player_id: str, settings: Settings
) -> PlayerBio | None:
    """Return a player's season summary, None when the bio has none, or raise
    SourceError."""
    if settings.player_bio_url is None:
        raise SourceError(SOURCE, "player bio URL is not configured")
    url = settings.player_bio_url.format(player_id=player_id)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderBio.model_validate(body)
    except ValidationError as error:
        raise _invalid(
            f"{error.error_count()} errors, first at {_location(error)}"
        ) from None
    summary = provider.athlete.stats_summary
    if summary is None or not summary.statistics:
        return None
    season = _SEASON.match(summary.display_name)
    if season is None:
        raise _invalid("1 errors, first at athlete.statsSummary.displayName")
    values = {
        statistic.name: {"value": statistic.value, "rank": statistic.rank}
        for statistic in summary.statistics
    }
    missing = [name for name in STATISTICS if name not in values]
    if missing:
        raise _invalid(
            f"1 errors, first at athlete.statsSummary.statistics.{missing[0]}"
        )
    try:
        return PlayerBio.model_validate(
            {
                "season": season.group(1),
                "points": values["avgPoints"],
                "rebounds": values["avgRebounds"],
                "assists": values["avgAssists"],
                "field_goal_pct": values["fieldGoalPct"],
            }
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"player {player_id} is invalid: {first['type']} at {_location(error)}",
        ) from None
