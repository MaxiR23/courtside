# api/app/sources/power_index.py
#
# Power index adapter: reads the paged power ranking of a season from the provider
# and maps each team to its standard code, its rank, its ratings, its record, its
# projected record and its two chances, in the provider's order. The index holds
# up to three runs of the season (regular season, play-in and postseason) and only
# the regular-season items are kept. A team is read from the provider team id in
# its link, never by following the link. A negative rank is a tie: the team keeps
# the absolute rank and tied is true. A stat that is absent, null or has an empty
# display value is null: a missing stat is never a failure. Page 1 is read, and
# page 2 only when page 1 held PAGE_SIZE items or more; no page after MAX_PAGES is
# ever read. The provider URL comes from Settings, and its own query is kept.
# Provider data never leaves this module.
#
# SEE: docs/api/power-ranking.md, docs/adr/0075-power-ranking-feed.md,
# api/app/sources/season_awards.py

import datetime as dt

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr, TeamCode
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.season_types import REGULAR_SEASON
from app.sources.teams import team_code_of_id

SOURCE = "power_index"
FRESH_FOR = dt.timedelta(hours=1)
PAGE_SIZE = 25
MAX_PAGES = 2
# The provider's stat names.
RANK = "bpirank"
RATING = "bpi"
OFFENSE = "bpioffense"
DEFENSE = "bpidefense"
WINS = "numwins"
LOSSES = "numlosses"
PROJECTED_WINS = "projectedw"
PROJECTED_LOSSES = "projectedl"
PLAYOFFS = "probmakeplayoffs"
TITLE = "probwintitle"


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderRef(_ProviderModel):
    ref: str = Field(alias="$ref")


class _ProviderStat(_ProviderModel):
    name: str
    value: float | None = None
    display_value: str | None = None


class _ProviderItem(_ProviderModel):
    season_type: int
    team: _ProviderRef
    stats: list[_ProviderStat] = []


class _ProviderPage(_ProviderModel):
    items: list[_ProviderItem]


class PowerIndexTeam(FeedModel):
    """A team of the power index. Never reaches a feed."""

    code: TeamCode
    rank: int | None
    tied: bool
    rating: float | None
    offense: float | None
    defense: float | None
    wins: int | None
    losses: int | None
    projected_wins: float | None
    projected_losses: float | None
    playoffs: float | None
    title: float | None
    playoffs_text: NonEmptyStr | None
    title_text: NonEmptyStr | None


class PowerIndex(FeedModel):
    """The regular-season teams of the index in the provider's order. Never reaches
    a feed."""

    teams: list[PowerIndexTeam]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _team_code(ref: str) -> str:
    parts = httpx.URL(ref).path.rstrip("/").split("/")
    if "teams" not in parts[:-1]:
        raise SourceError(SOURCE, "team link has no team id")
    return team_code_of_id(parts[parts.index("teams") + 1], source=SOURCE)


def _stats(item: _ProviderItem) -> dict[str, _ProviderStat]:
    return {
        stat.name: stat
        for stat in item.stats
        if stat.value is not None and stat.display_value != ""
    }


def _number(stats: dict[str, _ProviderStat], name: str) -> float | None:
    stat = stats.get(name)
    return None if stat is None else stat.value


def _whole(stats: dict[str, _ProviderStat], name: str) -> int | None:
    value = _number(stats, name)
    if value is None:
        return None
    if not value.is_integer():
        raise SourceError(SOURCE, f"stat {name} is not a whole number")
    return int(value)


def _text(stats: dict[str, _ProviderStat], name: str) -> str | None:
    stat = stats.get(name)
    return None if stat is None else stat.display_value or None


def _team(item: _ProviderItem) -> PowerIndexTeam:
    stats = _stats(item)
    rank = _whole(stats, RANK)
    return PowerIndexTeam(
        code=_team_code(item.team.ref),
        rank=None if rank is None else abs(rank),
        tied=rank is not None and rank < 0,
        rating=_number(stats, RATING),
        offense=_number(stats, OFFENSE),
        defense=_number(stats, DEFENSE),
        wins=_whole(stats, WINS),
        losses=_whole(stats, LOSSES),
        projected_wins=_number(stats, PROJECTED_WINS),
        projected_losses=_number(stats, PROJECTED_LOSSES),
        playoffs=_number(stats, PLAYOFFS),
        title=_number(stats, TITLE),
        playoffs_text=_text(stats, PLAYOFFS),
        title_text=_text(stats, TITLE),
    )


async def _read_page(
    client: SourceClient, template: str, season: int, page: int
) -> _ProviderPage:
    url = template.format(season=season, page=page)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        return _ProviderPage.model_validate(body)
    except ValidationError as error:
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {_location(error)}",
        ) from None


async def fetch_power_index(
    client: SourceClient, season: int, settings: Settings
) -> PowerIndex:
    """Return the regular-season teams of the power index, or raise SourceError."""
    if not settings.power_index_url:
        raise SourceError(SOURCE, "power index URL is not configured")
    items: list[_ProviderItem] = []
    for page in range(1, MAX_PAGES + 1):
        read = await _read_page(client, settings.power_index_url, season, page)
        items.extend(read.items)
        if len(read.items) < PAGE_SIZE:
            break
    return PowerIndex(
        teams=[_team(item) for item in items if item.season_type == REGULAR_SEASON]
    )
