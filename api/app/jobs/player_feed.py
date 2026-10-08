# api/app/jobs/player_feed.py
#
# Player feed builder: a pure function from the data the source adapters fetched
# to the player feed, with every conversion the contract needs: height in
# centimeters, weight in kilograms, ages on the US Eastern date, numbers from
# "made-attempted" text, percentages from 0-100 to 0-1, season labels from end
# years, game tags from notes, the two-team season as one row, the team of the
# draft by name, the injury from the league report by athlete id and the next
# game of the player's team. It reads no clock and no source: the caller passes
# the time and the ids of the games that have a detail feed. The live block is
# added at serve time and stays null here. The feed kind that wires it to the
# cache is a later issue.
#
# SEE: docs/api/player.md, api/app/jobs/team_feed.py

import datetime as dt
import re
from collections.abc import Set as AbstractSet
from typing import Any

from pydantic import ValidationError

from app.feeds.game_detail import GameResult
from app.feeds.player import GameKind, PlayerFeed
from app.jobs.team_feed import (
    CM_PER_INCH,
    KG_PER_LB,
    age_on,
    eastern_date,
    game_kind_and_tag,
    next_game,
    season_label,
)
from app.sources.division_standings import DivisionStandings
from app.sources.league_injuries import LeagueInjuries
from app.sources.player_bio import PlayerBio, RankedValue
from app.sources.player_draft import DraftPick
from app.sources.player_gamelog import GameLogGame, PlayerGameLog
from app.sources.player_overview import ProviderAward
from app.sources.player_stats import MiscLine, PlayerStats, StatLine
from app.sources.team_players import Roster, RosterEntry
from app.sources.team_schedule import SeasonSchedule

LAST_GAMES = 5

_MADE_ATTEMPTED = re.compile(r"^(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)$")


class PlayerBuildError(Exception):
    """The player feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def made_attempted(text: str) -> tuple[float, float]:
    """Parse a "8-17" or "8.6-17.1" text into made and attempted."""
    match = _MADE_ATTEMPTED.match(text)
    if match is None:
        raise PlayerBuildError(f"shooting {text!r} is not made-attempted")
    return float(match[1]), float(match[2])


def percentage(value: float) -> float:
    """A percentage from 0 to 100 as a share from 0 to 1."""
    return round(value / 100, 3)


def height(inches: float, display: str | None) -> dict[str, Any]:
    """The height text and centimeters; feet and inches when no text is sent."""
    feet, rest = divmod(round(inches), 12)
    return {
        "display": display or f"{feet}' {rest}\"",
        "cm": round(inches * CM_PER_INCH),
    }


def weight(pounds: float) -> dict[str, int]:
    return {"lb": round(pounds), "kg": round(pounds * KG_PER_LB)}


def _shooting(line: StatLine) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for kind in ("field_goals", "three_points", "free_throws"):
        made, attempted = made_attempted(getattr(line, kind))
        values[f"{kind}_made"] = made
        values[f"{kind}_attempted"] = attempted
    for kind in ("field_goal", "three_point", "free_throw"):
        values[f"{kind}_pct"] = percentage(getattr(line, f"{kind}_pct"))
    return values


def stat_row(line: StatLine, played: StatLine | None = None) -> dict[str, Any]:
    """A stat row from a stat line. A totals line takes its games played and
    started from the per game line of the same season, and has no minutes."""
    source = played or line
    if source.games_played is None or source.games_started is None:
        raise PlayerBuildError("a stat row has no games played")
    return {
        "games_played": source.games_played,
        "games_started": source.games_started,
        "minutes": None if played else line.minutes,
        **_shooting(line),
        "offensive_rebounds": line.offensive_rebounds,
        "defensive_rebounds": line.defensive_rebounds,
        "rebounds": line.rebounds,
        "assists": line.assists,
        "blocks": line.blocks,
        "steals": line.steals,
        "fouls": line.fouls,
        "turnovers": line.turnovers,
        "points": line.points,
    }


def _season_row(line: StatLine, played: StatLine | None = None) -> dict[str, Any]:
    if line.season is None or not line.teams:
        raise PlayerBuildError("a season row has no season or team")
    return {
        **stat_row(line, played),
        "season": line.season,
        "teams": line.teams,
    }


def season_split(stats: PlayerStats) -> dict[str, Any]:
    """The per game and totals rows newest first, and the career rows."""
    per_game = sorted(stats.per_game, key=lambda line: line.season or "", reverse=True)
    played = {line.season: line for line in stats.per_game}
    totals = sorted(stats.totals, key=lambda line: line.season or "", reverse=True)
    career = None
    if stats.career_per_game is not None and stats.career_totals is not None:
        career = {
            "per_game": stat_row(stats.career_per_game),
            "totals": stat_row(stats.career_totals, stats.career_per_game),
        }
    rows = []
    for line in totals:
        if line.season not in played:
            raise PlayerBuildError(f"season {line.season} has no per game row")
        rows.append(_season_row(line, played[line.season]))
    return {
        "per_game": [_season_row(line) for line in per_game],
        "totals": rows,
        "career": career,
    }


def _average_row(line: StatLine) -> dict[str, Any]:
    return {
        "games_played": line.games_played,
        "minutes": line.minutes,
        "field_goal_pct": percentage(line.field_goal_pct),
        "three_point_pct": percentage(line.three_point_pct),
        "free_throw_pct": percentage(line.free_throw_pct),
        "rebounds": line.rebounds,
        "assists": line.assists,
        "blocks": line.blocks,
        "steals": line.steals,
        "fouls": line.fouls,
        "turnovers": line.turnovers,
        "points": line.points,
    }


def averages(regular: PlayerStats, playoffs: PlayerStats) -> dict[str, Any]:
    """The newest regular season, the playoffs of that same season and the
    career, each null when it has no games."""
    newest = max(regular.per_game, key=lambda line: line.season or "", default=None)
    season_playoffs = None
    if newest is not None:
        season_playoffs = next(
            (line for line in playoffs.per_game if line.season == newest.season), None
        )

    def row(line: StatLine | None, *, with_season: bool) -> dict[str, Any] | None:
        if line is None or not line.games_played:
            return None
        values = _average_row(line)
        return {**values, "season": line.season} if with_season else values

    return {
        "regular": row(newest, with_season=True),
        "playoffs": row(season_playoffs, with_season=True),
        "career": row(regular.career_per_game, with_season=False),
    }


def _counts(line: MiscLine) -> dict[str, Any]:
    return {
        "double_doubles": line.double_doubles,
        "triple_doubles": line.triple_doubles,
        "disqualifications": line.disqualifications,
        "ejections": line.ejections,
        "technicals": line.technicals,
        "flagrants": line.flagrants,
        "assist_turnover_ratio": line.assist_turnover_ratio,
        "steal_turnover_ratio": line.steal_turnover_ratio,
    }


def milestones(stats: PlayerStats) -> dict[str, Any] | None:
    """The newest regular season's counts and the career's; none without rows."""
    newest = max(stats.misc, key=lambda line: line.season or "", default=None)
    if newest is None or newest.season is None or stats.career_misc is None:
        return None
    return {
        "season": newest.season,
        "current": _counts(newest),
        "career": _counts(stats.career_misc),
    }


def _log_entry(game: GameLogGame, detail_ids: AbstractSet[str]) -> dict[str, Any]:
    kind, tag = game_kind_and_tag(game.note, game.playoffs)
    values: dict[str, Any] = {}
    for name in ("field_goals", "three_points", "free_throws"):
        made, attempted = made_attempted(getattr(game, name))
        values[f"{name}_made"] = int(made)
        values[f"{name}_attempted"] = int(attempted)
    for name in ("field_goal", "three_point", "free_throw"):
        values[f"{name}_pct"] = percentage(getattr(game, f"{name}_pct"))
    return {
        "game_id": game.game_id,
        "date": eastern_date(game.start_time),
        "opponent": game.opponent,
        "is_home": game.is_home,
        "kind": kind,
        "tag": tag,
        "result": GameResult.WIN if game.won else GameResult.LOSS,
        "team_score": game.team_score,
        "opponent_score": game.opponent_score,
        "minutes": int(float(game.minutes)),
        **values,
        "rebounds": game.rebounds,
        "assists": game.assists,
        "blocks": game.blocks,
        "steals": game.steals,
        "fouls": game.fouls,
        "turnovers": game.turnovers,
        "points": game.points,
        "detail_available": game.game_id in detail_ids,
    }


def game_log(
    log: PlayerGameLog, detail_ids: AbstractSet[str]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """The game log newest first, none without games, and the last five games
    that are not All-Star games."""
    if not log.games or log.season is None:
        return None, []
    games = sorted(log.games, key=lambda game: game.start_time, reverse=True)
    entries = [_log_entry(game, detail_ids) for game in games]
    recent = [e for e in entries if e["kind"] is not GameKind.ALLSTAR][:LAST_GAMES]
    return {"season": log.season, "entries": entries}, recent


def awards(provided: list[ProviderAward]) -> list[dict[str, Any]]:
    """The awards with their count and season labels; an award with no season
    is left out."""
    return [
        {
            "name": award.name,
            "count": int(award.display_count.removesuffix("x")),
            "seasons": [season_label(year) for year in award.seasons],
        }
        for award in provided
        if award.seasons
    ]


def player_injury(player_id: str, injuries: LeagueInjuries) -> dict[str, Any] | None:
    """The league report with the athlete id, none when it has no date."""
    for reports in injuries.teams.values():
        for report in reports:
            if report.player_id == player_id and report.updated_at is not None:
                return {
                    "status": report.injury.status,
                    "comment": report.injury.comment,
                    "updated_at": report.updated_at,
                }
    return None


def _ranked(value: RankedValue, *, share: bool = False) -> dict[str, Any]:
    return {
        "value": percentage(value.value) if share else round(value.value, 1),
        "rank": value.rank,
    }


def _summary(bio: PlayerBio | None) -> dict[str, Any] | None:
    if bio is None:
        return None
    return {
        "season": bio.season,
        "points": _ranked(bio.points),
        "rebounds": _ranked(bio.rebounds),
        "assists": _ranked(bio.assists),
        "field_goal_pct": _ranked(bio.field_goal_pct, share=True),
    }


def _birthplace(entry: RosterEntry) -> dict[str, Any] | None:
    if entry.birth_city is None:
        return None
    place = (
        f"{entry.birth_city}, {entry.birth_state}"
        if entry.birth_state
        else entry.birth_city
    )
    return {"place": place, "country": entry.birth_country}


def build_player_feed(
    player_id: str,
    team_code: str,
    roster: Roster,
    standings: DivisionStandings,
    injuries: LeagueInjuries,
    regular: SeasonSchedule,
    playoffs: SeasonSchedule,
    bio: PlayerBio | None,
    draft: DraftPick | None,
    provided_awards: list[ProviderAward],
    log: PlayerGameLog,
    regular_stats: PlayerStats,
    playoff_stats: PlayerStats,
    *,
    now: dt.datetime,
    detail_ids: AbstractSet[str],
) -> PlayerFeed:
    """Build the player feed from the fetched data, or raise PlayerBuildError."""
    entry = next((p for p in roster.entries if p.player_id == player_id), None)
    if entry is None:
        raise PlayerBuildError(f"player {player_id} is not on the roster")
    if entry.position_name is None:
        raise PlayerBuildError(f"player {player_id} has no position")
    team = standings.teams.get(team_code)
    if team is None:
        raise PlayerBuildError(f"team {team_code} has no standing")
    drafted = None
    if draft is not None:
        drafting = standings.teams.get(draft.team_code)
        if drafting is None:
            raise PlayerBuildError(f"team {draft.team_code} has no standing")
        drafted = {
            "year": draft.year,
            "round": draft.round,
            "pick": draft.pick,
            "team_name": drafting.display_name,
        }
    ids = frozenset(detail_ids)
    seasons = {
        "regular": season_split(regular_stats),
        "playoffs": season_split(playoff_stats),
    }
    rows = seasons["regular"]["per_game"]
    log_feed, recent = game_log(log, ids)
    try:
        return PlayerFeed.model_validate(
            {
                "id": entry.player_id,
                "first_name": entry.first_name,
                "last_name": entry.last_name,
                "number": entry.jersey,
                "position": entry.position_name,
                "team": {
                    "code": team_code,
                    "name": team.name,
                    "city": team.location,
                },
                "photo_url": entry.headshot_url,
                "injury": player_injury(player_id, injuries),
                "profile": {
                    "height": height(entry.height_inches, entry.display_height)
                    if entry.height_inches
                    else None,
                    "weight": weight(entry.weight_lb) if entry.weight_lb else None,
                    "birth_date": entry.birth_date,
                    "age": age_on(entry.birth_date, eastern_date(now))
                    if entry.birth_date
                    else None,
                    "birthplace": _birthplace(entry),
                    "college": entry.college,
                    "draft": drafted,
                    "seasons": len(rows) if rows else None,
                    "debut_season": rows[-1]["season"] if rows else None,
                },
                "summary": _summary(bio),
                "next_game": next_game(regular, playoffs, ids),
                "live": None,
                "last_games": recent,
                "averages": averages(regular_stats, playoff_stats),
                "seasons": seasons,
                "milestones": milestones(regular_stats),
                "game_log": log_feed,
                "awards": awards(provided_awards),
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise PlayerBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None
