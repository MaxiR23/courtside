# api/app/jobs/season_cup_feed.py
#
# Cup feed of a past season (ADR 0045): the Cup feed's shape, built by the Cup
# feed builder from the sources of that season (read_cup_sources), with the
# schedules resolved by provider id first as the past season feeds do (ADR 0043).
# The Cup begins with the 2023-24 season (season 2024). A past Cup is stored only
# when it builds as complete: a Cup that is not complete fails the build and
# nothing is stored, because the feed is kept for good. Game detail is never
# available.
#
# SeasonCupFeeds is the feed kind of the on-demand cache: the id is the season's
# end year, the feed is stored at feeds/season-cup/{season}.json only when
# requested. A season is valid from 2024 to the season before the current one
# (past_cup_season_status). The current season is resolved before the cache
# (target) to the current Cup feed, as the calendar's current is (ADR 0042). A
# feed is built once and kept (rule G): it is never deleted, and rebuilt only when
# its build version is not the current one (ADR 0053).
#
# SEE: docs/api/cup.md, docs/adr/0045-season-competition-feeds.md,
# api/app/jobs/cup_feed.py

import dataclasses
import datetime as dt
import functools

from app.feeds.cup import CupFeed, CupStage
from app.jobs import cup_feed
from app.jobs.cup_feed import (
    CupBuildError,
    FetchConferenceTable,
    FetchGroupTable,
    FetchGroupTeams,
    FetchSeasonSchedule,
    build_cup_feed,
    read_cup_sources,
)
from app.jobs.on_demand import (
    FeedCache,
    FeedKind,
    IdStatus,
    is_current_build,
    with_build_version,
)
from app.jobs.season_standings_feed import past_season_status
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources import cup, team_schedule
from app.sources.http import SourceClient
from app.storage.feeds import read_by_id
from app.storage.state import StateStore

KIND = "season-cup"
FIRST_CUP_SEASON = 2024


def past_cup_season_status(text: str, current: int | None) -> IdStatus:
    """past_season_status with the Cup's first season: unknown before 2024."""
    status = past_season_status(text, current)
    if status is not IdStatus.UNKNOWN and int(text) < FIRST_CUP_SEASON:
        return IdStatus.UNKNOWN
    return status


class SeasonCupFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        stars: StarsJob,
        *,
        fetch_group_teams: FetchGroupTeams = cup.fetch_group_teams,
        fetch_group_table: FetchGroupTable = cup.fetch_group_table,
        fetch_conference_table: FetchConferenceTable = cup.fetch_conference_table,
        fetch_season_schedule: FetchSeasonSchedule = team_schedule.fetch_season_schedule,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._fetch_group_teams = fetch_group_teams
        self._fetch_group_table = fetch_group_table
        self._fetch_conference_table = fetch_conference_table
        self._fetch_season_schedule = fetch_season_schedule
        cache.register(self.kind())

    def check(self, season: str) -> IdStatus:
        return past_cup_season_status(season, self._stars.current_season())

    def target(self, season: str) -> tuple[str, str]:
        """The (kind, id) a route season maps to: the current season is the
        current Cup feed."""
        current = self._stars.current_season()
        if current is not None and season == str(current):
            return cup_feed.KIND, cup_feed.FEED_ID
        return KIND, season

    async def build(self, season: str) -> CupFeed:
        sources = await read_cup_sources(
            self._client,
            self._settings,
            int(season),
            fetch_group_teams=self._fetch_group_teams,
            fetch_group_table=self._fetch_group_table,
            fetch_conference_table=self._fetch_conference_table,
            fetch_season_schedule=functools.partial(
                self._fetch_season_schedule, by_id_first=True
            ),
        )
        feed = build_cup_feed(dataclasses.replace(sources, past=True))
        if feed.stage is not CupStage.COMPLETE:
            raise CupBuildError(f"the {season} Cup is not complete")
        return with_build_version(feed)

    def stored(self, season: str) -> CupFeed | None:
        """The stored Cup feed of a season, or none when missing or invalid."""
        body = read_by_id(self._settings.data_dir, KIND, season)
        if body is None:
            return None
        try:
            return CupFeed.model_validate_json(body)
        except ValueError:
            return None

    def is_fresh(self, feed: CupFeed, built_at: dt.datetime, now: dt.datetime) -> bool:
        return is_current_build(feed)

    def keep(self, feed_id: str) -> bool:
        return True

    def kind(self) -> FeedKind[CupFeed]:
        return FeedKind(
            KIND,
            CupFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
