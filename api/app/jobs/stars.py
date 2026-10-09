# api/app/jobs/stars.py
#
# Stars job: once a day, in the morning US Eastern time, picks each team's star
# from its current roster and season averages and keeps it in the job state.
# It runs in its own task and fetches the due teams concurrently. A team's roster
# and season leaders keep the adapters' 24-hour freshness (rule A of
# docs/source-rules.md). When no roster player is among the season leaders, the roster players'
# individual averages are used: each stays fresh until the team has a final
# game, known through final_games, whose final time is after the fetch (rule F),
# so such a team costs at most one request per player per game played. A star is
# only replaced by a newly picked one: a failed team keeps its last known star.
# The games job reads the stars through stars_of and waits for has_every_star
# before its first feed (a guest side has no star, ADR 0025). It records the players of every roster it fetches, with
# their team, for the player feed's ids (rule I), keeps each roster's entries and
# the time of the latest roster fetch for the search feed, and calls after_run
# after a run with due teams.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/adr/0014-star-guarantees.md, docs/source-rules.md, docs/adr/0020-source-rules.md

import asyncio
import datetime as dt
from collections.abc import Awaitable, Callable, Sequence

from app.feeds.games import Star, Stars
from app.jobs.games import EASTERN, AfterRun, eastern_date, no_after_run
from app.jobs.scheduler import utc_now
from app.settings import Settings
from app.sources import team_players
from app.sources.http import Freshness, SourceClient, SourceError
from app.sources.scoreboard import ScoreboardGame
from app.sources.team_players import PlayerAverages, Roster, RosterEntry
from app.sources.teams import TEAM_CODES
from app.storage.state import StateStore

JOB = "stars"
RETRY = dt.timedelta(minutes=5)

# Passed as the freshness of a team with no known final game: every stored entry
# was fetched after it, so it stays fresh.
NO_FINAL_GAME = dt.datetime.min.replace(tzinfo=dt.UTC)

FetchRoster = Callable[[SourceClient, str, Settings], Awaitable[Roster]]
FetchSeasonAverages = Callable[
    [SourceClient, str, int, Settings], Awaitable[list[PlayerAverages]]
]
FetchPlayerAverages = Callable[
    [SourceClient, str, int, Settings, Freshness], Awaitable[PlayerAverages | None]
]
FinalGames = Callable[[], Sequence[ScoreboardGame]]


def no_final_games() -> list[ScoreboardGame]:
    """Default when no final games provider is given: individual averages then never expire."""
    return []


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
        client: SourceClient,
        *,
        fetch_roster: FetchRoster = team_players.fetch_roster,
        fetch_season_averages: FetchSeasonAverages = team_players.fetch_season_averages,
        fetch_player_averages: FetchPlayerAverages = team_players.fetch_player_averages,
        final_games: FinalGames = no_final_games,
        clock: Callable[[], dt.datetime] = utc_now,
        after_run: AfterRun = no_after_run,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._fetch_roster = fetch_roster
        self._fetch_season_averages = fetch_season_averages
        self._fetch_player_averages = fetch_player_averages
        self._final_games = final_games
        self._clock = clock
        self._after_run = after_run
        self._player_teams: dict[str, str] = {}
        self._roster_fetched: set[str] = set()
        self._roster_entries: dict[str, list[RosterEntry]] = {}
        self._latest_roster_fetch: dt.datetime | None = None
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

    def _latest_final_time(self, code: str) -> dt.datetime:
        """The final time of the team's latest final game known to the games job."""
        times = [
            final_time
            for game in self._final_games()
            if code in (game.away.code, game.home.code)
            and (final_time := self._store.final_time(game.id)) is not None
        ]
        return max(times, default=NO_FINAL_GAME)

    async def _update_team(self, code: str) -> None:
        roster = await self._fetch_roster(self._client, code, self._settings)
        self._player_teams = {p: t for p, t in self._player_teams.items() if t != code}
        for member in roster.players:
            self._player_teams[member.player_id] = code
        self._roster_fetched.add(code)
        self._roster_entries[code] = list(roster.entries)
        self._latest_roster_fetch = self._clock()
        star: Star | None = None
        individual_error: SourceError | None = None
        for season in (roster.season, roster.season - 1):
            leaders = await self._fetch_season_averages(
                self._client, roster.team_id, season, self._settings
            )
            if not leaders:
                continue  # the provider has no statistics for that season yet
            star = pick_star(roster.players, leaders)
            if star is None:
                individual: list[PlayerAverages] = []
                fresh = self._latest_final_time(code)
                try:
                    for member in roster.players:
                        found = await self._fetch_player_averages(
                            self._client,
                            member.player_id,
                            season,
                            self._settings,
                            fresh,
                        )
                        if found is not None:
                            individual.append(found)
                except SourceError as error:
                    individual_error = error
                    continue  # try the next season before giving up
                star = pick_star(roster.players, individual)
            if star is not None:
                break
        if star is None:
            if individual_error is not None:
                raise individual_error
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
        started = self._clock()

        async def attempt(code: str) -> str | None:
            try:
                await self._update_team(code)
            except SourceError as error:
                self._failed_at[code] = now + (self._clock() - started)
                return str(error)
            self._pending.remove(code)
            self._failed_at.pop(code, None)
            return None

        results = await asyncio.gather(*(attempt(code) for code in due))
        failures = [result for result in results if result is not None]
        if failures:
            self._store.record_failure(JOB, now, failures[-1])
        # A run that leaves a team waiting for its retry records no success: health
        # must not report the stars as done.
        elif not self._pending:
            self._store.record_success(JOB, now)
        self._after_run()

    def has_every_star(self) -> bool:
        """True once every team has a star, stored or fetched."""
        return all(code in self._stars for code in TEAM_CODES.values())

    def player_team(self, player_id: str) -> str | None:
        """The standard code of the team whose latest fetched roster lists the player."""
        return self._player_teams.get(player_id)

    def rosters_ready(self) -> bool:
        """True once every team's roster has been fetched."""
        return all(code in self._roster_fetched for code in TEAM_CODES.values())

    def roster_entries(self) -> dict[str, list[RosterEntry]]:
        """The entries of each team's latest fetched roster, by standard code."""
        return {code: list(entries) for code, entries in self._roster_entries.items()}

    def latest_roster_fetch(self) -> dt.datetime | None:
        """When the latest roster was fetched; none before the first."""
        return self._latest_roster_fetch

    def stars_of(self, game: ScoreboardGame) -> Stars | None:
        away = (
            None
            if game.away.guest or game.away.code is None
            else self._stars.get(game.away.code)
        )
        home = (
            None
            if game.home.guest or game.home.code is None
            else self._stars.get(game.home.code)
        )
        if (away is None and not game.away.guest) or (
            home is None and not game.home.guest
        ):
            return None
        return Stars(away=away, home=home)
