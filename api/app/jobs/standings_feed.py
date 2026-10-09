# api/app/jobs/standings_feed.py
#
# Standings feed builder: a pure function from the division standings and the
# team colors to the standings feed, with every conversion the contract needs:
# the conference ranking by seed (a seed of 0 or none is no seed and goes last,
# then the provider's conference order), the conference games behind from wins
# and losses, the division games behind and division order as the provider
# sends them, win percentages, one-decimal points and games behind, signed
# differentials with the minus sign U+2212, the season label and the state. A
# team with no game has null pct, streak and games behind. It reads no clock and
# no source. StandingsFeeds is the feed kind of the on-demand cache: the only id
# is "league", the feed is stored at feeds/standings/league.json only when
# requested, and it expires 1 hour after a final game of the league that
# follows the build and 7 days after the build (rule G). Colors come from team
# info, one read per team, and are null when a read fails. The feed is never
# deleted.
#
# SEE: docs/api/standings.md, docs/source-rules.md, api/app/jobs/team_feed.py

import asyncio
import datetime as dt
from collections.abc import Mapping, Sequence

from pydantic import ValidationError

from app.feeds.game_detail import Conference
from app.feeds.standings import (
    PerGameDifferential,
    StandingsFeed,
    StandingsState,
    TotalDifferential,
)
from app.jobs.games import GamesJob
from app.jobs.on_demand import FeedCache, FeedKind, IdStatus
from app.jobs.team_feed import (
    FetchDivisionStandings,
    FetchInfo,
    TeamBuildError,
    conference_games_behind,
    feed_expired,
    season_label,
)
from app.jobs.team_feed import streak as parse_streak
from app.settings import Settings
from app.sources import division_standings, team_info
from app.sources.division_standings import DivisionEntry, DivisionStandings
from app.sources.http import SourceClient, SourceError
from app.sources.team_info import TeamInfo
from app.storage.state import StateStore

KIND = "standings"
FEED_ID = "league"
REGULAR_SEASON_GAMES = 82
MINUS = "−"
CONFERENCE_NAMES = {
    Conference.EAST: "Eastern Conference",
    Conference.WEST: "Western Conference",
}


class StandingsBuildError(Exception):
    """The standings feed built from the fetched data is not valid."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def seed_of(entry: DivisionEntry) -> int | None:
    """The seed of a team; 0 (before the first game) and none are no seed."""
    return entry.playoff_seed or None


def pct_text(wins: int, losses: int) -> str | None:
    """The share of games won to three decimals without the leading zero; none with no games."""
    games = wins + losses
    if games == 0:
        return None
    return f"{wins / games:.3f}".removeprefix("0")


def one_decimal(value: float) -> str:
    return f"{value:.1f}"


def signed_per_game(value: float) -> PerGameDifferential:
    """The per game differential to one decimal, signed; zero has no sign."""
    rounded = round(value, 1)
    if rounded == 0:
        return PerGameDifferential(value="0.0", non_negative=True)
    sign = "+" if rounded > 0 else MINUS
    return PerGameDifferential(
        value=f"{sign}{abs(rounded):.1f}", non_negative=rounded > 0
    )


def signed_total(value: float) -> TotalDifferential:
    """The total differential rounded to a whole number, signed; zero has no sign."""
    rounded = round(value)
    if rounded == 0:
        return TotalDifferential(value="0", non_negative=True)
    sign = "+" if rounded > 0 else MINUS
    return TotalDifferential(value=f"{sign}{abs(rounded)}", non_negative=rounded > 0)


def division_games_behind(text: str | None) -> str | None:
    """The provider's games behind in the division with one decimal; a dash or none is the leader."""
    if text is None or text == "-":
        return None
    try:
        return one_decimal(float(text))
    except ValueError:
        raise StandingsBuildError(f"games behind {text!r} is not a number") from None


def conference_order_key(entry: DivisionEntry) -> tuple[bool, int, int]:
    """Seeded teams by seed, then teams with no seed; ties in the provider's conference order."""
    seed = seed_of(entry)
    return (seed is None, seed or 0, entry.conference_order)


def leader_of(entries: Sequence[DivisionEntry]) -> DivisionEntry:
    """The team with the best wins minus losses; ties go to the better seed."""
    return min(
        entries,
        key=lambda entry: (-(entry.wins - entry.losses), *conference_order_key(entry)),
    )


def conference_games_behind_text(
    entry: DivisionEntry, leader: DivisionEntry, members: Sequence[DivisionEntry]
) -> str | None:
    """Games behind the leader of the conference with one decimal; none for the leader."""
    if entry is leader:
        return None
    return one_decimal(conference_games_behind(entry, members))


def _row(
    entry: DivisionEntry, info: TeamInfo | None, games_behind: str | None
) -> dict[str, object]:
    played = entry.wins + entry.losses > 0
    try:
        streak = parse_streak(entry.streak) if played and entry.streak else None
    except TeamBuildError as error:
        raise StandingsBuildError(error.reason) from None
    colors = (
        {"primary": f"#{info.color}", "secondary": f"#{info.alternate_color}"}
        if info is not None
        else {"primary": None, "secondary": None}
    )
    return {
        "code": entry.code,
        "city": entry.location,
        "name": entry.name,
        "colors": colors,
        "seed": seed_of(entry),
        "clinch": entry.clinch,
        "wins": entry.wins,
        "losses": entry.losses,
        "pct": pct_text(entry.wins, entry.losses),
        "games_behind": games_behind if played else None,
        "streak": streak,
        "home": entry.home,
        "away": entry.road,
        "last_ten": entry.last_ten,
        "division": entry.vs_division,
        "conference": entry.vs_conference,
        "points_for": one_decimal(entry.avg_points_for),
        "points_against": one_decimal(entry.avg_points_against),
        "differential": signed_per_game(entry.differential),
        "total": signed_total(entry.point_differential),
    }


def build_standings_feed(
    standings: DivisionStandings, colors: Mapping[str, TeamInfo | None]
) -> StandingsFeed:
    """Build the standings feed; raise StandingsBuildError when it is not valid."""
    entries = list(standings.teams.values())

    conferences = []
    for conference in (Conference.EAST, Conference.WEST):
        members = sorted(
            (entry for entry in entries if entry.conference is conference),
            key=conference_order_key,
        )
        leader = leader_of(members) if members else None
        rows = [
            _row(
                entry,
                colors.get(entry.code),
                conference_games_behind_text(entry, leader, members)
                if leader
                else None,
            )
            for entry in members
        ]
        conferences.append(
            {
                "key": conference,
                "name": CONFERENCE_NAMES[conference],
                "team_count": len(rows),
                "teams": rows,
            }
        )

    # Divisions in the provider's order: provider order runs over the whole
    # league, division by division, in the order the provider sends them.
    groups: dict[tuple[Conference, str], list[DivisionEntry]] = {}
    for entry in sorted(entries, key=lambda e: e.provider_order):
        groups.setdefault((entry.conference, entry.division), []).append(entry)
    divisions = [
        {
            "name": name,
            "conference": conference,
            "teams": [
                _row(
                    entry,
                    colors.get(entry.code),
                    division_games_behind(entry.games_behind),
                )
                for entry in sorted(members, key=lambda e: e.division_order)
            ],
        }
        for (conference, name), members in groups.items()
    ]

    final = standings.fallback or all(
        entry.wins + entry.losses == REGULAR_SEASON_GAMES for entry in entries
    )
    try:
        return StandingsFeed.model_validate(
            {
                "season": season_label(standings.season),
                "state": StandingsState.FINAL if final else StandingsState.REGULAR,
                "games_played": sum(entry.wins for entry in entries),
                "conferences": conferences,
                "divisions": divisions,
            }
        )
    except ValidationError as error:
        location = ".".join(str(part) for part in error.errors()[0]["loc"])
        raise StandingsBuildError(
            f"invalid feed: {error.error_count()} errors, first at {location}"
        ) from None


class StandingsFeeds:
    def __init__(
        self,
        settings: Settings,
        store: StateStore,
        client: SourceClient,
        cache: FeedCache,
        games: GamesJob,
        *,
        fetch_division_standings: FetchDivisionStandings = (
            division_standings.fetch_division_standings
        ),
        fetch_team_info: FetchInfo = team_info.fetch_team_info,
    ) -> None:
        self._settings = settings
        self._store = store
        self._client = client
        self._games = games
        self._fetch_division_standings = fetch_division_standings
        self._fetch_team_info = fetch_team_info
        cache.register(self.kind())

    def check(self, feed_id: str) -> IdStatus:
        return IdStatus.KNOWN if feed_id == FEED_ID else IdStatus.UNKNOWN

    async def _info(self, code: str) -> TeamInfo | None:
        try:
            return await self._fetch_team_info(self._client, code, self._settings)
        except SourceError:
            return None

    async def build(self, feed_id: str) -> StandingsFeed:
        standings = await self._fetch_division_standings(self._client, self._settings)
        codes = list(standings.teams)
        infos = await asyncio.gather(*(self._info(code) for code in codes))
        return build_standings_feed(standings, dict(zip(codes, infos, strict=True)))

    def final_times(self, built_at: dt.datetime, now: dt.datetime) -> list[dt.datetime]:
        """The final times of the league's games that can expire a feed built at built_at."""
        ids = sorted(game.id for game in self._games.final_games())
        times = (self._store.final_time(game_id) for game_id in ids)
        return [time for time in times if time is not None]

    def is_fresh(
        self, feed: StandingsFeed, built_at: dt.datetime, now: dt.datetime
    ) -> bool:
        return not feed_expired(built_at, now, self.final_times(built_at, now))

    def keep(self, feed_id: str) -> bool:
        return feed_id == FEED_ID

    def kind(self) -> FeedKind[StandingsFeed]:
        return FeedKind(
            KIND,
            StandingsFeed,
            check=self.check,
            build=self.build,
            is_fresh=self.is_fresh,
            keep=self.keep,
        )
