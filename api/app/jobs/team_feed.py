# api/app/jobs/team_feed.py
#
# Team feed builder: a pure function from the data the source adapters fetched
# to the team feed, with every conversion the contract needs: win percentages,
# records, streak, playoff status by seed, ranks, season labels, game tags from
# notes, ages on the US Eastern date, leaders matched to the roster, roster
# status from the league injuries, the record labeled with the season of the
# standings, games behind the conference leader (shared with the standings
# feed builder), the next game and the schedule grouped by
# US Eastern month with the playoffs last. It reads no clock and no source: the
# caller passes the time and the ids of the games that have a detail feed. The
# shared conversions are used by the player feed builder too. TeamFeeds is the
# feed kind of the on-demand cache: the ids are the 30 lowercase standard codes,
# the feed is stored at feeds/teams/{code}.json only when requested, it expires 1
# hour after a final game of the team that follows the build and 7 days after the
# build (rule G), and detailAvailable is set when it is served, from the games of
# the days shown. Team feeds are never deleted.
#
# SEE: docs/api/team.md, docs/api/player.md, docs/source-rules.md, api/app/jobs/game_detail_feed.py

import datetime as dt
import re
from collections.abc import Awaitable, Callable, Iterable
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
from app.jobs.games import GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.settings import Settings
from app.sources import (
    division_standings,
    league_injuries,
    team_info,
    team_players,
    team_schedule,
)
from app.sources.division_standings import DivisionEntry, DivisionStandings
from app.sources.http import SourceClient
from app.sources.league_injuries import LeagueInjuries
from app.sources.team_info import TeamInfo
from app.sources.team_players import (
    PlayerAverages,
    Roster,
    RosterEntry,
    SeasonLeaders,
)
from app.sources.team_schedule import ScheduledGame, SeasonSchedule
from app.sources.teams import TEAM_CODES
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "teams"
FEED_LIFETIME = dt.timedelta(days=7)
AFTER_FINAL = dt.timedelta(hours=1)
START_MARGIN = dt.timedelta(days=1)
TEAM_IDS = frozenset(code.lower() for code in TEAM_CODES.values())

FetchRoster = Callable[[SourceClient, str, Settings], Awaitable[Roster]]
FetchLeaders = Callable[[SourceClient, Roster, Settings], Awaitable[SeasonLeaders]]
FetchInfo = Callable[[SourceClient, str, Settings], Awaitable[TeamInfo]]
FetchDivisionStandings = Callable[
    [SourceClient, Settings], Awaitable[DivisionStandings]
]
FetchInjuries = Callable[[SourceClient, Settings], Awaitable[LeagueInjuries]]
FetchSeasonSchedule = Callable[..., Awaitable[SeasonSchedule]]

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


def conference_games_behind(
    entry: DivisionEntry, entries: Iterable[DivisionEntry]
) -> float:
    """Games behind the leader of the team's conference: half the gap between
    the best wins minus losses of the conference and the team's; 0 for the
    leader. The entries must contain the entry. Shared with the standings feed
    builder."""
    best = max(
        other.wins - other.losses
        for other in entries
        if other.conference is entry.conference
    )
    return (best - (entry.wins - entry.losses)) / 2


def playoff_position(seed: int | None, games: int) -> PlayoffPosition | None:
    """The playoff status of a seed: 1-6 seed, 7-10 playin, 11-15 out; none
    while the team has played no game or without a seed."""
    if games == 0 or seed is None:
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
    provider sends seed 0 because no game was played, or without a seed."""
    return entry.playoff_seed if entry.playoff_seed else entry.conference_order


def game_kind_and_tag(
    note: str | None, playoffs: bool, *, preseason: bool = False
) -> tuple[GameKind, GameTag | None]:
    """The kind and the tag of a game from its note. A preseason game has no tag."""
    if preseason:
        return GameKind.PRESEASON, None
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


def _record(
    entry: DivisionEntry, season: int, entries: Iterable[DivisionEntry]
) -> dict[str, Any]:
    games = entry.wins + entry.losses
    return {
        "season": season_label(season),
        "wins": entry.wins,
        "losses": entry.losses,
        "win_pct": win_pct(entry.wins, entry.losses),
        "home": split_record(entry.home),
        "away": split_record(entry.road),
        "last_ten": split_record(entry.last_ten),
        "streak": None if entry.streak is None else streak(entry.streak),
        "games_behind": (
            conference_games_behind(entry, entries) if games > 0 else None
        ),
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
                "record": _record(entry, standings.season, standings.teams.values()),
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


def feed_expired(
    built_at: dt.datetime, now: dt.datetime, final_times: Iterable[dt.datetime]
) -> bool:
    """Whether a stored feed is expired (rule G): 7 days after the build, or 1
    hour after a final game that follows the build."""
    if now - built_at >= FEED_LIFETIME:
        return True
    return any(built_at < time + AFTER_FINAL <= now for time in final_times)


def with_team_detail(feed: TeamFeed, ids: AbstractSet[str]) -> TeamFeed:
    """The feed with detailAvailable true exactly for the games with an id given."""
    data = feed.model_dump(by_alias=False)
    if data["next_game"] is not None:
        data["next_game"]["detail_available"] = data["next_game"]["game_id"] in ids
    if data["schedule"] is not None:
        for group in data["schedule"]["groups"]:
            for game in group["games"]:
                game["detail_available"] = game["game_id"] in ids
    return TeamFeed.model_validate(data)


class TeamFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        *,
        fetch_roster: FetchRoster = team_players.fetch_roster,
        fetch_team_leaders: FetchLeaders = team_players.fetch_team_leaders,
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
        fetch_division_standings: FetchDivisionStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_league_injuries: FetchInjuries = league_injuries.fetch_league_injuries,
        fetch_season_schedule: FetchSeasonSchedule = team_schedule.fetch_season_schedule,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._cache = cache
        self._games = games
        self._fetch_roster = fetch_roster
        self._fetch_team_leaders = fetch_team_leaders
        self._fetch_team_info = fetch_team_info
        self._fetch_division_standings = fetch_division_standings
        self._fetch_league_injuries = fetch_league_injuries
        self._fetch_season_schedule = fetch_season_schedule
        cache.register(self.kind())

    def check(self, code: str) -> IdStatus:
        return IdStatus.KNOWN if code in TEAM_IDS else IdStatus.UNKNOWN

    async def build(self, code: str) -> TeamFeed:
        team = code.upper()
        roster = await self._fetch_roster(self._client, team, self._settings)
        leaders = await self._fetch_team_leaders(self._client, roster, self._settings)
        info = await self._fetch_team_info(self._client, team, self._settings)
        standings = await self._fetch_division_standings(self._client, self._settings)
        injuries = await self._fetch_league_injuries(self._client, self._settings)
        regular = await self._fetch_season_schedule(
            self._client, team, roster.season, self._settings, playoffs=False
        )
        playoffs = await self._fetch_season_schedule(
            self._client, team, roster.season, self._settings, playoffs=True
        )
        return build_team_feed(
            team,
            info,
            standings,
            roster,
            leaders,
            injuries,
            regular,
            playoffs,
            now=self._client.clock(),
            detail_ids=self.detail_ids(),
        )

    def detail_ids(self) -> frozenset[str]:
        """The ids of the games of the days shown now."""
        return frozenset(game.id for game in self._games.loaded_games())

    def stored(self, team: str) -> TeamFeed | None:
        body = read_by_id(self._settings.data_dir, KIND, team.lower())
        if body is None:
            return None
        try:
            return TeamFeed.model_validate_json(body)
        except ValidationError:
            return None

    def final_times(
        self,
        team: str,
        schedule: Schedule | None,
        built_at: dt.datetime,
        now: dt.datetime,
    ) -> list[dt.datetime]:
        """The final times of the team's games that can expire a feed built at built_at."""
        ids = {
            game.id
            for game in self._games.final_games()
            if team in (game.away.code, game.home.code)
        }
        if schedule is not None:
            ids |= {
                game.game_id
                for group in schedule.groups
                for game in group.games
                if built_at - START_MARGIN < game.start_time <= now
            }
        times = (self._store.final_time(game_id) for game_id in sorted(ids))
        return [time for time in times if time is not None]

    def expired(
        self,
        team: str,
        schedule: Schedule | None,
        built_at: dt.datetime,
        now: dt.datetime,
    ) -> bool:
        return feed_expired(
            built_at, now, self.final_times(team, schedule, built_at, now)
        )

    def is_fresh(self, feed: TeamFeed, built_at: dt.datetime, now: dt.datetime) -> bool:
        return not self.expired(feed.code, feed.schedule, built_at, now)

    def serve_with(self, code: str, feed: TeamFeed) -> TeamFeed:
        return with_team_detail(feed, self.detail_ids())

    def keep(self, code: str) -> bool:
        return code in TEAM_IDS

    def kind(self) -> FeedKind[TeamFeed]:
        return FeedKind(
            KIND,
            TeamFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
        )
