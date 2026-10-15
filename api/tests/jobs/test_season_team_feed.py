# api/tests/jobs/test_season_team_feed.py
#
# Tests for the team feed of a past season and its feed kind.
#
# Tested:
# - The builder sets that season's name and city, the record of that season's standing (a 7th division place, the play-in position null before 2021 and set from 2021), the leaders of that season, the roster (every status active, ages on February 1 of the end year) and the schedule with the regular season and the playoffs group
# - The builder sets the arena, coach, injuries, next game, Cup and titles to null, and the feed validates as a past team feed
# - The builder fails for a team with no standing
# - The kind: a missing and an inactive season team answer unknown after one read, and a second request answers unknown with no read
# - The kind: 1993-okc, the current season, a future season, abc-okc, 2004-OKC and an unknown team answer unknown with no source request, and an unknown current season is not ready
# - The kind: the season is sent to the season reads, the schedules are read by id first and the leaders have no fallback
# - The kind: the names are built first and the stored feed carries them; serving sets the latest stored names
# - The kind: the feed is never rebuilt, also after a simulated restart and years later
# - The kind: a failed build with nothing stored answers unavailable
#
# What is covered:
# - Pure conversions: happy path, edges and errors; the built feed validates
# - Feed kind: success publishes a valid feed, failure with nothing stored is unavailable, kept for good
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_team_feed.py
#
# SEE: api/app/jobs/season_team_feed.py

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from app.feeds.team import NameRun, PastTeamFeed, TeamNames
from app.jobs.on_demand import (
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.season_team_feed import (
    KIND,
    SeasonTeamFeeds,
    build_season_team_feed,
)
from app.jobs.stars import StarsJob
from app.jobs.team_feed import TeamBuildError
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources.division_standings import DivisionStandings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.season_team import SeasonTeam
from app.sources.team_info import TeamInfo
from app.sources.team_players import PlayerAverages, Roster, SeasonLeaders
from app.sources.team_schedule import SeasonSchedule
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.jobs.test_team_feed import (
    info,
    leaders,
    played,
    player,
    roster,
    season,
    standing,
    standings,
)

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
YEARS = dt.timedelta(days=365 * 5)
GAME_TIME = dt.datetime(2003, 11, 2, 3, 0, tzinfo=dt.UTC)
PLAYOFF_TIME = dt.datetime(2004, 4, 22, 1, 0, tzinfo=dt.UTC)


def season_team(active: bool = True) -> SeasonTeam:
    return SeasonTeam(
        team_id="25",
        abbreviation="SEA",
        display_name="Seattle Harbor Gulls",
        name="Harbor Gulls",
        location="Seattle",
        active=active,
    )


def past_roster() -> Roster:
    return roster(player("1", "2", birth_date=dt.date(1978, 2, 1)), player("2", "9"))


def averages() -> SeasonLeaders:
    return leaders(("1", 21.44, 5.0, 7.0), ("2", 9.0, 8.26, 1.0), season=2004)


def regular_schedule() -> SeasonSchedule:
    return season(played("g1", GAME_TIME))


def playoffs_schedule() -> SeasonSchedule:
    return season(played("g2", PLAYOFF_TIME, playoffs=True))


def build(
    *,
    code: str = "OKC",
    end_year: int = 2004,
    entry_changes: dict[str, Any] | None = None,
    names: list[NameRun] | None = None,
) -> PastTeamFeed:
    entry = standing(code, division_order=7, **(entry_changes or {}))
    return build_season_team_feed(
        code,
        end_year,
        season_team(),
        info(),
        standings(entry, season=end_year),
        past_roster(),
        averages(),
        regular_schedule(),
        playoffs_schedule(),
        names,
    )


def test_the_builder_sets_the_name_and_city_of_that_season_and_todays_colors() -> None:
    feed = build()

    assert (feed.city, feed.name) == ("Seattle", "Harbor Gulls")
    assert feed.code == "OKC"
    assert feed.season == "2003-04"
    assert (feed.colors.primary, feed.colors.secondary) == ("#007ac1", "#ef3b24")


def test_the_builder_sets_the_record_of_that_seasons_standing_with_a_7th_division_place() -> (
    None
):
    feed = build()

    assert feed.record.season == "2003-04"
    assert (feed.record.wins, feed.record.losses) == (30, 10)
    assert feed.record.division_rank == 7


@pytest.mark.parametrize(("end_year", "has_playoff"), [(2020, False), (2021, True)])
def test_the_play_in_position_is_null_before_2021_and_set_from_2021(
    end_year: int, has_playoff: bool
) -> None:
    feed = build(end_year=end_year)

    assert (feed.record.playoff is not None) is has_playoff
    assert feed.record.conference_rank == 1


def test_the_builder_sets_the_leaders_of_that_season_with_no_fallback_label() -> None:
    feed = build()

    assert feed.leaders.season == "2003-04"
    assert feed.leaders.points is not None
    assert (feed.leaders.points.player_id, feed.leaders.points.value) == ("1", 21.4)
    assert feed.leaders.rebounds is not None
    assert feed.leaders.rebounds.player_id == "2"


def test_the_roster_has_every_status_active_and_ages_on_february_1() -> None:
    feed = build()

    assert [p.status for p in feed.roster] == ["active", "active"]
    assert feed.roster[0].age == 26
    assert feed.roster[1].age == 5


def test_the_schedule_has_the_regular_season_and_the_playoffs_group() -> None:
    feed = build()

    assert feed.schedule is not None
    assert [group.key for group in feed.schedule.groups] == ["2003-11", "playoffs"]
    assert feed.schedule.default_group == "playoffs"
    assert all(
        not game.detail_available and not game.is_next
        for group in feed.schedule.groups
        for game in group.games
    )


def test_the_builder_sets_the_blocks_of_today_to_null_and_the_names_given() -> None:
    names = [
        NameRun.model_validate(
            {"from": 1994, "to": None, "name": "Harbor", "location": "S", "code": "SEA"}
        )
    ]

    feed = build(names=names)

    assert feed.arena is None and feed.coach is None and feed.injuries is None
    assert feed.next_game is None and feed.cup is None and feed.titles is None
    assert feed.names == names
    PastTeamFeed.model_validate_json(feed.model_dump_json())


def test_the_builder_fails_for_a_team_with_no_standing() -> None:
    with pytest.raises(TeamBuildError) as raised:
        build_season_team_feed(
            "SAS",
            2004,
            season_team(),
            info(),
            standings(season=2004),
            past_roster(),
            averages(),
            regular_schedule(),
            playoffs_schedule(),
        )

    assert raised.value.reason == "team SAS has no standing"


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027

    def current_season(self) -> int | None:
        return self.season


class SeasonTeamKit:
    """The names kind and the season team kind over one client and one clock,
    with fake adapters that count their calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.stars = FakeStars()
        self.calls: list[str] = []
        self.name_reads = 0
        self.missing = False
        self.inactive = False
        self.failing = False
        self.start()

    def start(self) -> None:
        """A new cache and kinds over the same data directory: a restart."""
        self.cache = FeedCache(self.path, self.store, clock=lambda: self.clock[0])
        self.names = TeamNamesFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_team=self.fetch_season_team,
        )
        self.teams = SeasonTeamFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            self.names,
            fetch_season_team=self.fetch_season_team,
            fetch_team_info=self.fetch_team_info,
            fetch_division_standings=self.fetch_division_standings,
            fetch_season_roster=self.fetch_season_roster,
            fetch_season_averages=self.fetch_season_averages,
            fetch_season_schedule=self.fetch_season_schedule,
        )

    async def fetch_season_team(
        self, client: SourceClient, code: str, end_year: int, settings: Settings
    ) -> SeasonTeam | None:
        self.calls.append(f"season-team/{code}/{end_year}")
        if end_year != 2004:
            self.name_reads += 1
        if self.missing:
            return None
        return season_team(active=not self.inactive)

    async def fetch_team_info(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamInfo:
        self.calls.append(f"info/{code}")
        if self.failing:
            raise SourceError("test", "team info is down")
        return info()

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings, *, season: int | None = None
    ) -> DivisionStandings:
        self.calls.append(f"standings/{season}")
        return standings(standing("OKC", division_order=7), season=season or 0)

    async def fetch_season_roster(
        self, client: SourceClient, code: str, end_year: int, settings: Settings
    ) -> Roster:
        self.calls.append(f"roster/{code}/{end_year}")
        return past_roster()

    async def fetch_season_averages(
        self, client: SourceClient, team_id: str, end_year: int, settings: Settings
    ) -> list[PlayerAverages]:
        self.calls.append(f"averages/{team_id}/{end_year}")
        return averages().players

    async def fetch_season_schedule(
        self,
        client: SourceClient,
        code: str,
        end_year: int,
        settings: Settings,
        *,
        playoffs: bool,
        by_id_first: bool = False,
    ) -> SeasonSchedule:
        self.calls.append(f"schedule/{code}/{end_year}/{playoffs}/{by_id_first}")
        return playoffs_schedule() if playoffs else regular_schedule()

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, feed_id: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, feed_id)
        await self.settle()
        return body

    def stored(self, feed_id: str) -> PastTeamFeed | None:
        body = read_by_id(self.path, KIND, feed_id)
        return None if body is None else PastTeamFeed.model_validate_json(body)


@pytest.fixture
def kit(tmp_path: Path) -> SeasonTeamKit:
    return SeasonTeamKit(tmp_path)


@pytest.mark.anyio
async def test_a_request_builds_a_valid_feed_with_the_season_reads_by_id_first(
    kit: SeasonTeamKit,
) -> None:
    feed = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert feed.season == "2003-04"
    assert (feed.city, feed.name) == ("Seattle", "Harbor Gulls")
    assert "standings/2004" in kit.calls
    assert "roster/OKC/2004" in kit.calls
    assert "averages/25/2004" in kit.calls
    assert "schedule/OKC/2004/False/True" in kit.calls
    assert "schedule/OKC/2004/True/True" in kit.calls


@pytest.mark.anyio
@pytest.mark.parametrize("missing", [True, False])
async def test_a_missing_or_inactive_season_team_answers_unknown_after_one_read_and_then_with_none(
    kit: SeasonTeamKit, missing: bool
) -> None:
    kit.missing = missing
    kit.inactive = not missing

    with pytest.raises(UnknownFeedError):
        await kit.serve("2004-okc")
    after_first = list(kit.calls)
    with pytest.raises(UnknownFeedError):
        await kit.serve("2004-okc")

    # One read of the season's team object by the kind, one by the names build.
    assert after_first.count("season-team/OKC/2004") == 2
    assert kit.calls == after_first
    assert kit.stored("2004-okc") is None
    assert kit.store.feed_build("season-teams", "2004-okc") is None
    assert not any(call.startswith("standings") for call in kit.calls)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "feed_id",
    ["1993-okc", "2027-okc", "2028-okc", "abc-okc", "2004-OKC", "2004-xyz", "2004", ""],
)
async def test_an_invalid_early_current_future_or_unknown_id_answers_unknown_with_no_source_request(
    kit: SeasonTeamKit, feed_id: str
) -> None:
    assert kit.teams.check(feed_id) is IdStatus.UNKNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, feed_id)

    assert kit.calls == []


@pytest.mark.anyio
async def test_an_unknown_current_season_is_not_ready(kit: SeasonTeamKit) -> None:
    kit.stars.season = None

    assert kit.teams.check("2004-okc") is IdStatus.NOT_READY
    assert kit.teams.check("1993-okc") is IdStatus.UNKNOWN
    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "2004-okc")

    assert kit.calls == []


@pytest.mark.anyio
async def test_the_names_are_built_first_and_the_stored_feed_carries_them(
    kit: SeasonTeamKit,
) -> None:
    body = await kit.serve("2004-okc")

    assert kit.name_reads == 2027 - 1994 + 1 - 1
    feed = PastTeamFeed.model_validate_json(body)
    assert [(r.from_, r.to, r.name) for r in feed.names] == [
        (1994, None, "Harbor Gulls")
    ]
    stored = kit.stored("2004-okc")
    assert stored is not None and stored.names == feed.names


@pytest.mark.anyio
async def test_serving_sets_the_latest_stored_names(kit: SeasonTeamKit) -> None:
    await kit.serve("2004-okc")
    newer = [
        NameRun.model_validate(
            {"from": 1994, "to": None, "name": "Storm", "location": "S", "code": "SEA"}
        )
    ]
    publish_by_id(kit.path, "team-names", TeamNames, "okc", TeamNames(runs=newer))

    served = PastTeamFeed.model_validate_json(await kit.serve("2004-okc"))

    assert [r.name for r in served.names] == ["Storm"]
    stored = kit.stored("2004-okc")
    assert stored is not None and [r.name for r in stored.names] == ["Harbor Gulls"]


@pytest.mark.anyio
async def test_the_feed_is_never_rebuilt_even_after_a_restart_or_years_later(
    kit: SeasonTeamKit,
) -> None:
    first = await kit.serve("2004-okc")
    calls = len(kit.calls)
    await kit.serve("2004-okc", NOW + YEARS)
    kit.start()
    await kit.serve("2004-okc", NOW + 2 * YEARS)

    assert len(kit.calls) == calls
    assert read_by_id(kit.path, KIND, "2004-okc") is not None
    assert first


@pytest.mark.anyio
async def test_a_failed_build_with_nothing_stored_answers_unavailable(
    kit: SeasonTeamKit,
) -> None:
    kit.failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve("2004-okc")

    assert kit.stored("2004-okc") is None


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: SeasonTeamKit) -> None:
    await kit.serve("2004-okc")

    kit.cache.cleanup()

    assert kit.stored("2004-okc") is not None
