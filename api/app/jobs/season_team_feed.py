# api/app/jobs/season_team_feed.py
#
# Team feed of a past season (ADR 0043): the team feed's shape for one team in one
# season. The builder is a pure function from the data the adapters fetched to
# the feed; it reads no clock and no source and reuses the conversions of the team
# feed builder. City and name are the season's, from the season team object;
# colors are today's. The record is the standing of that season (the play-in
# position only from the 2020-21 season, when the play-in began), the leaders are
# that season's averages with no fallback, and the roster is the players of that
# season's box scores (SeasonRosters): their jersey and position come from the
# box score, else they are null, every status is active and every other roster
# field is null (ADR 0053). A leader whose box-score position is absent keeps a
# null position. The schedule holds the regular season and the playoffs, with
# detail available for every final game, and its opponents are named by that
# season's team object. The arena, coach, injuries, next game, Cup and titles
# are null.
#
# SeasonTeamFeeds is the feed kind of the on-demand cache: the id is
# {season}-{code} (the season's end year and the lowercase standard code), the
# feed is stored at feeds/season-teams/{id}.json only when requested. A season is
# valid from 1994 to the season before the current one (past_season_status). A
# franchise with no team object that season is unknown (404)
# after that one read, remembered in memory. The franchise names are built first
# (the names kind) and set again when served. A feed is built once and kept
# (rule G): it is never deleted, and rebuilt only when its build version is not
# the current one (ADR 0053).
#
# SEE: docs/api/team.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# docs/adr/0053-season-level-rules-for-past-seasons.md, api/app/jobs/team_feed.py

import datetime as dt
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from app.feeds.opponent import Opponent
from app.feeds.team import NameRun, PastTeamFeed
from app.jobs import team_names
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    UnknownFeedError,
    is_current_build,
    with_build_version,
)
from app.jobs.season_rosters import SeasonRosters
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    LEADER_CATEGORIES,
    TEAM_IDS,
    FetchInfo,
    TeamBuildError,
    _played,
    _record,
    roster_order,
    schedule,
    season_label,
    with_names,
)
from app.jobs.team_names import SeasonIdentity, TeamNamesFeeds, season_named
from app.settings import Settings
from app.sources import (
    division_standings,
    season_team,
    team_info,
    team_players,
    team_schedule,
)
from app.sources.division_standings import DivisionStandings
from app.sources.game_detail import BoxScoreRosterEntry
from app.sources.http import SourceClient
from app.sources.season_team import SeasonTeam
from app.sources.team_info import TeamInfo
from app.sources.team_players import PlayerAverages, SeasonLeaders
from app.sources.team_schedule import SeasonSchedule
from app.sources.teams import PROVIDER_IDS
from app.storage.state import StateStore

KIND = "season-teams"
FIRST_PLAYIN_SEASON = 2021
_ID = re.compile(r"([0-9]{4})-([a-z]{3})")

FetchSeasonTeam = Callable[
    [SourceClient, str, int, Settings], Awaitable[SeasonTeam | None]
]
FetchSeasonStandings = Callable[..., Awaitable[DivisionStandings]]
FetchSeasonAverages = Callable[
    [SourceClient, str, int, Settings], Awaitable[list[PlayerAverages]]
]
FetchSeasonSchedule = Callable[..., Awaitable[SeasonSchedule]]


def past_roster_player(entry: BoxScoreRosterEntry) -> dict[str, Any]:
    """A roster row of a past season: the box score gives the name, the jersey,
    the position and the photo, and every other field is null (ADR 0053)."""
    return {
        "id": entry.player_id,
        "name": entry.display_name,
        "number": entry.jersey,
        "position": entry.position_abbreviation,
        "height": None,
        "weight": None,
        "age": None,
        "birth_date": None,
        "birthplace": None,
        "college": None,
        "experience": None,
        "photo_url": entry.headshot_url,
        "status": "active",
    }


def past_leader(
    players: list[PlayerAverages], field: str, by_id: dict[str, BoxScoreRosterEntry]
) -> dict[str, Any] | None:
    """The leader of a statistic among the season's averages, with the box-score
    roster's name, jersey, position (which may be null) and photo."""
    best: PlayerAverages | None = None
    for player in players:
        if best is None or getattr(player, field) > getattr(best, field):
            best = player
    if best is None or best.player_id not in by_id:
        return None
    entry = by_id[best.player_id]
    return {
        "player_id": entry.player_id,
        "name": entry.display_name,
        "number": entry.jersey,
        "position": entry.position_abbreviation,
        "photo_url": entry.headshot_url,
        "value": round(getattr(best, field), 1),
    }


def _renamed(
    games: SeasonSchedule, names: Mapping[str, SeasonIdentity]
) -> SeasonSchedule:
    return SeasonSchedule(
        games=[
            game.model_copy(update={"opponent": season_named(game.opponent, names)})
            for game in games.games
        ]
    )


def opponent_codes(*schedules: SeasonSchedule) -> list[str]:
    """The distinct league opponent codes of the schedules."""
    sides: list[Opponent] = [
        game.opponent for schedule_ in schedules for game in schedule_.games
    ]
    return sorted(
        {side.code for side in sides if not side.guest and side.code is not None}
    )


def build_season_team_feed(
    team_code: str,
    season: int,
    season_team: SeasonTeam,
    info: TeamInfo,
    standings: DivisionStandings,
    roster: Sequence[BoxScoreRosterEntry],
    leaders: SeasonLeaders,
    regular: SeasonSchedule,
    playoffs: SeasonSchedule,
    names: list[NameRun] | None = None,
    opponent_names: Mapping[str, SeasonIdentity] | None = None,
    identity: SeasonIdentity | None = None,
) -> PastTeamFeed:
    """Build the team feed of a past season, or raise TeamBuildError."""
    entry = standings.teams.get(team_code)
    if entry is None:
        raise TeamBuildError(f"team {team_code} has no standing")
    by_id = {player.player_id: player for player in roster}
    record = _record(entry, standings.season, standings.teams.values())
    if season < FIRST_PLAYIN_SEASON:
        record["playoff"] = None
    try:
        sorted_entries = sorted(roster, key=lambda player: roster_order(player.jersey))
        regular = _renamed(regular, opponent_names or {})
        playoffs = _renamed(playoffs, opponent_names or {})
        final_ids = frozenset(
            game.game_id for game in (*regular.games, *playoffs.games) if _played(game)
        )
        data: dict[str, Any] = {
            "code": team_code,
            "city": season_team.location,
            "name": season_team.name,
            "conference": entry.conference,
            "division": entry.division,
            "colors": {
                "primary": f"#{info.color}",
                "secondary": f"#{info.alternate_color}",
            },
            "arena": None,
            "coach": None,
            "season": season_label(season),
            "record": record,
            "leaders": {
                "season": season_label(leaders.season),
                **{
                    field: past_leader(leaders.players, field, by_id)
                    for field in LEADER_CATEGORIES
                },
            },
            "roster": [past_roster_player(player) for player in sorted_entries],
            "injuries": None,
            "next_game": None,
            "schedule": schedule(regular, playoffs, None, final_ids),
            "cup": None,
            "titles": None,
            "names": names or [],
        }
        if identity is not None:
            data["season_code"] = identity.code
            data["historical"] = identity.historical
        return PastTeamFeed.model_validate(data)
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise TeamBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class SeasonTeamFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        names: TeamNamesFeeds,
        rosters: SeasonRosters,
        *,
        fetch_season_team: FetchSeasonTeam = season_team.fetch_season_team,
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
        fetch_division_standings: FetchSeasonStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_season_averages: FetchSeasonAverages = team_players.fetch_season_averages,
        fetch_season_schedule: FetchSeasonSchedule = team_schedule.fetch_season_schedule,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._names = names
        self._rosters = rosters
        self._fetch_season_team = fetch_season_team
        self._fetch_team_info = fetch_team_info
        self._fetch_division_standings = fetch_division_standings
        self._fetch_season_averages = fetch_season_averages
        self._fetch_season_schedule = fetch_season_schedule
        # (season, code) of the franchises found to have no team that season.
        self._no_team: set[tuple[int, str]] = set()
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        match = _ID.fullmatch(feed_id)
        if match is None or match[2] not in TEAM_IDS:
            return IdStatus.UNKNOWN
        status = past_season_status(match[1], self._stars.current_season())
        if status is not IdStatus.KNOWN:
            return status
        if (int(match[1]), match[2]) in self._no_team:
            return IdStatus.UNKNOWN
        return IdStatus.KNOWN

    def depends_on(self, feed_id: str) -> tuple[str, str] | None:
        match = _ID.fullmatch(feed_id)
        return None if match is None else (team_names.KIND, match[2])

    async def build(self, feed_id: str) -> PastTeamFeed:
        match = _ID.fullmatch(feed_id)
        if match is None:
            raise TeamBuildError(f"{feed_id} is not a season and a team")
        season, code = int(match[1]), match[2]
        team = code.upper()
        found = await self._fetch_season_team(
            self._client, team, season, self._settings
        )
        if found is None:
            self._no_team.add((season, code))
            raise UnknownFeedError(feed_id)
        info = await self._fetch_team_info(self._client, team, self._settings)
        standings = await self._fetch_division_standings(
            self._client, self._settings, season=season
        )
        roster = await self._rosters.roster(team, season)
        players = await self._fetch_season_averages(
            self._client, PROVIDER_IDS[team], season, self._settings
        )
        regular = await self._fetch_season_schedule(
            self._client, team, season, self._settings, playoffs=False, by_id_first=True
        )
        playoffs = await self._fetch_season_schedule(
            self._client, team, season, self._settings, playoffs=True, by_id_first=True
        )
        opponent_names = await self._names.season_names(
            opponent_codes(regular, playoffs), season
        )
        return with_build_version(
            build_season_team_feed(
                team,
                season,
                found,
                info,
                standings,
                roster,
                SeasonLeaders(season=season, players=players),
                regular,
                playoffs,
                self._names.stored(code),
                opponent_names,
                (await self._names.season_names([team], season)).get(team),
            )
        )

    def serve_with(self, feed_id: str, feed: PastTeamFeed) -> PastTeamFeed:
        match = _ID.fullmatch(feed_id)
        runs = None if match is None else self._names.stored(match[2])
        return feed if runs is None else with_names(feed, runs)

    def is_fresh(
        self, feed: PastTeamFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[PastTeamFeed]:
        return FeedKind(
            KIND,
            PastTeamFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
            serve_with=self.serve_with,
            depends_on=self.depends_on,
        )
