# api/tests/jobs/test_search_feed.py
#
# Tests for the search feed builder and its feed kind.
#
# Tested:
# - Maps a team with every field: code, city, name, colors, record, division and division rank
# - Lists the 30 teams in standard code order
# - Gives null colors to a team whose team info is missing
# - Gives a 0-0 team the record 0-0
# - Fails with a build error when a code is missing from the standings
# - Maps a player with every field, the short name and the team code and primary
# - A player with no jersey, position, display name or headshot has null fields and the first plus last name
# - An injured player gets the status and a player with no report gets null
# - The team primary of a player is null when that team's info is missing
# - Lists players in team code order, then roster order
# - A player listed by two rosters appears once, under the team whose newer roster lists him
# - Wraps an invalid feed in a build error
# - The kind: an id other than league answers unknown with no build
# - The kind: it answers not ready before every roster is fetched and known after
# - The kind: no feed is built, stored or fetched without a request
# - The kind: a request builds and stores the feed and a second request reads storage
# - The kind: the build makes no roster request
# - The kind: a failed team info read leaves null colors and the build succeeds
# - The kind: a failed standings or injuries read answers unavailable and is not retried for 10 minutes
# - The kind: a failed rebuild of a stale feed keeps and serves the stored feed
# - The kind: fresh before a final game of the league plus 1 hour and stale at it
# - The kind: fresh before 7 days and stale at 7 days
# - The kind: a roster fetch after the build makes the next request rebuild, one before does not
# - The kind: the cleanup keeps league
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure keeps the last valid feed, expiry edges
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_search_feed.py
#
# SEE: api/app/jobs/search_feed.py

import asyncio
import datetime as dt
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.game_detail import Conference, Injury, InjuryStatus
from app.feeds.games import GameStatus, Star
from app.feeds.search import SearchFeed
from app.jobs.games import GamesJob
from app.jobs.on_demand import (
    RETRY_AFTER,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.search_feed import (
    CODES,
    FEED_ID,
    KIND,
    SearchBuildError,
    SearchFeeds,
    build_search_feed,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import FEED_LIFETIME
from app.settings import Settings
from app.sources.division_standings import DivisionStandings
from app.sources.game_detail import GameDetail
from app.sources.http import (
    Freshness,
    SourceClient,
    SourceError,
    create_client,
    get_json,
)
from app.sources.league_injuries import InjuryReport, LeagueInjuries
from app.sources.scoreboard import ScoreboardGame
from app.sources.team_info import TeamInfo
from app.sources.team_players import PlayerAverages, Roster, RosterEntry
from app.sources.teams import TEAM_CODES
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_game_detail_feed import games_detail
from tests.jobs.test_standings_feed import league, team
from tests.jobs.test_team_feed import HOUR, NOW, SECOND, TODAY, info, scoreboard

SOURCE = "https://example.com/source/"
DAY = dt.timedelta(days=1)


DIVISIONS = ["Atlantic", "Central", "Southeast", "Northwest", "Pacific", "Southwest"]


def full_league() -> DivisionStandings:
    """The 30 teams in 6 divisions of 5, each with a division position of 1 to 5."""
    return league(
        *(
            team(
                code,
                division=DIVISIONS[index // 5],
                division_order=index % 5 + 1,
                conference=Conference.EAST if index < 15 else Conference.WEST,
            )
            for index, code in enumerate(sorted(set(TEAM_CODES.values())))
        )
    )


def entry(player_id: str, **changes: Any) -> RosterEntry:
    values: dict[str, Any] = {
        "player_id": player_id,
        "first_name": "Shai",
        "last_name": "Gilgeous-Alexander",
        "display_name": "Shai G-A",
        "jersey": "2",
        "position_name": "Point Guard",
        "position_abbreviation": "PG",
        "headshot_url": "https://example.com/p.png",
    }
    return RosterEntry.model_validate(values | changes)


def no_injuries() -> LeagueInjuries:
    return LeagueInjuries(teams={})


def injured(player_id: str, status: InjuryStatus) -> LeagueInjuries:
    return LeagueInjuries(
        teams={
            "OKC": [
                InjuryReport(
                    injury=Injury(display_name="Shai", status=status),
                    player_id=player_id,
                    updated_at=NOW,
                )
            ]
        }
    )


def everyone_on_their_roster(player_id: str) -> str | None:
    return player_id.split("-")[0]


def built(
    rosters: dict[str, list[RosterEntry]] | None = None,
    colors: dict[str, TeamInfo | None] | None = None,
    injuries: LeagueInjuries | None = None,
    standings: DivisionStandings | None = None,
) -> SearchFeed:
    return build_search_feed(
        standings or full_league(),
        colors if colors is not None else dict.fromkeys(CODES, info()),
        rosters or {},
        everyone_on_their_roster,
        injuries or no_injuries(),
    )


def test_maps_a_team_with_every_field() -> None:
    standings = full_league()
    standings.teams["OKC"] = team(
        "OKC", division="Northwest", division_order=3, wins=64, losses=18
    )

    feed = built(standings=standings)

    okc = next(t for t in feed.teams if t.code == "OKC")
    assert okc.city == "Okc"
    assert okc.name == "Team"
    assert (okc.colors.primary, okc.colors.secondary) == ("#007ac1", "#ef3b24")
    assert okc.record == "64-18"
    assert okc.division == "Northwest"
    assert okc.division_rank == 3


def test_lists_the_30_teams_in_standard_code_order() -> None:
    codes = [t.code for t in built().teams]

    assert codes == sorted(codes)
    assert len(codes) == 30
    assert codes.index("BKN") < codes.index("BOS")


def test_gives_null_colors_to_a_team_whose_info_is_missing() -> None:
    feed = built(colors={"OKC": None})

    okc = next(t for t in feed.teams if t.code == "OKC")
    assert (okc.colors.primary, okc.colors.secondary) == (None, None)
    assert feed.teams[0].colors.primary is None


def test_gives_a_0_0_team_the_record_0_0() -> None:
    standings = full_league()
    standings.teams["OKC"] = team("OKC", wins=0, losses=0)

    feed = built(standings=standings)

    assert next(t for t in feed.teams if t.code == "OKC").record == "0-0"


def test_fails_when_a_code_is_missing_from_the_standings() -> None:
    standings = full_league()
    del standings.teams["OKC"]

    with pytest.raises(SearchBuildError, match="team OKC has no standing"):
        built(standings=standings)


def test_maps_a_player_with_every_field() -> None:
    feed = built({"OKC": [entry("OKC-1")]})

    (player,) = feed.players
    assert player.id == "OKC-1"
    assert player.name == "Shai G-A"
    assert player.short_name == "S. Gilgeous-Alexander"
    assert player.number == "2"
    assert player.position == "Point Guard"
    assert player.position_abbr == "PG"
    assert str(player.photo_url) == "https://example.com/p.png"
    assert player.injury is None
    assert (player.team.code, player.team.primary) == ("OKC", "#007ac1")


def test_a_player_with_no_jersey_position_display_name_or_headshot_has_null_fields() -> (
    None
):
    bare = entry(
        "OKC-1",
        display_name=None,
        jersey=None,
        position_name=None,
        position_abbreviation=None,
        headshot_url=None,
    )

    (player,) = built({"OKC": [bare]}).players

    assert player.name == "Shai Gilgeous-Alexander"
    assert player.number is None
    assert player.position is None
    assert player.position_abbr is None
    assert player.photo_url is None


def test_an_injured_player_gets_the_status_and_one_with_no_report_gets_null() -> None:
    feed = built(
        {"OKC": [entry("OKC-1"), entry("OKC-2")]},
        injuries=injured("OKC-1", InjuryStatus.OUT),
    )

    first, second = feed.players
    assert first.injury is not None and first.injury.status is InjuryStatus.OUT
    assert second.injury is None


def test_the_team_primary_of_a_player_is_null_when_the_teams_info_is_missing() -> None:
    feed = built({"OKC": [entry("OKC-1")]}, colors={"OKC": None})

    assert feed.players[0].team.primary is None


def test_lists_players_in_team_code_order_then_roster_order() -> None:
    feed = built(
        {
            "OKC": [entry("OKC-2"), entry("OKC-1")],
            "BOS": [entry("BOS-1")],
            "BKN": [entry("BKN-1")],
        }
    )

    assert [p.id for p in feed.players] == ["BKN-1", "BOS-1", "OKC-2", "OKC-1"]


def test_a_player_listed_by_two_rosters_appears_once_under_the_newer_roster() -> None:
    feed = build_search_feed(
        full_league(),
        dict.fromkeys(CODES, info()),
        {"BOS": [entry("p")], "OKC": [entry("p")]},
        lambda player_id: "OKC",
        no_injuries(),
    )

    assert [(p.id, p.team.code) for p in feed.players] == [("p", "OKC")]


def test_wraps_an_invalid_feed_in_a_build_error() -> None:
    with pytest.raises(SearchBuildError, match="invalid feed"):
        built({"OKC": [entry("OKC-1", jersey="A1")]})


class SearchKit:
    """A games job, a stars job, a feed cache and the search kind over one client and one clock.

    Every fake adapter reads one URL through the source cache from a counted
    respx route, so route calls are real source requests. The stars job gets a
    counted fake roster fetcher.
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
        self.roster_calls: list[str] = []
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
        self.stars = StarsJob(
            self.settings,
            self.store,
            self.client,
            fetch_roster=self.fetch_roster,
            fetch_season_averages=self.fetch_season_averages,
            final_games=lambda: self.games.final_games(),
            clock=lambda: self.clock[0],
        )
        self.search = SearchFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            self.games,
            self.stars,
            fetch_division_standings=self.fetch_division_standings,
            fetch_league_injuries=self.fetch_league_injuries,
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

    async def fetch_league_injuries(
        self, client: SourceClient, settings: Settings
    ) -> LeagueInjuries:
        await self.read("injuries", HOUR)
        return injured("OKC-1", InjuryStatus.OUT)

    async def fetch_team_info(
        self, client: SourceClient, team: str, settings: Settings
    ) -> TeamInfo:
        await self.read(f"info/{team}", HOUR)
        return info()

    async def fetch_roster(
        self, client: SourceClient, code: str, settings: Settings
    ) -> Roster:
        self.roster_calls.append(code)
        return Roster(
            season=2027,
            team_id=f"id-{code}",
            players=[
                Star.model_validate(
                    {
                        "player_id": f"{code}-{n}",
                        "first_name": "A",
                        "last_name": "B",
                        "short_name": "A. B",
                        "team_code": code,
                        "photo_url": "https://example.com/p.png",
                    }
                )
                for n in (1, 2)
            ],
            entries=[entry(f"{code}-1"), entry(f"{code}-2")],
        )

    async def fetch_season_averages(
        self, client: SourceClient, team_id: str, season: int, settings: Settings
    ) -> list[PlayerAverages]:
        code = team_id.removeprefix("id-")
        return [
            PlayerAverages(player_id=f"{code}-{n}", points=10, rebounds=1, assists=1)
            for n in (1, 2)
        ]

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

    async def run_stars(self, at: dt.datetime | None = None) -> None:
        if at is not None:
            self.clock[0] = at
        await self.stars.run(self.clock[0])

    async def serve(self, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, FEED_ID)
        await self.settle()
        return body

    def stored(self) -> SearchFeed | None:
        body = read_by_id(self.path, KIND, FEED_ID)
        return None if body is None else SearchFeed.model_validate_json(body)

    def last_build(self) -> dt.datetime | None:
        state = self.store.feed_build(KIND, FEED_ID)
        return None if state is None else state.last_build


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> SearchKit:
    return SearchKit(tmp_path)


@pytest.fixture
async def ready(kit: SearchKit) -> SearchKit:
    """The kit once the stars job has fetched every roster, an hour before NOW."""
    await kit.run_stars(NOW - HOUR)
    kit.clock[0] = NOW
    return kit


@pytest.mark.anyio
async def test_an_id_other_than_league_answers_unknown_with_no_build(
    ready: SearchKit, tmp_path: Path
) -> None:
    for feed_id in ("LEAGUE", "okc", ""):
        assert ready.search.check(feed_id) is IdStatus.UNKNOWN
        with pytest.raises(UnknownFeedError):
            await ready.cache.serve(KIND, feed_id)

    assert ready.search.check("league") is IdStatus.KNOWN
    assert ready.calls == [] and ready.requests == []
    assert not (tmp_path / "feeds" / KIND).exists()


@pytest.mark.anyio
async def test_answers_not_ready_before_every_roster_is_fetched_and_known_after(
    kit: SearchKit, tmp_path: Path
) -> None:
    assert kit.search.check("league") is IdStatus.NOT_READY
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, FEED_ID)
    assert kit.calls == [] and kit.requests == []
    assert not (tmp_path / "feeds" / KIND).exists()

    await kit.run_stars(NOW - HOUR)

    assert kit.search.check("league") is IdStatus.KNOWN


@pytest.mark.anyio
async def test_no_search_feed_is_built_stored_or_fetched_without_a_request(
    ready: SearchKit, tmp_path: Path
) -> None:
    ready.scoreboard[TODAY] = [scoreboard("g1", GameStatus.SCHEDULED, NOW + HOUR)]

    await ready.run_games()
    await ready.run_games(NOW + 30 * SECOND)
    ready.cache.cleanup()
    await ready.settle()

    assert ready.requests == [] and ready.calls == []
    assert not (tmp_path / "feeds" / KIND).exists()
    assert ready.store.feed_build_ids(KIND) == set()


@pytest.mark.anyio
async def test_a_request_builds_and_stores_the_feed_and_a_second_request_reads_storage(
    ready: SearchKit,
) -> None:
    first = await ready.serve()
    requests = list(ready.requests)
    second = await ready.serve(NOW + 30 * SECOND)

    feed = SearchFeed.model_validate_json(first)
    assert len(feed.teams) == 30 and len(feed.players) == 60
    assert second == first
    assert ready.requests == requests and requests != []
    assert ready.called("standings") == 1 and ready.called("injuries") == 1
    assert ready.last_build() == NOW
    assert ready.stored() is not None
    okc = [p for p in feed.players if p.team.code == "OKC"]
    assert okc[0].injury is not None and okc[1].injury is None


@pytest.mark.anyio
async def test_the_build_makes_no_roster_request(ready: SearchKit) -> None:
    roster_calls = list(ready.roster_calls)

    await ready.serve()

    assert ready.roster_calls == roster_calls
    assert {name.split("/")[0] for name in ready.requests} == {
        "standings",
        "injuries",
        "info",
    }
    assert ready.requested("info/") == 30


@pytest.mark.anyio
async def test_a_failed_team_info_read_leaves_null_colors_and_the_build_succeeds(
    ready: SearchKit,
) -> None:
    ready.failing.add("info/OKC")

    feed = SearchFeed.model_validate_json(await ready.serve())

    teams = {t.code: t for t in feed.teams}
    assert teams["OKC"].colors.primary is None
    assert teams["BOS"].colors.primary == "#007ac1"
    assert {p.team.primary for p in feed.players if p.team.code == "OKC"} == {None}
    assert ready.store.failed_feed_builds() == []


@pytest.mark.anyio
@pytest.mark.parametrize("source", ["standings", "injuries"])
async def test_a_failed_standings_or_injuries_read_answers_unavailable_and_is_not_retried_for_10_minutes(
    ready: SearchKit, source: str
) -> None:
    ready.failing.add(source)

    with pytest.raises(FeedUnavailableError):
        await ready.serve()
    await ready.settle()
    ready.clock[0] = NOW + RETRY_AFTER - SECOND
    with pytest.raises(FeedUnavailableError):
        await ready.serve()

    assert ready.called(source) == 1
    assert [f.feed_id for f in ready.store.failed_feed_builds()] == [FEED_ID]
    ready.failing.clear()
    body = await ready.serve(NOW + RETRY_AFTER)
    assert len(SearchFeed.model_validate_json(body).teams) == 30
    assert ready.called(source) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("source", ["standings", "injuries"])
async def test_a_failed_rebuild_of_a_stale_feed_keeps_and_serves_the_stored_feed(
    ready: SearchKit, source: str
) -> None:
    first = await ready.serve()
    stored = read_by_id(ready.path, KIND, FEED_ID)
    ready.failing.add(source)

    body = await ready.serve(NOW + FEED_LIFETIME)

    assert body == first
    assert ready.called(source) == 2
    assert read_by_id(ready.path, KIND, FEED_ID) == stored
    assert ready.last_build() == NOW
    assert [f.feed_id for f in ready.store.failed_feed_builds()] == [FEED_ID]


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_a_final_game_plus_1_hour_and_stale_at_it(
    ready: SearchKit,
) -> None:
    final = NOW + 2 * HOUR
    ready.scoreboard[TODAY] = [
        scoreboard("f1", GameStatus.FINAL, NOW - HOUR, away="BOS", home="NYK")
    ]
    ready.store.set_final_time("f1", TODAY, final)
    await ready.run_games()
    await ready.serve()

    await ready.serve(final + HOUR - SECOND)
    assert ready.called("standings") == 1
    await ready.serve(final + HOUR)

    assert ready.called("standings") == 2
    assert ready.last_build() == final + HOUR


@pytest.mark.anyio
async def test_a_feed_is_fresh_before_7_days_and_stale_at_7_days(
    ready: SearchKit,
) -> None:
    await ready.serve()

    await ready.serve(NOW + FEED_LIFETIME - SECOND)
    assert ready.called("standings") == 1
    await ready.serve(NOW + FEED_LIFETIME)

    assert ready.called("standings") == 2


@pytest.mark.anyio
async def test_a_roster_fetch_after_the_build_makes_the_next_request_rebuild(
    ready: SearchKit,
) -> None:
    await ready.serve()
    await ready.serve(NOW + 30 * SECOND)
    assert ready.called("standings") == 1

    await ready.run_stars(NOW + DAY)
    assert ready.stars.latest_roster_fetch() == NOW + DAY
    await ready.serve(NOW + DAY)

    assert ready.called("standings") == 2
    assert ready.last_build() == NOW + DAY


@pytest.mark.anyio
async def test_the_cleanup_keeps_league(ready: SearchKit, tmp_path: Path) -> None:
    publish_by_id(tmp_path, KIND, SearchFeed, FEED_ID, built())
    ready.store.record_build(KIND, FEED_ID, NOW)

    ready.cache.cleanup()

    assert ready.store.feed_build_ids(KIND) == {FEED_ID}
    assert read_by_id(tmp_path, KIND, FEED_ID) is not None
