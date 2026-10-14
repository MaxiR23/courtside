# api/app/jobs/all_star_discovery.py
#
# All-Star discovery job: once a day, with the daily fetch, finds the day of the
# All-Star games of the current season, and of the previous season once, by
# reading the scoreboard days from February 1 to March 7 of the season's end year
# in order, until a day has All-Star games. It stores the date and the game ids
# of the edition in the job state and never scans a season again once it is
# stored; a season with no All-Star game yet is scanned again at the next daily
# run. It runs in the task of the stars job, after it, so its reads never delay
# the live refresh (ADR 0014), and it does nothing until the stars job knows the
# season. A failed read records the failure, keeps what is stored and is retried
# five minutes later. The feed kind reads the time of the last completed run to
# expire a feed built before the edition.
#
# SEE: docs/api/all-star.md, docs/adr/0036-all-star-feed.md,
# docs/source-rules.md, api/app/jobs/stars.py

import datetime as dt
from collections.abc import Awaitable, Callable

from app.jobs.games import EASTERN, eastern_date
from app.jobs.stars import StarsJob
from app.settings import Settings
from app.sources import all_star_scoreboard
from app.sources.all_star_scoreboard import AllStarScoreboardGame
from app.sources.http import SourceClient, SourceError
from app.storage.state import AllStarEditionRecord, StateStore

JOB = "all-star-discovery"
RETRY = dt.timedelta(minutes=5)
SCAN_START = (2, 1)
SCAN_END = (3, 7)

FetchAllStarGames = Callable[
    [SourceClient, dt.date, Settings], Awaitable[list[AllStarScoreboardGame]]
]


def scan_days(season: int) -> list[dt.date]:
    """The days to scan for the edition of a season: February 1 to March 7 of its
    end year."""
    first = dt.date(season, *SCAN_START)
    last = dt.date(season, *SCAN_END)
    return [first + dt.timedelta(days=n) for n in range((last - first).days + 1)]


class AllStarDiscovery:
    name = JOB

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        stars: StarsJob,
        *,
        fetch_all_star_games: FetchAllStarGames = (
            all_star_scoreboard.fetch_all_star_games
        ),
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._stars = stars
        self._fetch_all_star_games = fetch_all_star_games
        self._daily_fetched_at: dt.datetime | None = None
        self._failed_at: dt.datetime | None = None
        self._last_run: dt.datetime | None = None
        self._ready_season: int | None = None

    def _daily_due(self, now: dt.datetime, today: dt.date) -> bool:
        if self._daily_fetched_at is None:
            return True
        morning = dt.datetime.combine(
            today, self._settings.daily_fetch_time, tzinfo=EASTERN
        )
        return now >= morning > self._daily_fetched_at

    async def _discover(self, season: int) -> None:
        if self._store.all_star_edition(season) is not None:
            return
        for day in scan_days(season):
            games = await self._fetch_all_star_games(self._client, day, self._settings)
            if games:
                self._store.set_all_star_edition(season, day, [g.id for g in games])
                return

    async def run(self, now: dt.datetime) -> None:
        season = self._stars.current_season()
        if season is None:
            return
        if self._failed_at is not None and now - self._failed_at < RETRY:
            return
        due = (
            self._failed_at is not None
            or season != self._ready_season
            or self._daily_due(now, eastern_date(now))
        )
        if not due:
            return
        try:
            for wanted in (season, season - 1):
                await self._discover(wanted)
        except SourceError as error:
            self._store.record_failure(JOB, now, str(error))
            self._failed_at = now
            return
        self._store.record_success(JOB, now)
        self._last_run = self._client.clock()
        self._ready_season = season
        self._daily_fetched_at = now
        self._failed_at = None

    def last_run(self) -> dt.datetime | None:
        """The end of the last completed run, or none before the first."""
        return self._last_run

    def ready(self) -> bool:
        """True once a run completed for the current season."""
        season = self._stars.current_season()
        return season is not None and season == self._ready_season

    def edition(self, season: int) -> AllStarEditionRecord | None:
        """The stored edition of a season, or none."""
        return self._store.all_star_edition(season)
