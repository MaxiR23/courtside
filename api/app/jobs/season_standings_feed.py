# api/app/jobs/season_standings_feed.py
#
# Standings feed of a past season (ADR 0043): the standings feed's shape, built
# from the division standings of that season, with the state final and the
# source's clinchers. Colors are today's, from team info, and null when a read
# fails. past_season_status is the check the three season kinds share: a season
# is four digits from 1994 to the season before the current one; the current
# season and later are unknown, and the answer is not ready while the stars job
# does not know the current season.
#
# SeasonStandingsFeeds is the feed kind of the on-demand cache: the id is the
# season's end year, the feed is stored at feeds/season-standings/{season}.json
# only when requested. A feed is built once and kept (rule G): it is never
# deleted, and rebuilt only when its build version is not the current one (ADR
# 0053). Each row is named by that season's team object (city and name) with
# today's code (ADR 0053).
#
# SEE: docs/api/standings.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# api/app/jobs/standings_feed.py

import asyncio
import datetime as dt
import re
from collections.abc import Awaitable, Callable

from app.feeds.calendar import FIRST_SEASON
from app.feeds.standings import StandingsFeed
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.standings_feed import build_standings_feed
from app.jobs.stars import StarsJob
from app.jobs.team_feed import FetchInfo
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources import division_standings, team_info
from app.sources.division_standings import DivisionStandings
from app.sources.http import SourceClient, SourceError
from app.sources.team_info import TeamInfo
from app.storage.state import StateStore

KIND = "season-standings"
_SEASON_ID = re.compile(r"[0-9]{4}")

FetchSeasonStandings = Callable[..., Awaitable[DivisionStandings]]


def past_season_status(text: str, current: int | None) -> IdStatus:
    """The status of a season id: unknown unless four digits from 1994 and before
    the current season; not ready while the current season is not known."""
    if _SEASON_ID.fullmatch(text) is None or int(text) < FIRST_SEASON:
        return IdStatus.UNKNOWN
    if current is None:
        return IdStatus.NOT_READY
    return IdStatus.UNKNOWN if int(text) >= current else IdStatus.KNOWN


class SeasonStandingsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        names: TeamNamesFeeds,
        *,
        fetch_division_standings: FetchSeasonStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._names = names
        self._fetch_division_standings = fetch_division_standings
        self._fetch_team_info = fetch_team_info
        cache.register(self.kind())

    def check(self, season: str) -> IdStatus:
        return past_season_status(season, self._stars.current_season())

    async def _info(self, code: str) -> TeamInfo | None:
        try:
            return await self._fetch_team_info(self._client, code, self._settings)
        except SourceError:
            return None

    async def build(self, season: str) -> StandingsFeed:
        standings = await self._fetch_division_standings(
            self._client, self._settings, season=int(season)
        )
        codes = list(standings.teams)
        infos = await asyncio.gather(*(self._info(code) for code in codes))
        season_names = await self._names.season_names(codes, int(season))
        named = standings.model_copy(
            update={
                "teams": {
                    code: entry
                    if code not in season_names
                    else entry.model_copy(
                        update={
                            "name": season_names[code][0],
                            "location": season_names[code][1],
                        }
                    )
                    for code, entry in standings.teams.items()
                }
            }
        )
        return with_build_version(
            build_standings_feed(
                named, dict(zip(codes, infos, strict=True)), final=True
            )
        )

    def is_fresh(
        self, feed: StandingsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return is_current_build(feed)

    def keep(self, season: str) -> bool:
        return True

    def kind(self) -> FeedKind[StandingsFeed]:
        return FeedKind(
            KIND,
            StandingsFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
