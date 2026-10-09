# api/app/sources/game_detail.py
#
# Game detail adapter: fetches one game's box score from the provider and
# maps it to the contract's leaders and team stats. It also maps the full
# game detail sections: venue, box score, team stats, win probability and
# its period boundaries, injuries, season series and videos. The provider URLs come from Settings.
# Provider data never leaves this module.
#
# A team is matched to its box score players by id when both sides send one,
# else by abbreviation. A team without an abbreviation is resolved by id or is a
# guest without a code (ADR 0026). Stat and win probability leaders are sides.
#
# SEE: docs/api/games.md, api/app/sources/scoreboard.py

import datetime as dt
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
    Video,
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
from app.settings import Settings
from app.sources.http import Freshness, SourceClient, SourceError, get_json
from app.sources.teams import side_of, to_team_code

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
    id: str
    display_name: str
    headshot: _ProviderHeadshot | None = None


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


def _number(game_id: str, value: str, kind: type[int | float]) -> Any:
    try:
        return kind(value)
    except ValueError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat that is not a number"
        ) from None


def _photo(athlete: _ProviderAthlete, photo_url: str, guest: bool) -> str | None:
    # A league player's photo comes from the template; a guest player has only
    # the box score headshot, if any.
    if guest:
        return athlete.headshot.href if athlete.headshot else None
    return photo_url.format(player_id=athlete.id)


def _leader(
    game_id: str,
    code: str | None,
    players: _ProviderBoxPlayers,
    photo_url: str,
    guest: bool,
) -> dict[str, Any]:
    label = code or "a guest side"
    if not players.statistics:
        raise SourceError(SOURCE, f"game {game_id} has no player stats for {label}")
    group = players.statistics[0]
    columns: dict[str, int] = {}
    for key in ("points", "rebounds", "assists"):
        if key not in group.keys:
            raise SourceError(SOURCE, f"game {game_id} has no {key} column")
        columns[key] = group.keys.index(key)
    played = [line for line in group.athletes if line.stats]
    if not played:
        raise SourceError(SOURCE, f"game {game_id} has no player stats for {label}")
    try:
        values = [
            {key: _number(game_id, line.stats[i], int) for key, i in columns.items()}
            for line in played
        ]
    except IndexError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat line shorter than its columns"
        ) from None
    # Rule: docs/adr/0009-game-leader-selection.md. max keeps the first on a full tie.
    top = max(
        range(len(played)),
        key=lambda i: (
            values[i]["points"],
            values[i]["rebounds"] + values[i]["assists"],
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
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> GameDetail:
    """Return the leaders and team stats of one game, or raise SourceError.

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
        code, guest = side_of(team.team.abbreviation, team.team.id, source=SOURCE)
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
    athlete: _ProviderAthlete
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


class _SummaryHref(_ProviderModel):
    href: str


class _SummaryVideoLinks(_ProviderModel):
    web: _SummaryHref


class _SummaryVideo(_ProviderModel):
    headline: str
    duration: NonNegativeInt
    thumbnail: str | None = None
    links: _SummaryVideoLinks


class _ProviderSummary(_ProviderModel):
    format: _SummaryFormat
    game_info: _SummaryGameInfo
    boxscore: _SummaryBoxscore
    plays: list[_SummaryPlay] = []
    winprobability: list[_SummaryWinProbability] = []
    injuries: list[_SummaryTeamInjuries] = []
    seasonseries: list[_SummarySeries] = []
    videos: list[_SummaryVideo] = []


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
    """A game's detail sections as the game summary knows them."""

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
    videos: list[Video] | None = None


def _stat_leader(
    row: str,
    away_value: float,
    home_value: float,
) -> Side | None:
    # Rule: docs/api/game-detail.md. A tie has no leader; turnovers go to the lower.
    if away_value == home_value:
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
    for key in wanted:
        if key not in keys:
            raise SourceError(SOURCE, f"game {game_id} has no {key} column")
    try:
        by_key = {key: values[keys.index(key)] for key in wanted}
    except IndexError:
        raise SourceError(
            SOURCE, f"game {game_id} has a stat line shorter than its columns"
        ) from None
    line: dict[str, Any] = {}
    for field, key in BOX_FIELDS.items():
        line[field] = _number(game_id, by_key[key], int)
    for field, key in BOX_SHOTS.items():
        made, attempted = _made_attempted(game_id, by_key[key])
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
    for line in group.athletes:
        if not line.stats:
            continue
        values = _box_line(game_id, group.keys, line.stats, wanted)
        for key in ("minutes", "plusMinus"):
            if key not in group.keys:
                raise SourceError(SOURCE, f"game {game_id} has no {key} column")
        try:
            minutes = line.stats[group.keys.index("minutes")]
            plus_minus = line.stats[group.keys.index("plusMinus")]
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
                "plus_minus": _number(game_id, plus_minus, int),
                "photo_url": _photo(line.athlete, photo_url, guest),
                **values,
            }
        )
    by_name = {stat.name: stat.display_value for stat in team.statistics}
    totals = _box_line(game_id, group.keys, group.totals, wanted)
    for field in ("field_goal_pct", "three_point_pct", "free_throw_pct"):
        name = STAT_ROWS[field]
        if name not in by_name:
            raise SourceError(SOURCE, f"game {game_id} has no {name} stat")
        totals[field] = _number(game_id, by_name[name], float) / 100
    return {"players": lines, "totals": totals}


def _detail_team_stats(game_id: str, team: _ProviderBoxTeam) -> dict[str, Any]:
    by_name = {stat.name: stat.display_value for stat in team.statistics}
    stats: dict[str, Any] = {}
    for field, name in STAT_ROWS.items():
        if name not in by_name:
            raise SourceError(SOURCE, f"game {game_id} has no {name} stat")
        if field in PERCENT_ROWS:
            stats[field] = _number(game_id, by_name[name], float) / 100
        else:
            stats[field] = _number(game_id, by_name[name], int)
    return stats


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


def _videos(videos: list[_SummaryVideo]) -> list[dict[str, Any]]:
    return [
        {
            "title": video.headline,
            "duration": f"{video.duration // 60}:{video.duration % 60:02d}",
            "thumbnail_url": video.thumbnail or None,
            "link_url": video.links.web.href,
        }
        for video in videos
    ]


async def fetch_game_detail_sections(
    client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
) -> GameDetailSections:
    """Return the detail sections of one game, or raise SourceError.

    `fresh` is the freshness of the game's state: 30 seconds live, the
    attempt's due time final, 1 hour otherwise."""
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
    resolved = {
        side: side_of(team.team.abbreviation, team.team.id, source=SOURCE)
        for side, team in sides.items()
    }
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
        sections["box_score"] = box_score
        sections["team_stats"] = team_stats

    points = _win_probability(summary)
    sections["win_probability"] = points or None
    sections["win_probability_leader"] = _win_probability_leader(points)
    sections["win_probability_periods"] = (
        _win_probability_periods(summary) if points else None
    )
    if summary.injuries:
        sections["injuries"] = _injuries(game_id, summary, abbreviations)
    # A guest game has no season series (ADR 0025).
    sections["season_series"] = (
        None
        if any(guests.values())
        else _season_series(
            game_id,
            summary,
            {side: code for side, (code, _) in resolved.items() if code is not None},
        )
    )
    sections["videos"] = _videos(summary.videos) or None

    try:
        return GameDetailSections.model_validate(sections)
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise SourceError(
            SOURCE, f"game {game_id} is invalid: {first['type']} at {location}"
        ) from None
