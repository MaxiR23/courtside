# api/tests/jobs/test_standings_feed.py
#
# Tests for the standings feed builder and its feed kind.
#
# Tested:
# - Formats pct without the leading zero and gives none with no games
# - Formats games behind and points with one decimal
# - Signs the per game and total differentials with + and U+2212, with zero unsigned
# - Reads the provider's division games behind, a dash as none, and rejects text that is not a number
# - Gives a null seed for seed 0 and a missing seed
# - Sorts a conference by seed, keeps the conference order for repeated seeds and puts null seeds last
# - Keeps the provider's division order and lists the divisions with their conference
# - Lists East then West with names and team counts
# - Computes the conference games behind from wins and losses, with the leader null and a tied team 0.0
# - Picks the leader by wins minus losses with ties to the lower seed
# - Keeps the provider's division games behind
# - Gives a 0-0 team null pct, streak and games behind in both groupings
# - Builds colors from team info and null for a team without
# - Labels the season, sums the wins and sets the state (fallback, 82 games, otherwise regular)
# - Wraps an invalid feed in a build error
# - Builds a valid feed from the recorded standings, in season and before the first game
# - The kind: an id other than league answers unknown
# - The kind: no feed is built, stored or fetched without a request
# - The kind: a request builds and stores the feed and a second request reads storage
# - The kind: team info is read once per team and a second build within the hour makes no request
# - The kind: a failed team info read leaves null colors and the build succeeds
# - The kind: a failed standings read with no stored feed answers unavailable and is not retried for 10 minutes
# - The kind: a failed rebuild of a stale feed keeps and serves the stored feed
# - The kind: fresh before a final game of the league plus 1 hour and stale at it
# - The kind: fresh before 7 days and stale at 7 days, and a final game whose hour ended before the build does not expire it
# - The kind: the cleanup keeps league
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_standings_feed.py
#
# SEE: api/app/jobs/standings_feed.py

import asyncio
import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.game_detail import Conference
from app.feeds.games import GameStatus
from app.feeds.standings import StandingsFeed, StandingsState
from app.jobs.games import GamesJob
from app.jobs.on_demand import (
    RETRY_AFTER,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.standings_feed import (
    FEED_ID,
    KIND,
    StandingsBuildError,
    StandingsFeeds,
    build_standings_feed,
    conference_games_behind,
    division_games_behind,
    leader_of,
    one_decimal,
    pct_text,
    seed_of,
    signed_per_game,
    signed_total,
)
from app.jobs.team_feed import FEED_LIFETIME
from app.settings import Settings
from app.sources.division_standings import (
    DivisionEntry,
    DivisionStandings,
    fetch_division_standings,
)
from app.sources.game_detail import GameDetail
from app.sources.http import (
    Freshness,
    SourceClient,
    SourceError,
    create_client,
    get_json,
)
from app.sources.scoreboard import ScoreboardGame
from app.sources.team_info import TeamInfo
from app.sources.teams import TEAM_CODES
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_game_detail_feed import games_detail
from tests.jobs.test_team_feed import HOUR, NOW, SECOND, TODAY, info, scoreboard

FIXTURES = Path(__file__).parent.parent / "sources" / "fixtures"
SOURCE = "https://example.com/source/"
MINUS = "−"


def team(code: str, **changes: Any) -> DivisionEntry:
    values: dict[str, Any] = {
        "code": code,
        "location": code.title(),
        "name": "Team",
        "display_name": f"{code.title()} Team",
        "conference": Conference.EAST,
        "division": "Atlantic",
        "division_order": 1,
        "conference_order": 1,
        "provider_order": 1,
        "wins": 40,
        "losses": 20,
        "playoff_seed": 1,
        "streak": "W3",
        "games_behind": "-",
        "home": "22-8",
        "road": "18-12",
        "last_ten": "7-3",
        "avg_points_for": 118.04,
        "avg_points_against": 107.92,
        "points_for": 7082,
        "points_against": 6475,
        "differential": 10.1,
        "point_differential": 607,
        "vs_division": "10-2",
        "vs_conference": "25-9",
        "clinch": None,
    }
    return DivisionEntry.model_validate(values | changes)


def league(
    *entries: DivisionEntry, season: int = 2026, fallback: bool = False
) -> DivisionStandings:
    return DivisionStandings(
        season=season, fallback=fallback, teams={entry.code: entry for entry in entries}
    )


def small() -> list[DivisionEntry]:
    """Two East divisions (Atlantic, Central) and one West division."""
    return [
        team(
            "AAA",
            division="Atlantic",
            division_order=1,
            conference_order=1,
            provider_order=1,
            playoff_seed=3,
        ),
        team(
            "BBB",
            division="Atlantic",
            division_order=2,
            conference_order=2,
            provider_order=2,
            playoff_seed=1,
        ),
        team(
            "CCC",
            division="Central",
            division_order=1,
            conference_order=3,
            provider_order=3,
            playoff_seed=2,
        ),
        team(
            "DDD",
            conference=Conference.WEST,
            division="Pacific",
            division_order=1,
            conference_order=1,
            provider_order=4,
        ),
    ]


def built(*entries: DivisionEntry, **kwargs: Any) -> StandingsFeed:
    return build_standings_feed(league(*(entries or small()), **kwargs), {})


def east(feed: StandingsFeed) -> list[str]:
    return [row.code for row in feed.conferences[0].teams]


def test_formats_pct_without_the_leading_zero_and_gives_none_with_no_games() -> None:
    assert pct_text(54, 28) == ".659"
    assert pct_text(82, 0) == "1.000"
    assert pct_text(0, 10) == ".000"
    assert pct_text(0, 0) is None


def test_formats_games_behind_and_points_with_one_decimal() -> None:
    assert one_decimal(4.5) == "4.5"
    assert one_decimal(118.04) == "118.0"
    assert one_decimal(0) == "0.0"


def test_signs_the_per_game_differential_with_plus_and_the_minus_sign() -> None:
    positive = signed_per_game(4.44)
    negative = signed_per_game(-4.4)

    assert (positive.value, positive.non_negative) == ("+4.4", True)
    assert (negative.value, negative.non_negative) == (f"{MINUS}4.4", False)
    assert negative.value[0] != "-"


def test_gives_a_per_game_differential_that_rounds_to_zero_no_sign() -> None:
    for value in (0.0, -0.0, -0.04, 0.04):
        zero = signed_per_game(value)
        assert (zero.value, zero.non_negative) == ("0.0", True)


def test_signs_the_total_differential() -> None:
    assert signed_total(631).value == "+631"
    assert signed_total(-312).value == f"{MINUS}312"
    assert signed_total(-312).non_negative is False
    zero = signed_total(0)
    assert (zero.value, zero.non_negative) == ("0", True)
    assert signed_total(-0.4).value == "0"


def test_reads_the_division_games_behind_with_a_dash_as_none() -> None:
    assert division_games_behind("-") is None
    assert division_games_behind(None) is None
    assert division_games_behind("3") == "3.0"
    assert division_games_behind("2.5") == "2.5"


def test_rejects_division_games_behind_that_is_not_a_number() -> None:
    with pytest.raises(StandingsBuildError, match="not a number"):
        division_games_behind("x")


def test_gives_a_null_seed_for_seed_0_and_a_missing_seed() -> None:
    assert seed_of(team("AAA", playoff_seed=0)) is None
    assert seed_of(team("AAA", playoff_seed=None)) is None
    assert seed_of(team("AAA", playoff_seed=7)) == 7


def test_sorts_a_conference_by_seed_with_a_seed_above_a_team_with_more_wins() -> None:
    feed = built(
        team("AAA", wins=50, losses=10, playoff_seed=2),
        team("BBB", wins=30, losses=30, playoff_seed=1, conference_order=2),
        team("DDD", conference=Conference.WEST),
    )

    assert east(feed) == ["BBB", "AAA"]
    assert [row.seed for row in feed.conferences[0].teams] == [1, 2]


def test_keeps_the_conference_order_for_repeated_seeds() -> None:
    feed = built(
        team("AAA", playoff_seed=4, conference_order=2),
        team("BBB", playoff_seed=4, conference_order=1),
        team("DDD", conference=Conference.WEST),
    )

    assert east(feed) == ["BBB", "AAA"]


def test_puts_null_seeds_last_in_conference_order() -> None:
    feed = built(
        team("AAA", playoff_seed=None, conference_order=1),
        team("BBB", playoff_seed=0, conference_order=2),
        team("CCC", playoff_seed=9, conference_order=3),
        team("DDD", conference=Conference.WEST),
    )

    assert east(feed) == ["CCC", "AAA", "BBB"]
    assert [row.seed for row in feed.conferences[0].teams] == [9, None, None]


def test_keeps_the_providers_division_order_and_the_conference_seed_in_division_rows() -> (
    None
):
    feed = built(
        team("AAA", division_order=2, conference_order=1, playoff_seed=3),
        team("BBB", division_order=1, conference_order=2, playoff_seed=1),
        team("DDD", conference=Conference.WEST),
    )

    division = feed.divisions[0]
    assert [row.code for row in division.teams] == ["BBB", "AAA"]
    assert [row.seed for row in division.teams] == [1, 3]


def test_lists_the_divisions_in_provider_order_with_their_conference() -> None:
    feed = built()

    assert [(d.name, d.conference) for d in feed.divisions] == [
        ("Atlantic", Conference.EAST),
        ("Central", Conference.EAST),
        ("Pacific", Conference.WEST),
    ]


def test_lists_the_divisions_in_provider_order_even_when_west_comes_first() -> None:
    feed = built(
        team("AAA", division="Atlantic", provider_order=3),
        team(
            "DDD",
            conference=Conference.WEST,
            division="Pacific",
            provider_order=1,
        ),
        team(
            "EEE",
            conference=Conference.WEST,
            division="Southwest",
            provider_order=2,
        ),
    )

    assert [(d.name, d.conference) for d in feed.divisions] == [
        ("Pacific", Conference.WEST),
        ("Southwest", Conference.WEST),
        ("Atlantic", Conference.EAST),
    ]


def test_lists_east_then_west_with_names_and_team_counts() -> None:
    feed = built()

    assert [(c.key, c.name, c.team_count) for c in feed.conferences] == [
        (Conference.EAST, "Eastern Conference", 3),
        (Conference.WEST, "Western Conference", 1),
    ]


def test_computes_the_conference_games_behind_from_wins_and_losses() -> None:
    feed = built(
        team("AAA", wins=50, losses=20, playoff_seed=1),
        team("BBB", wins=45, losses=24, playoff_seed=2, conference_order=2),
        team("CCC", wins=50, losses=20, playoff_seed=3, conference_order=3),
        team("DDD", conference=Conference.WEST),
    )

    behind = {row.code: row.games_behind for row in feed.conferences[0].teams}
    assert behind == {"AAA": None, "BBB": "4.5", "CCC": "0.0"}
    assert feed.conferences[1].teams[0].games_behind is None


def test_picks_the_leader_by_wins_minus_losses_with_ties_to_the_lower_seed() -> None:
    better_seed = team("AAA", wins=50, losses=30, playoff_seed=1)
    better_record = team("BBB", wins=48, losses=22, playoff_seed=2, conference_order=2)
    tied_low = team("CCC", wins=48, losses=22, playoff_seed=1, conference_order=3)
    tied_high = team("DDD", wins=49, losses=23, playoff_seed=4, conference_order=4)

    assert leader_of([better_seed, better_record]) is better_record
    assert leader_of([better_record, tied_low]) is tied_low
    assert leader_of([tied_high, tied_low]) is tied_low
    assert conference_games_behind(better_seed, better_record) == "3.0"
    assert conference_games_behind(better_record, better_record) is None


def test_keeps_the_providers_division_games_behind_with_the_leader_null() -> None:
    feed = built(
        team("AAA", division_order=1, games_behind="-"),
        team("BBB", division_order=2, conference_order=2, games_behind="2.5"),
        team("DDD", conference=Conference.WEST),
    )

    assert [row.games_behind for row in feed.divisions[0].teams] == [None, "2.5"]


def test_gives_a_0_0_team_null_pct_streak_and_games_behind_in_both_groupings() -> None:
    feed = built(
        team("AAA", wins=0, losses=0, playoff_seed=0, streak="-", games_behind="-"),
        team(
            "BBB",
            wins=0,
            losses=0,
            playoff_seed=0,
            conference_order=2,
            games_behind="1",
        ),
        team("DDD", conference=Conference.WEST, wins=0, losses=0),
    )

    for row in [*feed.conferences[0].teams, *feed.divisions[0].teams]:
        assert (row.pct, row.streak, row.games_behind, row.seed) == (
            None,
            None,
            None,
            None,
        )


def test_reads_a_streak_and_the_clinch_of_a_played_team() -> None:
    feed = built(
        team("AAA", streak="L2", clinch="z"),
        team("DDD", conference=Conference.WEST, streak="-"),
    )

    row = feed.conferences[0].teams[0]
    assert (row.streak.kind.value, row.streak.count) == ("loss", 2)  # type: ignore[union-attr]
    assert row.clinch is not None and row.clinch.value == "z"
    assert feed.conferences[1].teams[0].streak is None


def test_builds_the_row_text_from_the_entry() -> None:
    row = built().conferences[0].teams[1]

    assert (row.code, row.city, row.name) == ("CCC", "Ccc", "Team")
    assert (row.home, row.away, row.last_ten) == ("22-8", "18-12", "7-3")
    assert (row.division, row.conference) == ("10-2", "25-9")
    assert (row.pct, row.points_for, row.points_against) == (".667", "118.0", "107.9")
    assert (row.differential.value, row.total.value) == ("+10.1", "+607")


def test_builds_colors_from_team_info_and_null_for_a_team_without() -> None:
    colors = {"AAA": info(), "BBB": None}

    feed = build_standings_feed(league(*small()), colors)

    by_code = {row.code: row.colors for row in feed.conferences[0].teams}
    assert (by_code["AAA"].primary, by_code["AAA"].secondary) == ("#007ac1", "#ef3b24")
    assert (by_code["BBB"].primary, by_code["BBB"].secondary) == (None, None)
    assert (by_code["CCC"].primary, by_code["CCC"].secondary) == (None, None)


def test_labels_the_season_from_the_standings_end_year() -> None:
    assert built(season=2026).season == "2025-26"


def test_sets_the_state_final_from_the_fallback() -> None:
    assert built(fallback=True).state is StandingsState.FINAL


def test_sets_the_state_final_when_every_team_has_82_games() -> None:
    feed = built(
        team("AAA", wins=50, losses=32),
        team("DDD", conference=Conference.WEST, wins=30, losses=52),
    )

    assert feed.state is StandingsState.FINAL


def test_sets_the_state_regular_otherwise() -> None:
    feed = built(
        team("AAA", wins=50, losses=32),
        team("DDD", conference=Conference.WEST, wins=30, losses=51),
    )

    assert feed.state is StandingsState.REGULAR


def test_sets_games_played_to_the_sum_of_the_wins() -> None:
    assert built().games_played == 160


def test_wraps_an_invalid_feed_in_a_build_error() -> None:
    with pytest.raises(StandingsBuildError, match="invalid feed"):
        built(team("AAA", home="home"), team("DDD", conference=Conference.WEST))


def test_wraps_a_streak_it_cannot_read_in_a_build_error() -> None:
    with pytest.raises(StandingsBuildError, match="streak"):
        built(team("AAA", streak="X1"), team("DDD", conference=Conference.WEST))


def recorded(name: str) -> Any:
    return json.loads(
        (FIXTURES / "division_standings" / name).read_text(encoding="utf-8")
    )


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch_recorded(mock: respx.MockRouter, name: str) -> DivisionStandings:
    url = "https://example.com/standings?level=3&seasontype=2"
    mock.get(url).respond(json=recorded(name))
    settings = Settings(_env_file=None, division_standings_url=url)  # type: ignore[call-arg]
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_division_standings(client, settings)


@pytest.mark.anyio
async def test_builds_a_valid_feed_from_the_recorded_season(
    mock: respx.MockRouter,
) -> None:
    standings = await fetch_recorded(mock, "regular-2026.json")

    feed = build_standings_feed(standings, {})

    assert (
        StandingsFeed.model_validate_json(feed.model_dump_json(by_alias=True)) == feed
    )
    assert (feed.season, feed.state) == ("2025-26", StandingsState.FINAL)
    assert [c.team_count for c in feed.conferences] == [15, 15]
    assert len(feed.divisions) == 6
    assert feed.conferences[1].teams[0].code == "OKC"
    assert {row.colors.primary for row in feed.conferences[0].teams} == {None}


@pytest.mark.anyio
async def test_builds_a_valid_feed_before_the_first_game(
    mock: respx.MockRouter,
) -> None:
    standings = await fetch_recorded(mock, "before-first-game.json")

    feed = build_standings_feed(standings, {})

    assert feed.state is StandingsState.REGULAR
    assert feed.games_played == 0
    rows = [row for group in feed.conferences for row in group.teams]
    assert len(rows) == 30
    for row in rows:
        assert (row.seed, row.pct, row.streak, row.games_behind) == (
            None,
            None,
            None,
            None,
        )


def full_league() -> DivisionStandings:
    codes = sorted(set(TEAM_CODES.values()))
    entries = [
        team(
            code,
            conference=Conference.EAST if index < 15 else Conference.WEST,
            division="Atlantic" if index < 15 else "Pacific",
            division_order=index % 15 + 1,
            conference_order=index % 15 + 1,
            playoff_seed=index % 15 + 1,
        )
        for index, code in enumerate(codes)
    ]
    return league(*entries)


class StandingsKit:
    """A games job, a feed cache and the standings kind over one client and one clock.

    Every fake adapter reads one URL through the source cache from a counted
    respx route, so route calls are real source requests.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.requests: list[str] = []
        self.calls: list[str] = []
        self.failing: set[str] = set()
        self.scoreboard: dict[dt.date, list[ScoreboardGame]] = {}
        respx.get(url__startswith=SOURCE).mock(side_effect=self.answer)
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.games = GamesJob(
            self.settings,
            self.store,
            self.client,
            fetch_games=self.fetch_games,
            fetch_game_detail=self.fetch_game_detail,
        )
        self.standings = StandingsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.games,
            fetch_division_standings=self.fetch_division_standings,
            fetch_team_info=self.fetch_team_info,
        )

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request.url.path.removeprefix("/source/"))
        return httpx.Response(200, json={"ok": True})

    async def read(self, name: str, fresh: Freshness) -> None:
        self.calls.append(name)
        if name in self.failing:
            raise SourceError("test", f"{name} is down")
        await get_json(self.client, SOURCE + name, source="test", fresh=fresh)

    def requested(self, prefix: str) -> int:
        return sum(1 for name in self.requests if name.startswith(prefix))

    def called(self, name: str) -> int:
        return self.calls.count(name)

    async def fetch_games(
        self, client: SourceClient, day: dt.date, settings: Settings
    ) -> list[ScoreboardGame]:
        return list(self.scoreboard.get(day, []))

    async def fetch_game_detail(
        self, client: SourceClient, game_id: str, settings: Settings, fresh: Freshness
    ) -> GameDetail:
        return games_detail()

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings
    ) -> DivisionStandings:
        await self.read("standings", HOUR)
        return full_league()

    async def fetch_team_info(
        self, client: SourceClient, team: str, settings: Settings
    ) -> TeamInfo:
        await self.read(f"info/{team}", HOUR)
        return info()

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def run_games(self, at: dt.datetime | None = None) -> None:
        if at is not None:
            self.clock[0] = at
        await self.games.run(self.clock[0])
        await self.settle()

    async def serve(self, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    def stored(self) -> StandingsFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else StandingsFeed.model_validate_json(body)

    def last_build(self) -> dt.datetime | None:
        state = self.store.feed_build(KIND, FEED_ID)
        return None if state is None else state.last_build


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> StandingsKit:
    return StandingsKit(tmp_path)


@pytest.mark.anyio
async def test_an_id_other_than_league_answers_unknown_with_no_build(
    kit: StandingsKit, tmp_path: Path
) -> None:
    for feed_id in ("LEAGUE", "okc", ""):
        assert kit.standings.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await kit.cache.serve(KIND, feed_id)

    assert kit.standings.check("league") is IdStatus.KNOWN
    assert kit.calls == [] and kit.requests == []
    assert not (tmp_path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_no_standings_feed_is_built_stored_or_fetched_without_a_request(
    kit: StandingsKit, tmp_path: Path
) -> None:
    kit.scoreboard[TODAY] = [scoreboard("g1", GameStatus.SCHEDULED, NOW + HOUR)]

    await kit.run_games()
    await kit.run_games(NOW + 30 * SECOND)
    kit.cache.cleanup()
    await kit.settle()

    assert kit.requests == [] and kit.calls == []
    assert not (tmp_path / "feeds" / KIND).exists()
    assert kit.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_a_request_builds_and_stores_the_feed_and_a_second_request_reads_storage(
    kit: StandingsKit,
) -> None:
    first = await kit.serve()
    requests = list(kit.requests)
    second = await kit.serve(NOW + 30 * SECOND)

    assert StandingsFeed.model_validate_json(first).season == "2025-26"
    assert second == first
    assert kit.requests == requests and requests != []
    assert kit.called("standings") == 1
    assert kit.last_build() == NOW
    assert kit.stored() is not None


@pytest.mark.anyio
async def test_reads_team_info_once_per_team_and_a_second_build_within_the_hour_makes_no_request(
    kit: StandingsKit,
) -> None:
    await kit.serve()

    assert kit.requested("info/") == 30
    assert kit.requested("standings") == 1
    requests = len(kit.requests)

    kit.clock[0] = NOW + 10 * SECOND
    await kit.standings.build(FEED_ID)

    assert len(kit.requests) == requests
    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_failed_team_info_read_leaves_that_teams_colors_null_and_the_build_succeeds(
    kit: StandingsKit,
) -> None:
    kit.failing.add("info/OKC")

    feed = StandingsFeed.model_validate_json(await kit.serve())

    rows = {row.code: row for group in feed.conferences for row in group.teams}
    assert rows["OKC"].colors.primary is None
    assert rows["BOS"].colors.primary == "#007ac1"
    assert kit.store.failed_feed_builds() == []


@pytest.mark.anyio
async def test_a_failed_standings_read_answers_unavailable_and_is_not_retried_for_10_minutes(
    kit: StandingsKit,
) -> None:
    kit.failing.add("standings")

    with pytest.raises(FeedUnavailableError):
        await kit.serve()
    await kit.settle()
    kit.clock[0] = NOW + RETRY_AFTER - SECOND
    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.called("standings") == 1
    assert [f.feed_id for f in kit.store.failed_feed_builds()] == [FEED_ID]
    kit.failing.clear()
    body = await kit.serve(NOW + RETRY_AFTER)
    assert StandingsFeed.model_validate_json(body).season == "2025-26"
    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_failed_rebuild_of_a_stale_feed_keeps_and_serves_the_stored_feed(
    kit: StandingsKit,
) -> None:
    first = await kit.serve()
    stored = read_by_id(kit.path, KIND, FEED_ID)
    kit.failing.add("standings")

    body = await kit.serve(NOW + FEED_LIFETIME)

    assert body == first
    assert kit.called("standings") == 2
    assert read_by_id(kit.path, KIND, FEED_ID) == stored
    assert kit.last_build() == NOW
    assert [f.feed_id for f in kit.store.failed_feed_builds()] == [FEED_ID]


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_a_final_game_of_any_teams_plus_1_hour_and_stale_at_it(
    kit: StandingsKit,
) -> None:
    final = NOW + 2 * HOUR
    kit.scoreboard[TODAY] = [
        scoreboard("f1", GameStatus.FINAL, NOW - HOUR, away="BOS", home="NYK")
    ]
    kit.store.set_final_time("f1", TODAY, final)
    await kit.run_games()
    await kit.serve()

    await kit.serve(final + HOUR - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(final + HOUR)

    assert kit.called("standings") == 2
    assert kit.last_build() == final + HOUR


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_7_days_and_stale_at_7_days(
    kit: StandingsKit,
) -> None:
    await kit.serve()

    await kit.serve(NOW + FEED_LIFETIME - SECOND)
    assert kit.called("standings") == 1
    await kit.serve(NOW + FEED_LIFETIME)

    assert kit.called("standings") == 2


@pytest.mark.anyio
async def test_a_final_game_whose_hour_ended_before_the_build_does_not_expire_the_feed(
    kit: StandingsKit,
) -> None:
    kit.scoreboard[TODAY] = [scoreboard("f1", GameStatus.FINAL, NOW - 3 * HOUR)]
    kit.store.set_final_time("f1", TODAY, NOW - 2 * HOUR)
    await kit.run_games()
    await kit.serve()

    await kit.serve(NOW + 5 * HOUR)

    assert kit.called("standings") == 1


@pytest.mark.anyio
async def test_the_cleanup_keeps_league(kit: StandingsKit, tmp_path: Path) -> None:
    publish_by_id(tmp_path, KIND, StandingsFeed, FEED_ID, built())
    kit.store.record_build(KIND, FEED_ID, NOW)

    kit.cache.cleanup()

    assert kit.store.feed_build_ids(KIND) == {FEED_ID}
    assert read_by_id(tmp_path, KIND, FEED_ID) is not None
