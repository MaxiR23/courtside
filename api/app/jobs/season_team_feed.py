# api/app/jobs/season_team_feed.py
#
# Team feed of a past season (ADR 0043): the team feed's shape for one team in one
# season. The builder is a pure function from the data the adapters fetched to
# the feed; it reads no clock and no source and reuses the conversions of the team
# feed builder. City and name are the season's, from the season team object;
# colors are today's, from the cached team info, and null without it. The record
# is the standing of that season (the play-in position only from the 2020-21
# season, when the play-in began). The roster and leaders are null (ADR 0059).
# The schedule holds the regular season and the playoffs, with detail available
# for every final game, and its opponents are named from the schedule payloads
# with the season code of the stored franchise names. The dates of the final
# games are registered with no read. The arena, coach, injuries, next game, Cup
# and titles are null. The build declares a read budget of READ_BUDGET source
# reads, 4 of them sent: the season team object, the standings and the two
# schedules (ADR 0059).
#
# SeasonTeamFeeds is the feed kind of the on-demand cache: the id is
# {season}-{code} (the season's end year and the lowercase standard code), the
# feed is stored at feeds/season-teams/{id}.json only when requested. A season is
# valid from 1994 to the season before the current one (past_season_status). A
# franchise with no team object that season is unknown (404)
# after that one read, remembered in memory. The franchise names are built first
# (the names kind) and set again when served. A feed is built once and kept
# (rule G): it is deleted with its build row when not served in 90 days and
# rebuilt on its next request (ADR 0063), and rebuilt otherwise only when its
# build version is not the current one (ADR 0053) or its stored names are of another build version, in
# which case the names are rebuilt first (ADR 0055).
#
# SEE: docs/api/team.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# docs/adr/0053-season-level-rules-for-past-seasons.md, api/app/jobs/team_feed.py

import asyncio
import datetime as dt
import re
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from pydantic import ValidationError

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
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    TEAM_IDS,
    TeamBuildError,
    _played,
    _record,
    eastern_date,
    schedule,
    season_label,
    with_names,
)
from app.jobs.team_names import (
    SeasonIdentity,
    TeamNamesFeeds,
    payload_names,
    season_named,
)
from app.settings import Settings
from app.sources import division_standings, season_team, team_info, team_schedule
from app.sources.division_standings import DivisionStandings
from app.sources.http import ReadBudget, SourceClient, within_budget
from app.sources.season_team import SeasonTeam
from app.sources.team_info import TeamInfo
from app.sources.team_schedule import SeasonSchedule
from app.sources.teams import SeasonTeamName
from app.storage.state import StateStore

KIND = "season-teams"
READ_BUDGET = 5
FIRST_PLAYIN_SEASON = 2021
_ID = re.compile(r"([0-9]{4})-([a-z]{3})")

FetchSeasonTeam = Callable[
    [SourceClient, str, int, Settings], Awaitable[SeasonTeam | None]
]
FetchSeasonStandings = Callable[..., Awaitable[DivisionStandings]]
FetchSeasonSchedule = Callable[..., Awaitable[SeasonSchedule]]


def _renamed(
    games: SeasonSchedule, names: Mapping[str, SeasonIdentity]
) -> SeasonSchedule:
    return SeasonSchedule(
        games=[
            game.model_copy(update={"opponent": season_named(game.opponent, names)})
            for game in games.games
        ]
    )


def build_season_team_feed(
    team_code: str,
    season: int,
    season_team: SeasonTeam,
    info: TeamInfo | None,
    standings: DivisionStandings,
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
    record = _record(entry, standings.season, standings.teams.values())
    if season < FIRST_PLAYIN_SEASON:
        record["playoff"] = None
    try:
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
            "colors": None
            if info is None
            else {
                "primary": f"#{info.color}",
                "secondary": f"#{info.alternate_color}",
            },
            "arena": None,
            "coach": None,
            "season": season_label(season),
            "record": record,
            "leaders": None,
            "roster": None,
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
        *,
        fetch_season_team: FetchSeasonTeam = season_team.fetch_season_team,
        fetch_division_standings: FetchSeasonStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_season_schedule: FetchSeasonSchedule = team_schedule.fetch_season_schedule,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._names = names
        self._fetch_season_team = fetch_season_team
        self._fetch_division_standings = fetch_division_standings
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
        return await within_budget(
            ReadBudget(READ_BUDGET),
            f"season team: {feed_id}",
            lambda: self._build(feed_id),
        )

    async def _build(self, feed_id: str) -> PastTeamFeed:
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
        standings, regular, playoffs = await asyncio.gather(
            self._fetch_division_standings(self._client, self._settings, season=season),
            self._fetch_season_schedule(
                self._client,
                team,
                season,
                self._settings,
                playoffs=False,
                by_id_first=True,
            ),
            self._fetch_season_schedule(
                self._client,
                team,
                season,
                self._settings,
                playoffs=True,
                by_id_first=True,
            ),
        )
        self._store.set_past_game_dates(
            {
                game.game_id: eastern_date(game.start_time)
                for game in (*regular.games, *playoffs.games)
                if _played(game)
            },
            at=self._client.clock(),
        )
        info = team_info.cached_team_info(self._client, team, self._settings)
        identities = {**playoffs.teams, **regular.teams}
        identities[team] = SeasonTeamName(
            abbreviation=found.abbreviation, name=found.name, location=found.location
        )
        runs = {
            stored_code: stored
            for stored_code in sorted(identities)
            if (stored := self._names.stored(stored_code))
        }
        names = payload_names(identities, runs)
        return with_build_version(
            build_season_team_feed(
                team,
                season,
                found,
                info,
                standings,
                regular,
                playoffs,
                self._names.stored(code),
                names,
                names.get(team),
            )
        )

    def serve_with(self, feed_id: str, feed: PastTeamFeed) -> PastTeamFeed:
        match = _ID.fullmatch(feed_id)
        # A served page keeps the rows of the details it links (ADR 0063).
        if feed.schedule is not None:
            self._store.touch_past_games(
                (
                    game.game_id
                    for group in feed.schedule.groups
                    for game in group.games
                    if game.detail_available
                ),
                at=self._client.clock(),
            )
        runs = None if match is None else self._names.stored(match[2])
        return feed if runs is None else with_names(feed, runs)

    def is_fresh(
        self, feed: PastTeamFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        # A stored names list of another build also makes the feed stale, so its
        # rebuild starts the names first (ADR 0055).
        return is_current_build(feed) and not self._names.outdated(feed.code.lower())

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
