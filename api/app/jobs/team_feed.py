# api/app/jobs/team_feed.py
#
# Team feed builder: a pure function from the data the source adapters fetched
# to the team feed, with every conversion the contract needs: win percentages,
# records, streak, playoff status by seed, ranks, season labels, game tags from
# notes, ages on the US Eastern date, leaders matched to the roster, roster
# status from the league injuries, the next game and the schedule grouped by
# US Eastern month with the playoffs last. It reads no clock and no source: the
# caller passes the time and the ids of the games that have a detail feed. The
# shared conversions are used by the player feed builder too. The feed kind that
# wires it to the cache is a later issue.
#
# SEE: docs/api/team.md, docs/api/player.md, api/app/jobs/game_detail_feed.py

import datetime as dt
import re
from collections.abc import Iterable
from collections.abc import Set as AbstractSet
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.feeds.game_detail import Conference, GameResult, InjuryStatus
from app.feeds.player import GameKind, GameTag, NextGame, TagKind
from app.feeds.team import (
    PlayoffPosition,
    PlayoffStatus,
    Schedule,
    SplitRecord,
    Streak,
    TeamFeed,
)
from app.sources.division_standings import DivisionEntry, DivisionStandings
from app.sources.league_injuries import LeagueInjuries
from app.sources.team_info import TeamInfo
from app.sources.team_players import (
    PlayerAverages,
    Roster,
    RosterEntry,
    SeasonLeaders,
)
from app.sources.team_schedule import ScheduledGame, SeasonSchedule

EASTERN = ZoneInfo("America/New_York")
KG_PER_LB = 0.45359237
CM_PER_INCH = 2.54
PLAYOFFS_KEY = "playoffs"
ROUNDS = {"1st Round": 1, "Semifinals": 2, "Finals": 3}
CONFERENCES = {"East": Conference.EAST, "West": Conference.WEST}
LEADER_CATEGORIES = ("points", "rebounds", "assists")

_ROUND_NOTE = re.compile(r"^(East|West) (1st Round|Semifinals|Finals) - Game (\d+)$")
_FINALS_NOTE = re.compile(r"^NBA Finals - Game (\d+)$")
_RECORD = re.compile(r"^(\d+)-(\d+)$")
_STREAK = re.compile(r"^([WL])(\d+)$")


class TeamBuildError(Exception):
    """The team feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def season_label(end_year: int) -> str:
    """The label of a season from its end year: 2026 is 2025-26."""
    return f"{end_year - 1}-{end_year % 100:02d}"


def win_pct(wins: int, losses: int) -> float:
    """The share of games won, to three decimals; 0.0 with no games."""
    games = wins + losses
    return round(wins / games, 3) if games else 0.0


def split_record(text: str) -> SplitRecord:
    """Parse a "30-11" record."""
    match = _RECORD.match(text)
    if match is None:
        raise TeamBuildError(f"record {text!r} is not wins-losses")
    wins, losses = int(match[1]), int(match[2])
    return SplitRecord(wins=wins, losses=losses, win_pct=win_pct(wins, losses))


def streak(text: str) -> Streak | None:
    """Parse a "W2" or "L1" streak; a dash or an empty text is no streak."""
    if text in ("-", ""):
        return None
    match = _STREAK.match(text)
    if match is None or int(match[2]) < 1:
        raise TeamBuildError(f"streak {text!r} is not a win or loss streak")
    kind = GameResult.WIN if match[1] == "W" else GameResult.LOSS
    return Streak(kind=kind, count=int(match[2]))


def games_behind(text: str) -> float:
    """Parse games behind: a dash is the leader, 0."""
    if text == "-":
        return 0
    try:
        return float(text)
    except ValueError:
        raise TeamBuildError(f"games behind {text!r} is not a number") from None


def playoff_position(seed: int, games: int) -> PlayoffPosition | None:
    """The playoff status of a seed: 1-6 seed, 7-10 playin, 11-15 out; none
    while the team has played no game."""
    if games == 0:
        return None
    if 1 <= seed <= 6:
        status = PlayoffStatus.SEED
    elif 7 <= seed <= 10:
        status = PlayoffStatus.PLAYIN
    elif 11 <= seed <= 15:
        status = PlayoffStatus.OUT
    else:
        raise TeamBuildError(f"playoff seed {seed} is outside 1 to 15")
    return PlayoffPosition(status=status, seed=seed)


def conference_rank(entry: DivisionEntry) -> int:
    """The seed, or the team's place in its conference's entry order while the
    provider sends seed 0 because no game was played."""
    return entry.playoff_seed if entry.playoff_seed else entry.conference_order


def game_kind_and_tag(
    note: str | None, playoffs: bool
) -> tuple[GameKind, GameTag | None]:
    """The kind and the tag of a game from its note."""
    if playoffs:
        text = note or ""
        match = _ROUND_NOTE.match(text)
        if match is not None:
            tag = GameTag(
                kind=TagKind.PLAYOFFS,
                conference=CONFERENCES[match[1]],
                round=ROUNDS[match[2]],
                game=int(match[3]),
            )
            return GameKind.PLAYOFFS, tag
        finals = _FINALS_NOTE.match(text)
        if finals is not None:
            return GameKind.PLAYOFFS, GameTag(
                kind=TagKind.PLAYOFFS, round=4, game=int(finals[1])
            )
        return GameKind.PLAYOFFS, GameTag(kind=TagKind.PLAYOFFS)
    if note is not None and note.startswith("NBA Cup"):
        return GameKind.CUP, GameTag(kind=TagKind.CUP)
    if note is not None and note.startswith("NBA All-Star"):
        return GameKind.ALLSTAR, GameTag(kind=TagKind.ALLSTAR)
    return GameKind.REGULAR, None


def age_on(birth_date: dt.date, today: dt.date) -> int:
    """Whole years between the birth date and a date."""
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def eastern_date(moment: dt.datetime) -> dt.date:
    return moment.astimezone(EASTERN).date()


def eastern_month(start_time: dt.datetime) -> str:
    """The YYYY-MM of a start time on the US Eastern calendar."""
    return start_time.astimezone(EASTERN).strftime("%Y-%m")


def position_of(entry: RosterEntry | None) -> str | None:
    return entry.position_name if entry else None


def roster_status(player_id: str, injuries: LeagueInjuries) -> InjuryStatus | str:
    """The injury status of the league report with the athlete id, else active."""
    for reports in injuries.teams.values():
        for report in reports:
            if report.player_id == player_id:
                return report.injury.status
    return "active"


def _played(game: ScheduledGame) -> bool:
    return game.completed and game.state == "post"


def _by_start(games: Iterable[ScheduledGame]) -> list[ScheduledGame]:
    return sorted(games, key=lambda game: game.start_time)


def next_game(
    regular: SeasonSchedule, playoffs: SeasonSchedule, detail_ids: AbstractSet[str]
) -> NextGame | None:
    """The first unplayed game by start time across both schedules."""
    unplayed = [g for g in (*regular.games, *playoffs.games) if g.state == "pre"]
    if not unplayed:
        return None
    game = _by_start(unplayed)[0]
    _, tag = game_kind_and_tag(game.note, game.playoffs)
    return NextGame(
        game_id=game.game_id,
        start_time=game.start_time,
        opponent=game.opponent,
        is_home=game.is_home,
        tag=tag,
        arena=game.arena,
        city=game.city,
        broadcast=game.broadcast,
        detail_available=game.game_id in detail_ids,
    )


def _schedule_game(
    game: ScheduledGame, next_game_id: str | None, detail_ids: AbstractSet[str]
) -> dict[str, Any]:
    kind, tag = game_kind_and_tag(game.note, game.playoffs)
    played = _played(game)
    return {
        "game_id": game.game_id,
        "start_time": game.start_time,
        "opponent": game.opponent,
        "is_home": game.is_home,
        "kind": kind,
        "tag": tag,
        "result": (GameResult.WIN if game.won else GameResult.LOSS) if played else None,
        "team_score": game.team_score if played else None,
        "opponent_score": game.opponent_score if played else None,
        "broadcast": game.broadcast,
        "is_next": game.game_id == next_game_id,
        "detail_available": game.game_id in detail_ids,
    }


def schedule(
    regular: SeasonSchedule,
    playoffs: SeasonSchedule,
    next_game_id: str | None,
    detail_ids: AbstractSet[str],
) -> Schedule | None:
    """The season's games grouped by US Eastern month, then the playoffs group
    last; none without games. The default group holds the next game, else it is
    the last group."""
    months: dict[str, list[ScheduledGame]] = {}
    for game in _by_start(regular.games):
        months.setdefault(eastern_month(game.start_time), []).append(game)
    groups = sorted(months.items())
    if playoffs.games:
        groups.append((PLAYOFFS_KEY, _by_start(playoffs.games)))
    if not groups:
        return None
    default = groups[-1][0]
    for key, games in groups:
        if any(game.game_id == next_game_id for game in games):
            default = key
    return Schedule.model_validate(
        {
            "groups": [
                {
                    "key": key,
                    "games": [
                        _schedule_game(game, next_game_id, detail_ids) for game in games
                    ],
                }
                for key, games in groups
            ],
            "default_group": default,
        }
    )


def birthplace_text(entry: RosterEntry) -> str | None:
    """ "city, state", else "city, country", else "city"; none without a city."""
    if entry.birth_city is None:
        return None
    if entry.birth_state:
        return f"{entry.birth_city}, {entry.birth_state}"
    if entry.birth_country:
        return f"{entry.birth_city}, {entry.birth_country}"
    return entry.birth_city


def player_name(entry: RosterEntry) -> str:
    return entry.display_name or f"{entry.first_name} {entry.last_name}"


def _roster_order(number: str | None) -> tuple[bool, int]:
    if number is not None and not number.isdecimal():
        raise TeamBuildError(f"jersey number {number!r} is not a number")
    return (number is None, int(number or 0))


def _roster_player(
    entry: RosterEntry, today: dt.date, injuries: LeagueInjuries
) -> dict[str, Any]:
    return {
        "id": entry.player_id,
        "name": player_name(entry),
        "number": entry.jersey,
        "position": entry.position_abbreviation,
        "height": entry.display_height,
        "weight": round(entry.weight_lb) if entry.weight_lb else None,
        "age": age_on(entry.birth_date, today) if entry.birth_date else None,
        "birth_date": entry.birth_date,
        "birthplace": birthplace_text(entry),
        "college": entry.college,
        "experience": entry.experience,
        "photo_url": entry.headshot_url,
        "status": roster_status(entry.player_id, injuries),
    }


def _leader(
    players: list[PlayerAverages], field: str, by_id: dict[str, RosterEntry]
) -> dict[str, Any] | None:
    best: PlayerAverages | None = None
    for player in players:
        if best is None or getattr(player, field) > getattr(best, field):
            best = player
    if best is None or best.player_id not in by_id:
        return None
    entry = by_id[best.player_id]
    position = entry.position_name or entry.position_abbreviation
    if position is None:
        return None
    return {
        "player_id": entry.player_id,
        "name": player_name(entry),
        "number": entry.jersey,
        "position": position,
        "photo_url": entry.headshot_url,
        "value": round(getattr(best, field), 1),
    }


def _injuries(
    team_code: str, injuries: LeagueInjuries, by_id: dict[str, RosterEntry]
) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    for report in injuries.teams.get(team_code, []):
        if report.player_id is None or report.updated_at is None:
            continue
        entry = by_id.get(report.player_id)
        listed.append(
            {
                "player_id": report.player_id,
                "name": report.injury.display_name,
                "number": entry.jersey if entry else None,
                "position": position_of(entry),
                "status": report.injury.status,
                "comment": report.injury.comment,
                "updated_at": report.updated_at,
            }
        )
    return listed


def _record(entry: DivisionEntry) -> dict[str, Any]:
    games = entry.wins + entry.losses
    return {
        "wins": entry.wins,
        "losses": entry.losses,
        "win_pct": win_pct(entry.wins, entry.losses),
        "home": split_record(entry.home),
        "away": split_record(entry.road),
        "last_ten": split_record(entry.last_ten),
        "streak": streak(entry.streak),
        "games_behind": games_behind(entry.games_behind),
        "conference_rank": conference_rank(entry),
        "division_rank": entry.division_order,
        "playoff": playoff_position(entry.playoff_seed, games),
        "points_for": {
            "per_game": round(entry.avg_points_for, 1),
            "total": round(entry.points_for),
        },
        "points_against": {
            "per_game": round(entry.avg_points_against, 1),
            "total": round(entry.points_against),
        },
        "differential": {
            "per_game": round(entry.differential, 1),
            "total": round(entry.point_differential),
        },
    }


def build_team_feed(
    team_code: str,
    info: TeamInfo,
    standings: DivisionStandings,
    roster: Roster,
    leaders: SeasonLeaders,
    injuries: LeagueInjuries,
    regular: SeasonSchedule,
    playoffs: SeasonSchedule,
    *,
    now: dt.datetime,
    detail_ids: AbstractSet[str],
) -> TeamFeed:
    """Build the team feed from the fetched data, or raise TeamBuildError."""
    entry = standings.teams.get(team_code)
    if entry is None:
        raise TeamBuildError(f"team {team_code} has no standing")
    ids = frozenset(detail_ids)
    today = eastern_date(now)
    by_id = {player.player_id: player for player in roster.entries}
    upcoming = next_game(regular, playoffs, ids)
    coach = roster.coach
    try:
        sorted_entries = sorted(
            roster.entries, key=lambda player: _roster_order(player.jersey)
        )
        return TeamFeed.model_validate(
            {
                "code": team_code,
                "city": info.location,
                "name": info.name,
                "conference": entry.conference,
                "division": entry.division,
                "colors": {
                    "primary": f"#{info.color}",
                    "secondary": f"#{info.alternate_color}",
                },
                "arena": {
                    "name": info.venue_name,
                    "city": info.venue_city,
                    "photo_url": info.venue_photo_url,
                },
                "coach": (
                    {
                        "name": f"{coach.first_name} {coach.last_name}",
                        "seasons": coach.experience,
                    }
                    if coach
                    else None
                ),
                "season": season_label(roster.season),
                "record": _record(entry),
                "leaders": {
                    "season": season_label(leaders.season),
                    **{
                        field: _leader(leaders.players, field, by_id)
                        for field in LEADER_CATEGORIES
                    },
                },
                "roster": [
                    _roster_player(player, today, injuries) for player in sorted_entries
                ],
                "injuries": _injuries(team_code, injuries, by_id),
                "next_game": upcoming,
                "schedule": schedule(
                    regular,
                    playoffs,
                    upcoming.game_id if upcoming else None,
                    ids,
                ),
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise TeamBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None
