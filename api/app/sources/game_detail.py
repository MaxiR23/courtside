# api/app/sources/game_detail.py
#
# Game detail adapter: fetches one game's box score from the provider and
# maps it to the contract's leaders and team stats. It also maps the full
# game detail sections: venue, box score, team stats, win probability and
# its period boundaries, injuries and season series. The provider URLs come from Settings.
# Provider data never leaves this module.
#
# The past path (ADR 0041) reads the sections of a final game of a past day:
# sides by team id first, no injuries or season series, and the event's season.
# It also carries the leader of each side, by the rule of ADR 0009 (ADR 0057);
# the current sections never do.
#
# A team is matched to its box score players by id when both sides send one,
# else by abbreviation. A team without an abbreviation is resolved by id or is a
# guest without a code (ADR 0026). Stat and win probability leaders are sides.
#
# fetch_past_game_players reads the same summary for the players of a final
# game of a past season (ADR 0053): for each league side, the players with a
# stat line, with the jersey and the position of that game's box score, leniently
# read (a missing key or a jersey that is not one or two digits is null).
#
# Reading rules for the box score (ADR 0052, ADR 0055). Team turnovers are the
# team's totalTurnovers when the provider sends it, else turnovers. A team
# percentage the provider does not send is null. When every player of both
# teams has a plus-minus of 0, the provider sent none, so every plus-minus is
# null. A team or player stat the provider does not send is null, never a
# failure; a value that is sent and is not a number still fails. A box score row
# with no player id is skipped and logged once, in every reader.
#
# SEE: docs/api/games.md, docs/adr/0041-past-game-detail.md,
# docs/adr/0052-box-score-reading.md, docs/adr/0055-past-season-reading-rules-and-versioned-stored-data.md, docs/adr/0053-season-level-rules-for-past-seasons.md, api/app/sources/scoreboard.py

import datetime as dt
import logging
import re
from collections.abc import Sequence
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    ValidationError,
)
from pydantic.alias_generators import to_camel

from app.feeds.game_detail import (
    BoxScore,
    DetailGameTeamStats,
    Injuries,
    InjuryStatus,
    Venue,
    WinProbabilityLeader,
    WinProbabilityPeriods,
    WinProbabilityPoint,
)
from app.feeds.games import (
    FeedModel,
    GameTeamStats,
    Leaders,
    NonEmptyStr,
    Score,
    TeamCode,
)
from app.feeds.opponent import Side
from app.feeds.player import JerseyNumber
from app.settings import Settings
from app.sources.http import Freshness, SourceClient, SourceError, get_json
from app.sources.teams import TEAM_CODES, TEAM_IDS, side_of, to_team_code

logger = logging.getLogger(__name__)

SOURCE = "game_detail"
EASTERN = ZoneInfo("America/New_York")
PERCENT_STATS = {
    "field_goal_pct": "fieldGoalPct",
    "three_point_pct": "threePointFieldGoalPct",
}
COUNT_STATS = {
    "rebounds": "totalRebounds",
    "assists": "assists",
    "turnovers": "turnovers",
}
# Team stat rows of the detail feed, by provider stat name. The first three
# are percentages, which the contract holds as fractions.
STAT_ROWS = {
    "field_goal_pct": "fieldGoalPct",
    "three_point_pct": "threePointFieldGoalPct",
    "free_throw_pct": "freeThrowPct",
    "rebounds": "totalRebounds",
    "assists": "assists",
    "turnovers": "turnovers",
    "steals": "steals",
    "blocks": "blocks",
}
PERCENT_ROWS = {"field_goal_pct", "three_point_pct", "free_throw_pct"}
TOTAL_TURNOVERS = "totalTurnovers"


class _ProviderModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, validate_by_name=True
    )


class _ProviderTeamRef(_ProviderModel):
    abbreviation: str | None = None
    id: str | None = None


def _same_team(a: _ProviderTeamRef, b: _ProviderTeamRef) -> bool:
    # Equal ids when both are sent, else equal abbreviations when both are sent.
    if a.id and b.id:
        return a.id == b.id
    return bool(a.abbreviation) and a.abbreviation == b.abbreviation


def _team_name(team: _ProviderTeamRef) -> str:
    return team.abbreviation or team.id or "an unnamed team"


class _ProviderStatistic(_ProviderModel):
    name: str
    display_value: str


class _ProviderBoxTeam(_ProviderModel):
    home_away: str
    team: _ProviderTeamRef
    statistics: list[_ProviderStatistic]


class _ProviderHeadshot(_ProviderModel):
    href: str


class _ProviderAthlete(_ProviderModel):
    # A row with no id is skipped by every reader (ADR 0055); a row with an id
    # and no name fails when the feed validates it.
    id: str | None = None
    display_name: str | None = None
    headshot: _ProviderHeadshot | None = None


class _ProviderAthleteLine(_ProviderModel):
    # A row with no athlete object reads as an athlete with no id: skipped.
    athlete: _ProviderAthlete = _ProviderAthlete()
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


def _number(game_id: str, value: str, kind: type[int | float]) -> Any:
    try:
        return kind(value)
    except ValueError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat that is not a number"
        ) from None


def _with_player_id[L: (_ProviderAthleteLine, _SummaryAthleteLine, _PlayersLine)](
    game_id: str, lines: Sequence[L]
) -> list[L]:
    # Rule: ADR 0055. A box score row with no player id is skipped and logged.
    kept = []
    for line in lines:
        if not line.athlete.id:
            logger.warning(
                "game detail: game %s has a box score row with no player id, skipped",
                game_id,
            )
            continue
        kept.append(line)
    return kept


def _photo(athlete: _ProviderAthlete, photo_url: str, guest: bool) -> str | None:
    # A league player's photo comes from the template; a guest player has only
    # the box score headshot, if any.
    if guest:
        return athlete.headshot.href if athlete.headshot else None
    return photo_url.format(player_id=athlete.id)


def _leader[P: (_ProviderBoxPlayers, _SummaryBoxPlayers)](
    game_id: str,
    code: str | None,
    players: P,
    photo_url: str,
    guest: bool,
) -> dict[str, Any]:
    label = code or "a guest side"
    if not players.statistics:
        raise SourceError(SOURCE, f"game {game_id} has no player stats for {label}")
    group = players.statistics[0]
    # Rule: ADR 0055. A column the provider does not send is a null value.
    columns: dict[str, int | None] = {
        key: group.keys.index(key) if key in group.keys else None
        for key in ("points", "rebounds", "assists")
    }
    played = [line for line in _with_player_id(game_id, group.athletes) if line.stats]
    if not played:
        raise SourceError(SOURCE, f"game {game_id} has no player stats for {label}")
    try:
        values = [
            {
                key: None if i is None else _number(game_id, line.stats[i], int)
                for key, i in columns.items()
            }
            for line in played
        ]
    except IndexError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat line shorter than its columns"
        ) from None
    # Rule: docs/adr/0009-game-leader-selection.md. max keeps the first on a full
    # tie. A missing value counts as 0 for the order only (ADR 0055).
    top = max(
        range(len(played)),
        key=lambda i: (
            values[i]["points"] or 0,
            (values[i]["rebounds"] or 0) + (values[i]["assists"] or 0),
        ),
    )
    athlete = played[top].athlete
    return {
        "player_id": athlete.id,
        "display_name": athlete.display_name,
        "team_code": code,
        "photo_url": _photo(athlete, photo_url, guest),
        **values[top],
    }


def _without_unidentified_rows(players: _SummaryBoxPlayers) -> _SummaryBoxPlayers:
    # The box score already skipped and logged the rows with no player id
    # (ADR 0055): the leader reads the same rows without logging them again.
    first, *rest = players.statistics
    kept = first.model_copy(
        update={"athletes": [line for line in first.athletes if line.athlete.id]}
    )
    return players.model_copy(update={"statistics": [kept, *rest]})


def _has_leader(players: _SummaryBoxPlayers) -> bool:
    # The two cases where _leader raises: no stat group, no row with stats.
    return bool(players.statistics) and any(
        line.athlete.id and line.stats for line in players.statistics[0].athletes
    )


def _past_leaders(
    game_id: str,
    sides: dict[str, _ProviderBoxTeam],
    resolved: dict[str, tuple[str | None, bool]],
    guests: dict[str, bool],
    box_players: list[_SummaryBoxPlayers],
    photo_url: str,
) -> dict[str, Any] | None:
    # Rule: ADR 0057. A side without a stat line leaves the leaders null; the
    # build does not fail for it.
    by_side: dict[str, _SummaryBoxPlayers] = {}
    for side, team in sides.items():
        players = next((p for p in box_players if _same_team(p.team, team.team)), None)
        if players is None or not _has_leader(players):
            return None
        by_side[side] = _without_unidentified_rows(players)
    return {
        side: _leader(
            game_id, resolved[side][0], by_side[side], photo_url, guests[side]
        )
        for side in sides
    }


def _turnovers_stat(by_name: dict[str, str]) -> str:
    # Rule: ADR 0052. totalTurnovers counts the team's turnovers too.
    return TOTAL_TURNOVERS if TOTAL_TURNOVERS in by_name else "turnovers"


def _percent(game_id: str, by_name: dict[str, str], name: str) -> float | None:
    # Rule: ADR 0052. A percentage the provider does not send is null.
    if name not in by_name:
        return None
    value: float = _number(game_id, by_name[name], float)
    return value / 100


def _team_stats(game_id: str, team: _ProviderBoxTeam) -> dict[str, Any]:
    by_name = {stat.name: stat.display_value for stat in team.statistics}

    stats: dict[str, Any] = {}
    for field, name in PERCENT_STATS.items():
        stats[field] = _percent(game_id, by_name, name)
    for field, name in COUNT_STATS.items():
        if field == "turnovers":
            name = _turnovers_stat(by_name)
        # Rule: ADR 0055. A count the provider does not send is null.
        stats[field] = _number(game_id, by_name[name], int) if name in by_name else None
    return stats


async def fetch_game_detail(
    client: SourceClient,
    game_id: str,
    settings: Settings,
    fresh: Freshness,
    *,
    by_id_first: bool = False,
) -> GameDetail:
    """Return the leaders and team stats of one game, or raise SourceError.
    With by_id_first each side resolves by provider id first (a past game).

    `fresh` is the freshness of the game's state: 30 seconds live, the
    attempt's due time final, 1 hour otherwise."""
    if settings.game_detail_url is None:
        raise SourceError(SOURCE, "game detail URL is not configured")
    if settings.player_photo_url is None:
        raise SourceError(SOURCE, "player photo URL is not configured")
    url = settings.game_detail_url.format(game_id=game_id)
    body = await get_json(client, url, source=SOURCE, fresh=fresh)
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
        code, guest = _resolve_side(team, past=by_id_first)
        players = next((p for p in box.players if _same_team(p.team, team.team)), None)
        if players is None:
            raise SourceError(
                SOURCE, f"game {game_id} has no players for {_team_name(team.team)}"
            )
        leaders[side] = _leader(
            game_id, code, players, settings.player_photo_url, guest
        )
        team_stats[side] = _team_stats(game_id, team)

    try:
        return GameDetail.model_validate({"leaders": leaders, "team_stats": team_stats})
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {game_id} is invalid: {first['type']} at {location}"
        ) from None


class _SummaryPeriods(_ProviderModel):
    periods: PositiveInt
    clock: float


class _SummaryOvertime(_ProviderModel):
    clock: float


class _SummaryFormat(_ProviderModel):
    regulation: _SummaryPeriods
    overtime: _SummaryOvertime


class _SummaryAddress(_ProviderModel):
    city: str | None = None


class _SummaryImage(_ProviderModel):
    href: str


class _SummaryVenue(_ProviderModel):
    full_name: str
    address: _SummaryAddress | None = None
    images: list[_SummaryImage] = []


class _SummaryGameInfo(_ProviderModel):
    venue: _SummaryVenue


class _SummaryAthleteLine(_ProviderModel):
    athlete: _ProviderAthlete = _ProviderAthlete()
    starter: bool
    stats: list[str]


class _SummaryStatGroup(_ProviderModel):
    keys: list[str]
    totals: list[str]
    athletes: list[_SummaryAthleteLine]


class _SummaryBoxPlayers(_ProviderModel):
    team: _ProviderTeamRef
    statistics: list[_SummaryStatGroup]


class _SummaryBoxscore(_ProviderModel):
    teams: list[_ProviderBoxTeam]
    players: list[_SummaryBoxPlayers] = []


class _SummaryPlayPeriod(_ProviderModel):
    number: int


class _SummaryPlayClock(_ProviderModel):
    display_value: str


class _SummaryPlay(_ProviderModel):
    id: str
    period: _SummaryPlayPeriod
    clock: _SummaryPlayClock


class _SummaryWinProbability(_ProviderModel):
    play_id: str
    home_win_percentage: float


class _SummaryInjuryAthlete(_ProviderModel):
    display_name: str


class _SummaryInjuryEntry(_ProviderModel):
    status: str
    athlete: _SummaryInjuryAthlete


class _SummaryTeamInjuries(_ProviderModel):
    team: _ProviderTeamRef
    injuries: list[_SummaryInjuryEntry]


class _SummaryCompetitor(_ProviderModel):
    home_away: str
    team: _ProviderTeamRef
    score: str
    winner: bool = False


class _SummarySeriesEvent(_ProviderModel):
    id: str
    date: AwareDatetime
    status: str
    competitors: list[_SummaryCompetitor]


class _SummarySeries(_ProviderModel):
    type: str
    total_competitions: PositiveInt
    events: list[_SummarySeriesEvent] = []


class _SummarySeason(_ProviderModel):
    year: int | None = None


class _SummaryHeader(_ProviderModel):
    season: _SummarySeason | None = None


class _ProviderSummary(_ProviderModel):
    # The header is read apart and leniently: an unexpected shape is no season,
    # never a failed read.
    header: Any = None
    format: _SummaryFormat
    game_info: _SummaryGameInfo
    boxscore: _SummaryBoxscore
    plays: list[_SummaryPlay] = []
    winprobability: list[_SummaryWinProbability] = []
    injuries: list[_SummaryTeamInjuries] = []
    seasonseries: list[_SummarySeries] = []


class SeriesMeeting(FeedModel):
    """A game of the season series: a completed game, or this game whatever
    its status. Without its arena: the provider does not send it here. The job
    takes it from the team schedule by game id."""

    game_id: NonEmptyStr
    date: dt.date
    away: TeamCode
    home: TeamCode
    is_current: bool
    score: Score | None
    winner: TeamCode | None


class SeriesMeetings(FeedModel):
    total_games: PositiveInt
    away_wins: NonNegativeInt
    home_wins: NonNegativeInt
    leader: TeamCode | None
    games: list[SeriesMeeting]


class GameDetailSections(FeedModel):
    """A game's detail sections as the game summary knows them, and the event's
    season end year when the summary gives it."""

    venue: Venue
    team_stats: DetailGameTeamStats | None = None
    box_score: BoxScore | None = None
    win_probability: (
        Annotated[list[WinProbabilityPoint], Field(min_length=1)] | None
    ) = None
    win_probability_leader: WinProbabilityLeader | None = None
    win_probability_periods: WinProbabilityPeriods | None = None
    injuries: Injuries | None = None
    season_series: SeriesMeetings | None = None
    season: PositiveInt | None = None
    # The leader of each side by the rule of ADR 0009; set by the past sections
    # only (ADR 0057).
    leaders: Leaders | None = None


def _stat_leader(
    row: str,
    away_value: float | None,
    home_value: float | None,
) -> Side | None:
    # Rule: docs/api/game-detail.md. A tie has no leader; turnovers go to the lower.
    # A value the provider did not send gives no leader.
    if away_value is None or home_value is None or away_value == home_value:
        return None
    away_leads = (
        away_value < home_value if row == "turnovers" else away_value > home_value
    )
    return Side.AWAY if away_leads else Side.HOME


def _period_length(period: int, fmt: _SummaryFormat) -> float:
    # Periods 1..regulation.periods last regulation.clock seconds, later ones
    # overtime.clock.
    regulation = fmt.regulation
    return regulation.clock if period <= regulation.periods else fmt.overtime.clock


def _period_start(period: int, fmt: _SummaryFormat) -> float:
    # Elapsed game seconds at the start of the period.
    return sum(_period_length(n, fmt) for n in range(1, period))


def _elapsed_seconds(period: int, clock: str, fmt: _SummaryFormat) -> int | None:
    # clock is the time remaining, "MM:SS" or "S.s". Periods 1..regulation.periods
    # last regulation.clock seconds, later ones overtime.clock.
    if period < 1:
        return None
    length = _period_length(period, fmt)
    try:
        if ":" in clock:
            minutes, seconds = clock.split(":")
            remaining = int(minutes) * 60 + float(seconds)
        else:
            remaining = float(clock)
    except ValueError:
        return None
    if not 0 <= remaining <= length:
        return None
    return int(_period_start(period, fmt) + length - remaining)


def _made_attempted(game_id: str, value: str) -> tuple[int, int]:
    parts = value.split("-")
    if len(parts) != 2:
        raise SourceError(SOURCE, f"game {game_id} has a stat that is not a number")
    return _number(game_id, parts[0], int), _number(game_id, parts[1], int)


BOX_COLUMNS = (
    "points",
    "rebounds",
    "assists",
    "turnovers",
    "steals",
    "blocks",
    "offensiveRebounds",
    "defensiveRebounds",
    "fouls",
)
BOX_SHOTS = {
    "field_goals": "fieldGoalsMade-fieldGoalsAttempted",
    "three_points": "threePointFieldGoalsMade-threePointFieldGoalsAttempted",
    "free_throws": "freeThrowsMade-freeThrowsAttempted",
}
BOX_FIELDS = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "turnovers": "turnovers",
    "steals": "steals",
    "blocks": "blocks",
    "offensive_rebounds": "offensiveRebounds",
    "defensive_rebounds": "defensiveRebounds",
    "fouls": "fouls",
}


def _box_line(
    game_id: str, keys: list[str], values: list[str], wanted: tuple[str, ...]
) -> dict[str, Any]:
    # Rule: ADR 0055. A column the provider does not send is a null value.
    try:
        by_key = {
            key: values[keys.index(key)] if key in keys else None for key in wanted
        }
    except IndexError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat line shorter than its columns"
        ) from None
    line: dict[str, Any] = {}
    for field, key in BOX_FIELDS.items():
        value = by_key[key]
        line[field] = None if value is None else _number(game_id, value, int)
    for field, key in BOX_SHOTS.items():
        shot = by_key[key]
        made, attempted = (
            (None, None) if shot is None else _made_attempted(game_id, shot)
        )
        line[f"{field}_made"] = made
        line[f"{field}_attempted"] = attempted
    return line


def _team_box_score(
    game_id: str,
    team: _ProviderBoxTeam,
    players: _SummaryBoxPlayers,
    photo_url: str,
    guest: bool,
) -> dict[str, Any]:
    if not players.statistics:
        raise SourceError(
            SOURCE, f"game {game_id} has no player stats for {_team_name(team.team)}"
        )
    group = players.statistics[0]
    wanted = (*BOX_COLUMNS, *BOX_SHOTS.values())
    lines = []
    for line in _with_player_id(game_id, group.athletes):
        if not line.stats:
            continue
        values = _box_line(game_id, group.keys, line.stats, wanted)
        try:
            minutes = (
                line.stats[group.keys.index("minutes")]
                if "minutes" in group.keys
                else None
            )
            plus_minus = (
                line.stats[group.keys.index("plusMinus")]
                if "plusMinus" in group.keys
                else None
            )
        except IndexError:
            raise SourceError(
                SOURCE, f"game {game_id} has a stat line shorter than its columns"
            ) from None
        lines.append(
            {
                "player_id": line.athlete.id,
                "display_name": line.athlete.display_name,
                "starter": line.starter,
                "minutes": minutes,
                "plus_minus": (
                    None if plus_minus is None else _number(game_id, plus_minus, int)
                ),
                "photo_url": _photo(line.athlete, photo_url, guest),
                **values,
            }
        )
    by_name = {stat.name: stat.display_value for stat in team.statistics}
    totals = _box_line(game_id, group.keys, group.totals, wanted)
    for field in ("field_goal_pct", "three_point_pct", "free_throw_pct"):
        totals[field] = _percent(game_id, by_name, STAT_ROWS[field])
    if TOTAL_TURNOVERS in by_name:
        totals["turnovers"] = _number(game_id, by_name[TOTAL_TURNOVERS], int)
    return {"players": lines, "totals": totals}


def _detail_team_stats(game_id: str, team: _ProviderBoxTeam) -> dict[str, Any]:
    by_name = {stat.name: stat.display_value for stat in team.statistics}
    stats: dict[str, Any] = {}
    for field, name in STAT_ROWS.items():
        if field in PERCENT_ROWS:
            stats[field] = _percent(game_id, by_name, name)
            continue
        if field == "turnovers":
            name = _turnovers_stat(by_name)
        # Rule: ADR 0055. A count the provider does not send is null.
        stats[field] = _number(game_id, by_name[name], int) if name in by_name else None
    return stats


def _without_plus_minus(box_score: dict[str, Any]) -> None:
    # Rule: ADR 0052. A game whose players all have a plus-minus of 0 came
    # without one from the provider, so no row carries it.
    lines = [line for side in ("away", "home") for line in box_score[side]["players"]]
    sent = [line["plus_minus"] for line in lines if line["plus_minus"] is not None]
    if sent and all(value == 0 for value in sent):
        for line in lines:
            line["plus_minus"] = None


def _win_probability(summary: _ProviderSummary) -> list[dict[str, Any]]:
    plays = {play.id: play for play in summary.plays}
    points = []
    for entry in summary.winprobability:
        play = plays.get(entry.play_id)
        if play is None:
            continue
        elapsed = _elapsed_seconds(
            play.period.number, play.clock.display_value, summary.format
        )
        if elapsed is None:
            continue
        points.append(
            {
                "elapsed_seconds": elapsed,
                "home_win_probability": entry.home_win_percentage,
            }
        )
    # Game time order; sorted is stable, so points at the same second keep the
    # source order. Rule: docs/api/game-detail.md.
    return sorted(points, key=lambda point: point["elapsed_seconds"])


def _win_probability_leader(points: list[dict[str, Any]]) -> dict[str, Any] | None:
    # Rule: docs/api/game-detail.md. The side ahead at the last published
    # point; none when it is exactly even.
    if not points:
        return None
    latest = points[-1]["home_win_probability"]
    if latest > 0.5:
        return {"side": Side.HOME, "win_probability": latest}
    if latest < 0.5:
        return {"side": Side.AWAY, "win_probability": 1 - latest}
    return None


def _win_probability_periods(summary: _ProviderSummary) -> dict[str, Any]:
    # Lengths come from the game format; the count comes from the plays' period
    # numbers, with the regulation count as the minimum.
    fmt = summary.format
    played = max((play.period.number for play in summary.plays), default=0)
    count = max(fmt.regulation.periods, played)
    return {
        "periods": [
            {"number": n, "start_elapsed_seconds": int(_period_start(n, fmt))}
            for n in range(1, count + 1)
        ],
        "end_elapsed_seconds": int(_period_start(count + 1, fmt)),
    }


def _injuries(
    game_id: str, summary: _ProviderSummary, abbreviations: dict[str, str | None]
) -> dict[str, list[dict[str, Any]]]:
    injuries: dict[str, list[dict[str, Any]]] = {}
    for side, abbreviation in abbreviations.items():
        listed: list[dict[str, Any]] = []
        for entry in summary.injuries:
            # A side without a code lists nothing (ADR 0026).
            if abbreviation is None or entry.team.abbreviation != abbreviation:
                continue
            for injury in entry.injuries:
                try:
                    status = InjuryStatus(injury.status.lower())
                except ValueError:
                    raise SourceError(
                        SOURCE, f"game {game_id} has an unknown injury status"
                    ) from None
                listed.append(
                    {
                        "display_name": injury.athlete.display_name,
                        "status": status,
                        "comment": None,
                    }
                )
        injuries[side] = listed
    return injuries


def _season_series(
    game_id: str, summary: _ProviderSummary, codes: dict[str, str]
) -> dict[str, Any] | None:
    series = next((s for s in summary.seasonseries if s.type == "season"), None)
    if series is None:
        return None
    games: list[dict[str, Any]] = []
    wins = {code: 0 for code in codes.values()}
    for event in series.events:
        is_current = event.id == game_id
        completed = event.status == "post"
        if not completed and not is_current:
            continue
        sides = {c.home_away: c for c in event.competitors}
        if set(sides) != {"home", "away"} or len(event.competitors) != 2:
            raise SourceError(
                SOURCE,
                f"game {game_id} has a series game without one home and one away team",
            )
        away = to_team_code(sides["away"].team.abbreviation or "", source=SOURCE)
        home = to_team_code(sides["home"].team.abbreviation or "", source=SOURCE)
        if {away, home} != set(codes.values()):
            raise SourceError(
                SOURCE, f"game {game_id} has a series game of other teams"
            )
        winner: str | None = None
        score: dict[str, int] | None = None
        if completed:
            winners = [
                code
                for competitor, code in ((sides["away"], away), (sides["home"], home))
                if competitor.winner
            ]
            if len(winners) != 1:
                raise SourceError(
                    SOURCE, f"game {game_id} has a series game without one winner"
                )
            winner = winners[0]
            wins[winner] += 1
            score = {
                "away": _number(game_id, sides["away"].score, int),
                "home": _number(game_id, sides["home"].score, int),
            }
        games.append(
            {
                "game_id": event.id,
                "date": event.date.astimezone(EASTERN).date(),
                "away": away,
                "home": home,
                "is_current": is_current,
                "score": score,
                "winner": winner,
            }
        )
    away_wins, home_wins = wins[codes["away"]], wins[codes["home"]]
    leader = (
        codes["away"]
        if away_wins > home_wins
        else codes["home"]
        if home_wins > away_wins
        else None
    )
    return {
        "total_games": series.total_competitions,
        "away_wins": away_wins,
        "home_wins": home_wins,
        "leader": leader,
        "games": games,
    }


def _season(summary: _ProviderSummary) -> int | None:
    # The season end year (2005 for 2004-05), or None when the summary has no
    # readable one. Never raises.
    try:
        header = _SummaryHeader.model_validate(summary.header)
    except ValidationError:
        return None
    year = header.season.year if header.season else None
    return year if year is not None and year > 0 else None


async def fetch_game_detail_sections(
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> GameDetailSections:
    """Return the detail sections of one game, or raise SourceError.

    `fresh` is the freshness of the game's state: 30 seconds live, the
    attempt's due time final, 1 hour otherwise."""
    return await _fetch_sections(client, game_id, settings, fresh, past=False)


async def fetch_past_game_detail_sections(
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> GameDetailSections:
    """The detail sections of a final game of a past day (ADR 0041): sides by
    team id first, as the past day's scoreboard (ADR 0040), and no injuries
    or season series, which a past game never shows. Raises SourceError."""
    return await _fetch_sections(client, game_id, settings, fresh, past=True)


def _resolve_ref(ref: _ProviderTeamRef, *, past: bool) -> tuple[str | None, bool]:
    # A past game's team id of the 30 wins over the abbreviation, which may be
    # a historical one (ADR 0040).
    if past and ref.id in TEAM_IDS:
        return TEAM_CODES[TEAM_IDS[ref.id]], False
    return side_of(ref.abbreviation, ref.id, source=SOURCE)


def _resolve_side(team: _ProviderBoxTeam, *, past: bool) -> tuple[str | None, bool]:
    return _resolve_ref(team.team, past=past)


async def _fetch_sections(
    client: SourceClient,
    game_id: str,
    settings: Settings,
    fresh: Freshness,
    *,
    past: bool,
) -> GameDetailSections:
    if settings.game_detail_url is None:
        raise SourceError(SOURCE, "game detail URL is not configured")
    if settings.player_photo_url is None:
        raise SourceError(SOURCE, "player photo URL is not configured")
    url = settings.game_detail_url.format(game_id=game_id)
    body = await get_json(client, url, source=SOURCE, fresh=fresh)
    try:
        summary = _ProviderSummary.model_validate(body)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None

    box = summary.boxscore
    sides = {team.home_away: team for team in box.teams}
    if set(sides) != {"home", "away"} or len(box.teams) != 2:
        raise SourceError(SOURCE, f"game {game_id} needs one home and one away team")
    abbreviations = {side: team.team.abbreviation for side, team in sides.items()}
    resolved = {side: _resolve_side(team, past=past) for side, team in sides.items()}
    guests = {side: guest for side, (_, guest) in resolved.items()}

    venue = summary.game_info.venue
    sections: dict[str, Any] = {
        "venue": {
            "name": venue.full_name,
            "city": venue.address.city if venue.address else None,
            "photo_url": venue.images[0].href if venue.images else None,
        }
    }

    if box.players:
        box_score: dict[str, Any] = {}
        team_stats: dict[str, Any] = {}
        for side, team in sides.items():
            players = next(
                (p for p in box.players if _same_team(p.team, team.team)), None
            )
            if players is None:
                raise SourceError(
                    SOURCE,
                    f"game {game_id} has no players for {_team_name(team.team)}",
                )
            box_score[side] = _team_box_score(
                game_id, team, players, settings.player_photo_url, guests[side]
            )
            team_stats[side] = _detail_team_stats(game_id, team)
        team_stats["leaders"] = {
            row: _stat_leader(
                row,
                team_stats["away"][row],
                team_stats["home"][row],
            )
            for row in STAT_ROWS
        }
        _without_plus_minus(box_score)
        sections["box_score"] = box_score
        sections["team_stats"] = team_stats
        if past:
            sections["leaders"] = _past_leaders(
                game_id, sides, resolved, guests, box.players, settings.player_photo_url
            )

    points = _win_probability(summary)
    sections["win_probability"] = points or None
    sections["win_probability_leader"] = _win_probability_leader(points)
    sections["win_probability_periods"] = (
        _win_probability_periods(summary) if points else None
    )
    sections["season"] = _season(summary)
    if not past:
        if summary.injuries:
            sections["injuries"] = _injuries(game_id, summary, abbreviations)
        # A guest game has no season series (ADR 0025).
        sections["season_series"] = (
            None
            if any(guests.values())
            else _season_series(
                game_id,
                summary,
                {
                    side: code
                    for side, (code, _) in resolved.items()
                    if code is not None
                },
            )
        )

    try:
        return GameDetailSections.model_validate(sections)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {game_id} is invalid: {first['type']} at {location}"
        ) from None


class BoxScoreRosterEntry(FeedModel):
    """A player with a stat line in the box score of one past game. Never reaches
    a feed."""

    player_id: NonEmptyStr
    display_name: NonEmptyStr
    jersey: JerseyNumber | None
    position_abbreviation: NonEmptyStr | None
    headshot_url: NonEmptyStr | None
    # Start of the newest final game of the season the player played for the
    # team; set by the past playoffs build only, so stored GamePlayers bodies still validate.
    last_played: dt.datetime | None = None


class GamePlayers(FeedModel):
    """The players of a past game by standard team code, league sides only."""

    teams: dict[str, list[BoxScoreRosterEntry]]
    # The rules version of the stored body (ADR 0053, ADR 0055); null on a body
    # from before the field.
    build_version: PositiveInt | None = None


class _PlayersPosition(_ProviderModel):
    abbreviation: str | None = None


class _PlayersAthlete(_ProviderAthlete):
    jersey: str | None = None
    position: _PlayersPosition | None = None


class _PlayersLine(_ProviderModel):
    athlete: _PlayersAthlete = _PlayersAthlete()
    stats: list[str] = []


class _PlayersGroup(_ProviderModel):
    athletes: list[_PlayersLine] = []


class _PlayersBox(_ProviderModel):
    team: _ProviderTeamRef
    statistics: list[_PlayersGroup] = []


class _PlayersTeam(_ProviderModel):
    team: _ProviderTeamRef


class _PlayersBoxscore(_ProviderModel):
    teams: list[_PlayersTeam] = []
    players: list[_PlayersBox] = []


class _PlayersSummary(_ProviderModel):
    boxscore: _PlayersBoxscore


_JERSEY = re.compile(r"\d{1,2}")


async def fetch_past_game_players(
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> GamePlayers:
    """The players with a stat line of each league side of a final game of a past
    season, with the jersey and position of its box score (ADR 0053), or raise
    SourceError. A summary without box score players gives no teams."""
    if settings.game_detail_url is None:
        raise SourceError(SOURCE, "game detail URL is not configured")
    if settings.player_photo_url is None:
        raise SourceError(SOURCE, "player photo URL is not configured")
    url = settings.game_detail_url.format(game_id=game_id)
    body = await get_json(client, url, source=SOURCE, fresh=fresh)
    try:
        summary = _PlayersSummary.model_validate(body)
        teams: dict[str, list[BoxScoreRosterEntry]] = {}
        for side in summary.boxscore.teams:
            code, guest = _resolve_ref(side.team, past=True)
            players = next(
                (p for p in summary.boxscore.players if _same_team(p.team, side.team)),
                None,
            )
            if guest or code is None or players is None or not players.statistics:
                continue
            teams[code] = [
                BoxScoreRosterEntry.model_validate(
                    {
                        "player_id": line.athlete.id,
                        "display_name": line.athlete.display_name,
                        "jersey": (
                            line.athlete.jersey
                            if line.athlete.jersey
                            and _JERSEY.fullmatch(line.athlete.jersey)
                            else None
                        ),
                        "position_abbreviation": (
                            line.athlete.position.abbreviation or None
                            if line.athlete.position
                            else None
                        ),
                        "headshot_url": _photo(
                            line.athlete, settings.player_photo_url, guest=False
                        ),
                    }
                )
                for line in _with_player_id(game_id, players.statistics[0].athletes)
                if line.stats
            ]
        return GamePlayers(teams=teams)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE,
            f"invalid payload: {error.error_count()} errors, first at {location}",
        ) from None
