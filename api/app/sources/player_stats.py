# api/app/sources/player_stats.py
#
# Player stats adapter: fetches one player's per game averages, totals and
# miscellaneous counts by season, with the career rows, for the regular season
# or the playoffs. Shooting stays as "made-attempted" text and percentages stay
# from 0 to 100. A season played for two teams has one row per team and a
# combined row: the adapter keeps the combined row with the codes of the team
# rows in their order. A player the provider has no stats for gives no rows.
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/player.md, api/app/sources/team_schedule.py

import datetime as dt
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    StringConstraints,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, TeamCode
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json, with_query
from app.sources.teams import team_code_of_id

SOURCE = "player_stats"
FRESH_FOR = dt.timedelta(hours=1)
PLAYOFFS_SEASON_TYPE = 3

Made = Annotated[str, StringConstraints(pattern=r"^\d+(\.\d+)?-\d+(\.\d+)?$")]
Percent = Annotated[float, Field(ge=0, le=100)]
SeasonName = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}$")]

AVERAGE_LABELS = (
    "GP",
    "GS",
    "MIN",
    "FG",
    "FG%",
    "3PT",
    "3P%",
    "FT",
    "FT%",
    "OR",
    "DR",
    "REB",
    "AST",
    "BLK",
    "STL",
    "PF",
    "TO",
    "PTS",
)
TOTAL_LABELS = AVERAGE_LABELS[3:]
MISC_LABELS = ("DD2", "TD3", "DQ", "EJECT", "TECH", "FLAG", "AST/TO", "STL/TO")


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderSeason(_ProviderModel):
    display_name: str


class _ProviderRow(_ProviderModel):
    team_id: str | None = None
    team_slug: str
    season: _ProviderSeason
    stats: list[str]


class _ProviderCategory(_ProviderModel):
    name: str
    labels: list[str]
    statistics: list[_ProviderRow] = []
    totals: list[str] | None = None


class _ProviderStats(_ProviderModel):
    categories: list[_ProviderCategory] = []


class StatLine(FeedModel):
    """A season's or the career's stat line. The totals have no games played,
    games started or minutes. Never reaches a feed."""

    season: SeasonName | None = None
    teams: list[TeamCode] = Field(default_factory=list)
    games_played: NonNegativeInt | None = None
    games_started: NonNegativeInt | None = None
    minutes: NonNegativeFloat | None = None
    field_goals: Made
    field_goal_pct: Percent
    three_points: Made
    three_point_pct: Percent
    free_throws: Made
    free_throw_pct: Percent
    offensive_rebounds: NonNegativeFloat
    defensive_rebounds: NonNegativeFloat
    rebounds: NonNegativeFloat
    assists: NonNegativeFloat
    blocks: NonNegativeFloat
    steals: NonNegativeFloat
    fouls: NonNegativeFloat
    turnovers: NonNegativeFloat
    points: NonNegativeFloat


class MiscLine(FeedModel):
    """A season's or the career's miscellaneous counts. Never reaches a feed."""

    season: SeasonName | None = None
    double_doubles: NonNegativeInt
    triple_doubles: NonNegativeInt
    disqualifications: NonNegativeInt
    ejections: NonNegativeInt
    technicals: NonNegativeInt
    flagrants: NonNegativeInt
    assist_turnover_ratio: NonNegativeFloat
    steal_turnover_ratio: NonNegativeFloat


class PlayerStats(FeedModel):
    """A player's rows by season in the provider's order, and the career rows."""

    per_game: list[StatLine] = Field(default_factory=list)
    totals: list[StatLine] = Field(default_factory=list)
    misc: list[MiscLine] = Field(default_factory=list)
    career_per_game: StatLine | None = None
    career_totals: StatLine | None = None
    career_misc: MiscLine | None = None


_STAT_FIELDS = {
    "FG": "field_goals",
    "FG%": "field_goal_pct",
    "3PT": "three_points",
    "3P%": "three_point_pct",
    "FT": "free_throws",
    "FT%": "free_throw_pct",
    "OR": "offensive_rebounds",
    "DR": "defensive_rebounds",
    "REB": "rebounds",
    "AST": "assists",
    "BLK": "blocks",
    "STL": "steals",
    "PF": "fouls",
    "TO": "turnovers",
    "PTS": "points",
    "GP": "games_played",
    "GS": "games_started",
    "MIN": "minutes",
}
_MISC_FIELDS = {
    "DD2": "double_doubles",
    "TD3": "triple_doubles",
    "DQ": "disqualifications",
    "EJECT": "ejections",
    "TECH": "technicals",
    "FLAG": "flagrants",
    "AST/TO": "assist_turnover_ratio",
    "STL/TO": "steal_turnover_ratio",
}


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _invalid(reason: str) -> SourceError:
    return SourceError(SOURCE, f"invalid payload: {reason}")


def _values(
    category: _ProviderCategory,
    stats: list[str],
    required: tuple[str, ...],
    fields: dict[str, str],
) -> dict[str, object]:
    if len(stats) != len(category.labels) or any(
        label not in category.labels for label in required
    ):
        raise _invalid(f"1 errors, first at {category.name} stats")
    return {
        fields[label]: value
        for label, value in zip(category.labels, stats, strict=True)
        if label in fields
    }


def _season_rows(
    category: _ProviderCategory,
) -> list[tuple[str, list[str], list[str]]]:
    """Each season once, in order, with its stats and the provider team ids of
    its team rows. A combined row replaces the team rows of its season."""
    team_rows: dict[str, list[str]] = {}
    combined: dict[str, list[str]] = {}
    team_ids: dict[str, list[str]] = {}
    for row in category.statistics:
        name = row.season.display_name
        ids = team_ids.setdefault(name, [])
        if row.team_slug == f"{name} Totals":
            combined[name] = row.stats
        elif row.team_id is None:
            raise _invalid(f"1 errors, first at {category.name} team of {name}")
        else:
            team_rows.setdefault(name, row.stats)
            if row.team_id not in ids:
                ids.append(row.team_id)
    return [
        (name, combined.get(name, team_rows.get(name, [])), ids)
        for name, ids in team_ids.items()
    ]


def _stat_lines(
    category: _ProviderCategory, required: tuple[str, ...]
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    rows = [
        {
            **_values(category, stats, required, _STAT_FIELDS),
            "season": name,
            "teams": [team_code_of_id(team_id, source=SOURCE) for team_id in team_ids],
        }
        for name, stats, team_ids in _season_rows(category)
    ]
    career = (
        _values(category, category.totals, required, _STAT_FIELDS)
        if category.totals is not None
        else None
    )
    return rows, career


def _misc_lines(
    category: _ProviderCategory,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    rows = [
        {**_values(category, stats, MISC_LABELS, _MISC_FIELDS), "season": name}
        for name, stats, _ in _season_rows(category)
    ]
    career = (
        _values(category, category.totals, MISC_LABELS, _MISC_FIELDS)
        if category.totals is not None
        else None
    )
    return rows, career


async def fetch_player_stats(
    client: SourceClient, player_id: str, settings: Settings, *, playoffs: bool
) -> PlayerStats:
    """Return a player's rows by season and the career rows of the regular
    season or the playoffs, empty when the provider has none, or raise
    SourceError."""
    if settings.player_stats_url is None:
        raise SourceError(SOURCE, "player stats URL is not configured")
    url = settings.player_stats_url.format(player_id=player_id)
    if playoffs:
        url = with_query(url, {"seasontype": PLAYOFFS_SEASON_TYPE})
    try:
        body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    except SourceError as error:
        if error.status_code == 404:
            return PlayerStats()
        raise
    try:
        provider = _ProviderStats.model_validate(body)
    except ValidationError as error:
        raise _invalid(
            f"{error.error_count()} errors, first at {_location(error)}"
        ) from None

    built: dict[str, object] = {}
    for category in provider.categories:
        if category.name == "averages":
            rows, career = _stat_lines(category, AVERAGE_LABELS)
            built["per_game"], built["career_per_game"] = rows, career
        elif category.name == "totals":
            rows, career = _stat_lines(category, TOTAL_LABELS)
            built["totals"], built["career_totals"] = rows, career
        elif category.name == "miscellaneous":
            rows, career = _misc_lines(category)
            built["misc"], built["career_misc"] = rows, career
    try:
        return PlayerStats.model_validate(built)
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"player {player_id} is invalid: {first['type']} at {_location(error)}",
        ) from None
