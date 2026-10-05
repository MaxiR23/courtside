# api/app/jobs/stars.py
#
# Stars job: once a day, in the morning US Eastern time, picks each team's star
# from its current roster and season averages and keeps it in the job state.
# The games job reads the stars through stars_of.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md

import datetime as dt
from collections.abc import Awaitable, Callable, Sequence

import httpx

from app.feeds.games import Star, Stars
from app.jobs.games import EASTERN, eastern_date
from app.jobs.scheduler import utc_now
from app.settings import Settings
from app.sources import team_players
from app.sources.http import SourceError
from app.sources.scoreboard import ScoreboardGame
from app.sources.team_players import PlayerAverages, Roster
from app.sources.teams import TEAM_CODES
from app.storage.state import StateStore

JOB = "stars"
RETRY = dt.timedelta(minutes=5)
# Time one run may spend starting new teams. The scheduler runs the jobs in one
# task, so a long stars run delays the games job's 30 second live cadence (ADR
# 0007). Once it is spent the rest of the due teams wait for the next tick. A
# team already started finishes: its requests are bounded by the HTTP timeout.
RUN_BUDGET = dt.timedelta(seconds=10)

FetchRoster = Callable[[httpx.AsyncClient, str, Settings], Awaitable[Roster]]
FetchSeasonAverages = Callable[
    [httpx.AsyncClient, str, int, Settings], Awaitable[list[PlayerAverages]]
]


def pick_star(
    players: Sequence[Star], averages: Sequence[PlayerAverages]
) -> Star | None:
    """Return the roster player with the best points + rebounds + assists.

    The first in roster order wins a tie. A player not on the roster is never
    returned. None when no roster player has averages.
    """
    by_id = {a.player_id: a for a in averages}
    best: Star | None = None
    best_total = 0.0
    for player in players:
        found = by_id.get(player.player_id)
        if found is None:
            continue
        total = found.points + found.rebounds + found.assists
        if best is None or total > best_total:
            best, best_total = player, total
    return best


class StarsJob:
    name = JOB

    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: httpx.AsyncClient,
        *,
        fetch_roster: FetchRoster = team_players.fetch_roster,
        fetch_season_averages: FetchSeasonAverages = team_players.fetch_season_averages,
        clock: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._fetch_roster = fetch_roster
        self._fetch_season_averages = fetch_season_averages
        self._clock = clock
        self._stars: dict[str, Star] = store.stars()
        self._daily_fetched_at: dt.datetime | None = None
        self._pending: list[str] = []
        self._failed_at: dict[str, dt.datetime] = {}

    def _daily_due(self, now: dt.datetime, today: dt.date) -> bool:
        if self._daily_fetched_at is None:
            return True
        morning = dt.datetime.combine(
            today, self._settings.daily_fetch_time, tzinfo=EASTERN
        )
        return now >= morning > self._daily_fetched_at

    async def _update_team(self, code: str) -> None:
        roster = await self._fetch_roster(self._client, code, self._settings)
        stored = self._stars.get(code)
        if stored is not None and stored.player_id not in {
            p.player_id for p in roster.players
        }:
            self._store.delete_star(code)
            del self._stars[code]
        star: Star | None = None
        for season in (roster.season, roster.season - 1):
            averages = await self._fetch_season_averages(
                self._client, roster.team_id, season, self._settings
            )
            star = pick_star(roster.players, averages)
            if star is not None:
                break
        if star is None:
            raise SourceError(
                team_players.SOURCE,
                f"team {code} has no season averages for its current roster",
            )
        self._store.set_star(star)
        self._stars[code] = star

    async def run(self, now: dt.datetime) -> None:
        if self._daily_due(now, eastern_date(now)):
            self._pending = list(dict.fromkeys(TEAM_CODES.values()))
            self._failed_at = {}
            self._daily_fetched_at = now
        due = [
            code
            for code in self._pending
            if code not in self._failed_at or now - self._failed_at[code] >= RETRY
        ]
        if not due:
            return
        failure: str | None = None
        started = self._clock()
        for code in due:
            if self._clock() - started >= RUN_BUDGET:
                break
            try:
                await self._update_team(code)
            except SourceError as error:
                self._failed_at[code] = now + (self._clock() - started)
                failure = str(error)
            else:
                self._pending.remove(code)
                self._failed_at.pop(code, None)
        if failure is not None:
            self._store.record_failure(JOB, now, failure)
        # A run that leaves teams pending (cut by the budget, or a team waiting for
        # its retry) records no success: health must not report the stars as done.
        elif not self._pending:
            self._store.record_success(JOB, now)

    def stars_of(self, game: ScoreboardGame) -> Stars | None:
        away = self._stars.get(game.away.code)
        home = self._stars.get(game.home.code)
        if away is None or home is None:
            return None
        return Stars(away=away, home=home)
