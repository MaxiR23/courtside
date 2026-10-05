# api/app/sources/game_detail.py
#
# Game detail adapter: fetches one game's box score from the provider and
# maps it to the contract's leaders and team stats. The provider URLs come
# from Settings. Provider data never leaves this module.
#
# SEE: docs/api/games.md, api/app/sources/scoreboard.py

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, GameTeamStats, Leaders
from app.settings import Settings
from app.sources.http import SourceError, get_json
from app.sources.teams import to_team_code

SOURCE = "game_detail"
PERCENT_STATS = {
    "field_goal_pct": "fieldGoalPct",
    "three_point_pct": "threePointFieldGoalPct",
}
COUNT_STATS = {
    "rebounds": "totalRebounds",
    "assists": "assists",
    "turnovers": "turnovers",
}


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeamRef(_ProviderModel):
    abbreviation: str


class _ProviderStatistic(_ProviderModel):
    name: str
    display_value: str


class _ProviderBoxTeam(_ProviderModel):
    home_away: str
    team: _ProviderTeamRef
    statistics: list[_ProviderStatistic]


class _ProviderAthlete(_ProviderModel):
    id: str
    display_name: str


class _ProviderAthleteLine(_ProviderModel):
    athlete: _ProviderAthlete
    stats: list[str]


class _ProviderStatGroup(_ProviderModel):
    keys: list[str]
    athletes: list[_ProviderAthleteLine]


class _ProviderBoxPlayers(_ProviderModel):
    team: _ProviderTeamRef
    statistics: list[_ProviderStatGroup]


class _ProviderBoxscore(_ProviderModel):
    teams: list[_ProviderBoxTeam]
    players: list[_ProviderBoxPlayers]


class _ProviderGameDetail(_ProviderModel):
    boxscore: _ProviderBoxscore


class GameDetail(FeedModel):
    """A game's detail as the box score knows it: leaders and team stats."""

    leaders: Leaders
    team_stats: GameTeamStats


def _number(game_id: str, value: str, kind: type[int] | type[float]) -> Any:
    try:
        return kind(value)
    except ValueError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat that is not a number"
        ) from None


def _leader(
    game_id: str, code: str, players: _ProviderBoxPlayers, photo_url: str
) -> dict[str, Any]:
    if not players.statistics:
        raise SourceError(SOURCE, f"game {game_id} has no player stats for {code}")
    group = players.statistics[0]
    columns: dict[str, int] = {}
    for key in ("points", "rebounds", "assists"):
        if key not in group.keys:
            raise SourceError(SOURCE, f"game {game_id} has no {key} column")
        columns[key] = group.keys.index(key)
    played = [line for line in group.athletes if line.stats]
    if not played:
        raise SourceError(SOURCE, f"game {game_id} has no player stats for {code}")
    try:
        values = [
            {key: _number(game_id, line.stats[i], int) for key, i in columns.items()}
            for line in played
        ]
    except IndexError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat line shorter than its columns"
        ) from None
    top = max(range(len(played)), key=lambda i: values[i]["points"])
    athlete = played[top].athlete
    return {
        "player_id": athlete.id,
        "display_name": athlete.display_name,
        "team_code": code,
        "photo_url": photo_url.format(player_id=athlete.id),
        **values[top],
    }


def _team_stats(game_id: str, team: _ProviderBoxTeam) -> dict[str, Any]:
    by_name = {stat.name: stat.display_value for stat in team.statistics}

    def lookup(name: str) -> str:
        if name not in by_name:
            raise SourceError(SOURCE, f"game {game_id} has no {name} stat")
        return by_name[name]

    stats: dict[str, Any] = {}
    for field, name in PERCENT_STATS.items():
        stats[field] = _number(game_id, lookup(name), float) / 100
    for field, name in COUNT_STATS.items():
        stats[field] = _number(game_id, lookup(name), int)
    return stats


async def fetch_game_detail(
    client: httpx.AsyncClient, game_id: str, settings: Settings
) -> GameDetail:
    """Return the leaders and team stats of one game, or raise SourceError."""
    if settings.game_detail_url is None:
        raise SourceError(SOURCE, "game detail URL is not configured")
    if settings.player_photo_url is None:
        raise SourceError(SOURCE, "player photo URL is not configured")
    url = settings.game_detail_url.format(game_id=game_id)
    body = await get_json(client, url, source=SOURCE)
    try:
        detail = _ProviderGameDetail.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None

    box = detail.boxscore
    sides = {team.home_away: team for team in box.teams}
    if set(sides) != {"home", "away"} or len(box.teams) != 2:
        raise SourceError(SOURCE, f"game {game_id} needs one home and one away team")

    leaders: dict[str, Any] = {}
    team_stats: dict[str, Any] = {}
    for side, team in sides.items():
        abbreviation = team.team.abbreviation
        code = to_team_code(abbreviation, source=SOURCE)
        players = next(
            (p for p in box.players if p.team.abbreviation == abbreviation), None
        )
        if players is None:
            raise SourceError(
                SOURCE, f"game {game_id} has no players for {abbreviation}"
            )
        leaders[side] = _leader(game_id, code, players, settings.player_photo_url)
        team_stats[side] = _team_stats(game_id, team)

    try:
        return GameDetail.model_validate({"leaders": leaders, "team_stats": team_stats})
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {game_id} is invalid: {first['type']} at {location}"
        ) from None
