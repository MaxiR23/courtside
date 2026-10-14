# api/app/sources/team_postseason.py
#
# Team postseason adapter: fetches the postseason record (overall, home and
# road) and the postseason statistics of one team from the provider. The record
# items are named overall, Home and Road; a summary that is not W-L is null. The
# statistics are flattened by name across the categories; a missing statistic is
# null and the plus-minus statistic is never read. The provider team id comes
# from the fixed team id table. The provider URLs come from Settings. Provider
# data never leaves this module.
#
# SEE: docs/api/playoffs.md, docs/adr/0032-playoffs-feed.md,
# api/app/sources/depth_chart.py

import datetime as dt
import re

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel
from app.settings import Settings
from app.sources.depth_chart import PROVIDER_IDS
from app.sources.http import SourceClient, SourceError, get_json

SOURCE_RECORD = "team_postseason_record"
SOURCE_STATS = "team_postseason_stats"
FRESH_FOR = dt.timedelta(hours=1)
_RECORD = re.compile(r"^\d+-\d+$")
RECORD_ITEMS = {"overall": "overall", "Home": "home", "Road": "road"}
# The provider name of each statistic.
STAT_NAMES = {
    "points": "avgPoints",
    "rebounds": "avgRebounds",
    "assists": "avgAssists",
    "blocks": "avgBlocks",
    "steals": "avgSteals",
    "field_goal_pct": "fieldGoalPct",
    "effective_fg_pct": "effectiveFGPct",
    "technical_fouls": "technicalFouls",
    "games_played": "gamesPlayed",
}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderRecordItem(_ProviderModel):
    name: str
    summary: str | None = None


class _ProviderRecord(_ProviderModel):
    items: list[_ProviderRecordItem]


class _ProviderStat(_ProviderModel):
    name: str
    value: float | None = None


class _ProviderCategory(_ProviderModel):
    stats: list[_ProviderStat] = []


class _ProviderSplits(_ProviderModel):
    categories: list[_ProviderCategory]


class _ProviderStats(_ProviderModel):
    splits: _ProviderSplits


class TeamPostseasonRecord(FeedModel):
    """A team's postseason record as W-L text. Never reaches a feed."""

    overall: str | None
    home: str | None
    road: str | None


class TeamPostseasonStats(FeedModel):
    """A team's postseason statistics, each null when absent. Never reaches a
    feed."""

    points: float | None
    rebounds: float | None
    assists: float | None
    blocks: float | None
    steals: float | None
    field_goal_pct: float | None
    effective_fg_pct: float | None
    technical_fouls: float | None
    games_played: int | None


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _team_id(team_code: str, source: str) -> str:
    team_id = PROVIDER_IDS.get(team_code)
    if team_id is None:
        raise SourceError(source, f"unknown team code {team_code!r}")
    return team_id


async def fetch_team_postseason_record(
    client: SourceClient, team_code: str, season: int, settings: Settings
) -> TeamPostseasonRecord:
    """Return the postseason record of one team, or raise SourceError."""
    if not settings.team_postseason_record_url:
        raise SourceError(SOURCE_RECORD, "team postseason record URL is not configured")
    team_id = _team_id(team_code, SOURCE_RECORD)
    url = settings.team_postseason_record_url.format(season=season, team_id=team_id)
    body = await get_json(client, url, source=SOURCE_RECORD, fresh=FRESH_FOR)
    try:
        provider = _ProviderRecord.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE_RECORD,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    found: dict[str, str | None] = {"overall": None, "home": None, "road": None}
    for item in provider.items:
        field = RECORD_ITEMS.get(item.name)
        if field is not None and item.summary and _RECORD.match(item.summary):
            found[field] = item.summary
    return TeamPostseasonRecord(**found)


async def fetch_team_postseason_stats(
    client: SourceClient, team_code: str, season: int, settings: Settings
) -> TeamPostseasonStats:
    """Return the postseason statistics of one team, or raise SourceError."""
    if not settings.team_postseason_stats_url:
        raise SourceError(SOURCE_STATS, "team postseason stats URL is not configured")
    team_id = _team_id(team_code, SOURCE_STATS)
    url = settings.team_postseason_stats_url.format(season=season, team_id=team_id)
    body = await get_json(client, url, source=SOURCE_STATS, fresh=FRESH_FOR)
    try:
        provider = _ProviderStats.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE_STATS,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None
    values = {
        stat.name: stat.value
        for category in provider.splits.categories
        for stat in category.stats
    }
    mapped: dict[str, float | int | None] = {
        field: values.get(name) for field, name in STAT_NAMES.items()
    }
    games = mapped["games_played"]
    mapped["games_played"] = None if games is None else int(games)
    return TeamPostseasonStats.model_validate(mapped)
