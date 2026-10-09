# api/app/sources/player_gamelog.py
#
# Player game log adapter: fetches one player's game log of the provider's
# current season and maps the regular season, postseason and preseason games
# with their stats. The stats come as text aligned with the
# labels the response names; shooting stays as "made-attempted" text and
# percentages stay from 0 to 100. An All-Star game has no opponent. An opponent
# without a code is a guest; one with neither a code nor a name is not a team and
# its game is skipped (ADR 0026). Only the events a season type references are
# validated.
# The provider URL comes from Settings. Provider data never leaves this module.
#
# SEE: docs/api/player.md, api/app/sources/team_schedule.py

import datetime as dt
import re
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    StringConstraints,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.games import FeedModel, NonEmptyStr, UtcDatetime
from app.feeds.opponent import Opponent
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, get_json
from app.sources.teams import to_opponent

SOURCE = "player_gamelog"
FRESH_FOR = dt.timedelta(hours=1)
LABELS = (
    "MIN",
    "FG",
    "FG%",
    "3PT",
    "3P%",
    "FT",
    "FT%",
    "REB",
    "AST",
    "BLK",
    "STL",
    "PF",
    "TO",
    "PTS",
)

Made = Annotated[str, StringConstraints(pattern=r"^\d+-\d+$")]
Percent = Annotated[float, Field(ge=0, le=100)]
_SEASON_TYPE = re.compile(r"^(\d{4}-\d{2}) (Regular Season|Postseason|Preseason)$")


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderOpponent(_ProviderModel):
    abbreviation: str | None = None
    id: str | None = None
    display_name: str | None = None
    name: str | None = None
    location: str | None = None


class _ProviderEvent(_ProviderModel):
    id: str
    at_vs: str
    game_date: UtcDatetime
    game_result: str
    home_team_score: NonNegativeInt
    away_team_score: NonNegativeInt
    opponent: _ProviderOpponent | None = None
    event_note: str | None = None


class _ProviderLine(_ProviderModel):
    event_id: str
    stats: list[str]


class _ProviderCategory(_ProviderModel):
    events: list[_ProviderLine] = []


class _ProviderSeasonType(_ProviderModel):
    display_name: str
    categories: list[_ProviderCategory] = []


class _ProviderGameLog(_ProviderModel):
    labels: list[str]
    events: dict[str, Any] = {}
    season_types: list[_ProviderSeasonType] = []


class GameLogGame(FeedModel):
    """One game of a player's log. Never reaches a feed."""

    game_id: NonEmptyStr
    start_time: UtcDatetime
    is_home: bool
    opponent: Opponent | None = None
    won: bool
    team_score: NonNegativeInt
    opponent_score: NonNegativeInt
    note: NonEmptyStr | None = None
    playoffs: bool
    preseason: bool
    minutes: Annotated[str, StringConstraints(pattern=r"^\d+(\.\d+)?$")]
    field_goals: Made
    field_goal_pct: Percent
    three_points: Made
    three_point_pct: Percent
    free_throws: Made
    free_throw_pct: Percent
    rebounds: NonNegativeInt
    assists: NonNegativeInt
    blocks: NonNegativeInt
    steals: NonNegativeInt
    fouls: NonNegativeInt
    turnovers: NonNegativeInt
    points: NonNegativeInt


class PlayerGameLog(FeedModel):
    """A player's regular season, postseason and preseason games of one season. Never
    reaches a feed."""

    season: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}$")] | None = None
    games: list[GameLogGame]


def _location(error: ValidationError) -> str:
    return ".".join(str(part) for part in error.errors()[0]["loc"])


def _invalid(reason: str) -> SourceError:
    return SourceError(SOURCE, f"invalid payload: {reason}")


def _opponent(event: _ProviderEvent) -> dict[str, Any] | None:
    opponent = event.opponent or _ProviderOpponent()
    return to_opponent(
        opponent.abbreviation,
        opponent.id,
        opponent.name or opponent.display_name,
        opponent.location,
        source=SOURCE,
    )


def _game(
    event: _ProviderEvent,
    line: _ProviderLine,
    columns: dict[str, int],
    playoffs: bool,
    preseason: bool,
) -> dict[str, object] | None:
    stats = line.stats
    if len(stats) != len(columns) or any(label not in columns for label in LABELS):
        raise _invalid(f"1 errors, first at stats of event {line.event_id}")

    def stat(label: str) -> str:
        return stats[columns[label]]

    note = event.event_note
    all_star = note is not None and note.startswith("NBA All-Star")
    is_home = event.at_vs == "vs"
    home, away = event.home_team_score, event.away_team_score
    opponent = None if all_star else _opponent(event)
    if opponent is None and not all_star:
        return None
    return {
        "game_id": event.id,
        "start_time": event.game_date,
        "is_home": is_home,
        "opponent": opponent,
        "won": event.game_result == "W",
        "team_score": home if is_home else away,
        "opponent_score": away if is_home else home,
        "note": note,
        "playoffs": playoffs,
        "preseason": preseason,
        "minutes": stat("MIN"),
        "field_goals": stat("FG"),
        "field_goal_pct": stat("FG%"),
        "three_points": stat("3PT"),
        "three_point_pct": stat("3P%"),
        "free_throws": stat("FT"),
        "free_throw_pct": stat("FT%"),
        "rebounds": stat("REB"),
        "assists": stat("AST"),
        "blocks": stat("BLK"),
        "steals": stat("STL"),
        "fouls": stat("PF"),
        "turnovers": stat("TO"),
        "points": stat("PTS"),
    }


async def fetch_player_gamelog(
    client: SourceClient, player_id: str, settings: Settings
) -> PlayerGameLog:
    """Return a player's regular season and postseason games, or raise
    SourceError."""
    if settings.player_gamelog_url is None:
        raise SourceError(SOURCE, "player game log URL is not configured")
    url = settings.player_gamelog_url.format(player_id=player_id)
    body = await get_json(client, url, source=SOURCE, fresh=FRESH_FOR)
    try:
        provider = _ProviderGameLog.model_validate(body)
    except ValidationError as error:
        raise _invalid(
            f"{error.error_count()} errors, first at {_location(error)}"
        ) from None

    columns = {label: index for index, label in enumerate(provider.labels)}
    season: str | None = None
    games: list[dict[str, object]] = []
    for season_type in provider.season_types:
        matched = _SEASON_TYPE.match(season_type.display_name)
        if matched is None:
            continue
        season = season or matched.group(1)
        playoffs = matched.group(2) == "Postseason"
        preseason = matched.group(2) == "Preseason"
        for category in season_type.categories:
            for line in category.events:
                raw = provider.events.get(line.event_id)
                if raw is None:
                    raise _invalid(f"1 errors, first at events.{line.event_id}")
                try:
                    event = _ProviderEvent.model_validate(raw)
                except ValidationError as error:
                    raise _invalid(
                        f"{error.error_count()} errors, first at"
                        f" events.{line.event_id}.{_location(error)}"
                    ) from None
                game = _game(event, line, columns, playoffs, preseason)
                if game is not None:
                    games.append(game)
    try:
        return PlayerGameLog.model_validate({"season": season, "games": games})
    except ValidationError as error:
        first = error.errors()[0]
        raise SourceError(
            SOURCE,
            f"player {player_id} is invalid: {first['type']} at {_location(error)}",
        ) from None
