# api/app/jobs/season_standings_feed.py
#
# Standings feed of a past season (ADR 0043): the standings feed's shape, built
# from the division standings of that season, with the state final and the
# source's clinchers. Colors are today's, from the cached team info (no read),
# and null without it. The build declares a read budget of READ_BUDGET source
# read: the standings. past_season_status is the check the three season kinds share: a season
# is four digits from 1994 to the season before the current one; the current
# season and later are unknown, and the answer is not ready while the stars job
# does not know the current season.
#
# SeasonStandingsFeeds is the feed kind of the on-demand cache: the id is the
# season's end year, the feed is stored at feeds/season-standings/{season}.json
# only when requested. A feed is built once and kept (rule G): it is never
# deleted, and rebuilt only when its build version is not the current one (ADR
# 0053). Each row is named by the standings payload (city and name), with the
# season code of the stored franchise names (ADR 0059).
#
# SEE: docs/api/standings.md, docs/adr/0043-season-feeds-and-franchise-names.md,
# api/app/jobs/standings_feed.py

import datetime as dt
import re
from collections.abc import Awaitable, Callable, Mapping

from app.feeds.calendar import FIRST_SEASON
from app.feeds.standings import StandingsFeed, StandingsRow
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.standings_feed import build_standings_feed
from app.jobs.stars import StarsJob
from app.jobs.team_names import SeasonIdentity, TeamNamesFeeds, payload_names
from app.settings import Settings
from app.sources import division_standings, team_info
from app.sources.division_standings import DivisionStandings
from app.sources.http import ReadBudget, SourceClient, within_budget
from app.sources.teams import SeasonTeamName
from app.storage.state import StateStore

KIND = "season-standings"
READ_BUDGET = 1
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


def _with_season_codes(
    feed: StandingsFeed, season_names: Mapping[str, SeasonIdentity]
) -> StandingsFeed:
    """The feed with the season code and the historical flag on every row whose
    code the season names know (ADR 0054)."""

    def coded(row: StandingsRow) -> StandingsRow:
        identity = season_names.get(row.code)
        if identity is None:
            return row
        return row.model_copy(
            update={"season_code": identity.code, "historical": identity.historical}
        )

    return feed.model_copy(
        update={
            "conferences": [
                group.model_copy(update={"teams": [coded(row) for row in group.teams]})
                for group in feed.conferences
            ],
            "divisions": [
                group.model_copy(update={"teams": [coded(row) for row in group.teams]})
                for group in feed.divisions
            ],
        }
    )


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
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._names = names
        self._fetch_division_standings = fetch_division_standings
        cache.register(self.kind())

    def check(self, season: str) -> IdStatus:
        return past_season_status(season, self._stars.current_season())

    async def build(self, season: str) -> StandingsFeed:
        return await within_budget(
            ReadBudget(READ_BUDGET),
            f"season standings: {season}",
            lambda: self._build(season),
        )

    async def _build(self, season: str) -> StandingsFeed:
        standings = await self._fetch_division_standings(
            self._client, self._settings, season=int(season)
        )
        infos = {
            code: team_info.cached_team_info(self._client, code, self._settings)
            for code in standings.teams
        }
        identities = {
            code: SeasonTeamName(
                abbreviation=entry.abbreviation,
                name=entry.name,
                location=entry.location,
            )
            for code, entry in standings.teams.items()
            if entry.abbreviation
        }
        runs = {
            code: found for code in identities if (found := self._names.stored(code))
        }
        return with_build_version(
            _with_season_codes(
                build_standings_feed(standings, infos, final=True),
                payload_names(identities, runs),
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
