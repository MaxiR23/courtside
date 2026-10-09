# api/app/jobs/search_feed.py
#
# Search feed builder: a pure function from the division standings, the team
# colors, the roster entries the stars job keeps and the league injuries to the
# search feed. Teams come in standard code order and players in team code order,
# then roster order; a player whose newest roster is another team's is listed
# only there. SearchFeeds is the feed kind of the on-demand cache: the only id is
# "league", the feed is stored at feeds/search/league.json only when requested,
# and it answers 503 (not ready) until the stars job has fetched every roster.
# The build makes no roster request and no per-player request: the rosters come
# from the stars job's memory. It expires 1 hour after a final game of the league
# that follows the build, 7 days after the build, and when the stars job fetches
# a roster after the build (rule G). Colors come from team info, one read per
# team, and are null when a read fails. The feed is never deleted.
#
# SEE: docs/api/search.md, docs/source-rules.md, api/app/jobs/standings_feed.py

import asyncio
import datetime as dt
from collections.abc import Callable, Mapping, Sequence

from pydantic import ValidationError

from app.feeds.search import SearchFeed
from app.jobs.games import GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.stars import StarsJob
from app.jobs.team_feed import (
    FetchDivisionStandings,
    FetchInfo,
    FetchInjuries,
    feed_expired,
    player_name,
    roster_status,
)
from app.settings import Settings
from app.sources import division_standings, league_injuries, team_info
from app.sources.division_standings import DivisionStandings
from app.sources.http import SourceClient, SourceError
from app.sources.league_injuries import LeagueInjuries
from app.sources.team_info import TeamInfo
from app.sources.team_players import RosterEntry
from app.sources.teams import TEAM_CODES
from app.storage.state import StateStore

KIND = "search"
FEED_ID = "league"
CODES = sorted(set(TEAM_CODES.values()))


class SearchBuildError(Exception):
    """The search feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def short_name(entry: RosterEntry) -> str:
    """The first initial, a period and the last name."""
    return f"{entry.first_name[0]}. {entry.last_name}"


def injury_of(player_id: str, injuries: LeagueInjuries) -> dict[str, object] | None:
    """The player's injury status from the league report; none when not reported."""
    status = roster_status(player_id, injuries)
    return None if status == "active" else {"status": status}


def build_search_feed(
    standings: DivisionStandings,
    colors: Mapping[str, TeamInfo | None],
    rosters: Mapping[str, Sequence[RosterEntry]],
    player_team: Callable[[str], str | None],
    injuries: LeagueInjuries,
) -> SearchFeed:
    """Build the search feed; raise SearchBuildError when it is not valid."""
    teams: list[dict[str, object]] = []
    primaries: dict[str, str | None] = {}
    for code in CODES:
        entry = standings.teams.get(code)
        if entry is None:
            raise SearchBuildError(f"team {code} has no standing")
        info = colors.get(code)
        primaries[code] = f"#{info.color}" if info is not None else None
        teams.append(
            {
                "code": code,
                "city": entry.location,
                "name": entry.name,
                "colors": {
                    "primary": primaries[code],
                    "secondary": (
                        f"#{info.alternate_color}" if info is not None else None
                    ),
                },
                "record": f"{entry.wins}-{entry.losses}",
                "division": entry.division,
                "division_rank": entry.division_order,
            }
        )

    players: list[dict[str, object]] = []
    for code in CODES:
        for member in rosters.get(code, []):
            if player_team(member.player_id) != code:
                continue
            players.append(
                {
                    "id": member.player_id,
                    "name": player_name(member),
                    "short_name": short_name(member),
                    "number": member.jersey,
                    "position": member.position_name,
                    "position_abbr": member.position_abbreviation,
                    "photo_url": member.headshot_url,
                    "injury": injury_of(member.player_id, injuries),
                    "team": {"code": code, "primary": primaries[code]},
                }
            )

    try:
        return SearchFeed.model_validate({"teams": teams, "players": players})
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise SearchBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class SearchFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        stars: StarsJob,
        *,
        fetch_division_standings: FetchDivisionStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_league_injuries: FetchInjuries = league_injuries.fetch_league_injuries,
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._games = games
        self._stars = stars
        self._fetch_division_standings = fetch_division_standings
        self._fetch_league_injuries = fetch_league_injuries
        self._fetch_team_info = fetch_team_info
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        if feed_id != FEED_ID:
            return IdStatus.UNKNOWN
        if not self._stars.rosters_ready():
            return IdStatus.NOT_READY
        return IdStatus.KNOWN

    async def _info(self, code: str) -> TeamInfo | None:
        try:
            return await self._fetch_team_info(self._client, code, self._settings)
        except SourceError:
            return None

    async def build(self, feed_id: str) -> SearchFeed:
        standings = await self._fetch_division_standings(self._client, self._settings)
        injuries = await self._fetch_league_injuries(self._client, self._settings)
        infos = await asyncio.gather(*(self._info(code) for code in CODES))
        return build_search_feed(
            standings,
            dict(zip(CODES, infos, strict=True)),
            self._stars.roster_entries(),
            self._stars.player_team,
            injuries,
        )

    def final_times(self, built_at: dt.datetime, now: dt.datetime) -> list[dt.datetime]:
        """The final times of the league's games that can expire a feed built at built_at."""
        ids = sorted(game.id for game in self._games.final_games())
        times = (self._store.final_time(game_id) for game_id in ids)
        return [time for time in times if time is not None]

    def is_fresh(
        self, feed: SearchFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        latest = self._stars.latest_roster_fetch()
        if latest is not None and latest > built_at:
            return False
        return not feed_expired(built_at, now, self.final_times(built_at, now))

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

    def kind(self) -> FeedKind[SearchFeed]:
        return FeedKind(
            KIND,
            SearchFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
