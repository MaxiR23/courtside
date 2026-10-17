# api/tests/jobs/test_season_standings_feed.py
#
# Tests for the standings feed of a past season and its feed kind.
#
# Tested:
# - past_season_status: 1993, abc, 01999, 2027 with a trailing newline, a non-ASCII digit string, the current season and a future season are unknown; 1994 and the season before the current one are known; an unknown current season is not ready for a well-formed id
# - The kind: a past season builds a valid feed with the season parameter, the state final with fewer than 82 games and the clinchers of the source
# - The kind: the feed is stored and rebuilt only for another version: a second request, a request years later and a new cache over the same data directory (a restart) all serve with no source call
# - The kind: a failed build with nothing stored answers unavailable
# - The kind: an invalid id answers unknown and a not ready season answers unavailable, with no source request
# - The kind: the colors are today's and null when a team info read fails
# - The kind: each row is named by that season's team object with today's code
# - The kind: the built feed carries the current build version, a stored feed of an older or missing version is rebuilt on its next request, and one of the current version is served with no source request (ADR 0053)
# - The kind: the cleanup keeps it
#
# What is covered:
# - Pure status logic: happy path, edges and errors
# - Feed kind: success publishes a valid feed, failure with nothing stored is unavailable, kept for good
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_season_standings_feed.py
#
# SEE: api/app/jobs/season_standings_feed.py

import asyncio
import datetime as dt
from pathlib import Path
from typing import Any, cast

import pytest

from app.feeds.game_detail import Conference
from app.feeds.standings import Clinch, StandingsFeed, StandingsState
from app.jobs.on_demand import (
    SEASON_BUILD_VERSION,
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.season_standings_feed import (
    KIND,
    SeasonStandingsFeeds,
    past_season_status,
)
from app.jobs.stars import StarsJob
from app.jobs.team_names import TeamNamesFeeds
from app.settings import Settings
from app.sources.division_standings import DivisionEntry, DivisionStandings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.season_team import SeasonTeam
from app.sources.team_info import TeamInfo
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
YEARS = dt.timedelta(days=365 * 5)


@pytest.mark.parametrize(
    "text", ["1993", "abc", "01999", "2027\n", "", "١٩٩٩", "2027", "2028", "19999"]
)
def test_an_ill_formed_early_current_or_future_season_is_unknown(text: str) -> None:
    assert past_season_status(text, 2027) is IdStatus.UNKNOWN


def test_the_first_and_the_season_before_the_current_one_are_known() -> None:
    assert past_season_status("1994", 2027) is IdStatus.KNOWN
    assert past_season_status("2026", 2027) is IdStatus.KNOWN


def test_an_unknown_current_season_is_not_ready_for_a_well_formed_id() -> None:
    assert past_season_status("2000", None) is IdStatus.NOT_READY
    assert past_season_status("1993", None) is IdStatus.UNKNOWN
    assert past_season_status("abc", None) is IdStatus.UNKNOWN


def entry(
    code: str, conference: Conference, order: int, **changes: Any
) -> DivisionEntry:
    values: dict[str, Any] = {
        "code": code,
        "location": code.title(),
        "name": "Team",
        "display_name": f"{code.title()} Team",
        "conference": conference,
        "division": "Atlantic" if conference is Conference.EAST else "Pacific",
        "division_order": order,
        "conference_order": order,
        "provider_order": order + (0 if conference is Conference.EAST else 10),
        "wins": 40,
        "losses": 20,
        "playoff_seed": order,
        "streak": "W3",
        "games_behind": "-",
        "home": "22-8",
        "road": "18-12",
        "last_ten": "7-3",
        "avg_points_for": 98.04,
        "avg_points_against": 97.92,
        "points_for": 6082,
        "points_against": 5975,
        "differential": 0.1,
        "point_differential": 7,
        "vs_division": "10-2",
        "vs_conference": "25-9",
        "clinch": None,
    }
    return DivisionEntry.model_validate(values | changes)


def past_standings(season: int = 1996) -> DivisionStandings:
    entries = [
        entry("AAA", Conference.EAST, 1, clinch=Clinch.DIVISION),
        entry("BBB", Conference.EAST, 2, clinch=Clinch.PLAYOFFS, wins=30, losses=30),
        entry("CCC", Conference.WEST, 1, clinch=Clinch.ELIMINATED),
    ]
    return DivisionStandings(
        season=season, fallback=False, teams={e.code: e for e in entries}
    )


def info() -> TeamInfo:
    return TeamInfo(
        location="Place",
        name="Team",
        color="007ac1",
        alternate_color="ef3b24",
        venue_name="Arena",
    )


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = 2027

    def current_season(self) -> int | None:
        return self.season


class StandingsKit:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.stars = FakeStars()
        self.seasons: list[int | None] = []
        self.calls: list[str] = []
        self.info_codes: list[str] = []
        self.failing = False
        self.failing_info: set[str] = set()
        # The (name, city) of the season team object by code; the default is the
        # name and city of the standings rows.
        self.season_names: dict[str, tuple[str, str]] = {}
        # The current season's team object by code, when it differs.
        self.current_names: dict[str, tuple[str, str]] = {}
        self.start()

    def start(self) -> None:
        """A new cache and kind over the same data directory: a restart."""
        self.cache = FeedCache(self.path, self.store, clock=lambda: self.clock[0])
        self.names = TeamNamesFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_team=self.fetch_season_team,
        )
        self.kind = SeasonStandingsFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            self.names,
            fetch_division_standings=self.fetch_division_standings,
            fetch_team_info=self.fetch_team_info,
        )

    async def fetch_season_team(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        self.calls.append(f"season-team/{code}/{season}")
        names = self.current_names if season == 2027 else self.season_names
        name, city = names.get(code, ("Team", code.title()))
        return SeasonTeam(
            team_id="1",
            abbreviation="OLD",
            display_name=f"{city} {name}",
            name=name,
            location=city,
        )

    async def fetch_division_standings(
        self, client: SourceClient, settings: Settings, *, season: int | None = None
    ) -> DivisionStandings:
        self.seasons.append(season)
        self.calls.append(f"standings/{season}")
        if self.failing:
            raise SourceError("test", "standings are down")
        return past_standings(season or 0)

    async def fetch_team_info(
        self, client: SourceClient, code: str, settings: Settings
    ) -> TeamInfo:
        self.info_codes.append(code)
        self.calls.append(f"info/{code}")
        if code in self.failing_info:
            raise SourceError("test", "team info is down")
        return info()

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, season: str, at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, season)
        await self.settle()
        return body


@pytest.fixture
def kit(tmp_path: Path) -> StandingsKit:
    return StandingsKit(tmp_path)


@pytest.mark.anyio
async def test_a_past_season_builds_a_valid_final_feed_with_the_season_and_the_clinchers(
    kit: StandingsKit,
) -> None:
    body = await kit.serve("1996")

    feed = StandingsFeed.model_validate_json(body)
    assert kit.seasons == [1996]
    assert feed.season == "1995-96"
    assert feed.state is StandingsState.FINAL
    east = {row.code: row for row in feed.conferences[0].teams}
    assert east["AAA"].clinch is Clinch.DIVISION
    assert east["BBB"].clinch is Clinch.PLAYOFFS
    assert feed.conferences[1].teams[0].clinch is Clinch.ELIMINATED
    assert east["AAA"].colors.primary == "#007ac1"
    assert feed.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_each_row_is_named_by_that_seasons_team_object_with_todays_code(
    kit: StandingsKit,
) -> None:
    kit.season_names = {"AAA": ("Harbor Gulls", "Seattle")}

    feed = StandingsFeed.model_validate_json(await kit.serve("1996"))

    east = {row.code: row for row in feed.conferences[0].teams}
    assert (east["AAA"].code, east["AAA"].name, east["AAA"].city) == (
        "AAA",
        "Harbor Gulls",
        "Seattle",
    )
    assert (east["BBB"].name, east["BBB"].city) == ("Team", "Bbb")
    assert (east["AAA"].season_code, east["AAA"].historical) == ("OLD", True)
    assert (east["BBB"].season_code, east["BBB"].historical) == ("OLD", False)
    divisional = {row.code: row for row in feed.divisions[0].teams}
    assert divisional["AAA"].historical is True
    assert "season-team/AAA/1996" in kit.calls


@pytest.mark.anyio
async def test_the_colors_are_null_when_a_team_info_read_fails(
    kit: StandingsKit,
) -> None:
    kit.failing_info = {"BBB"}

    feed = StandingsFeed.model_validate_json(await kit.serve("1996"))

    east = {row.code: row for row in feed.conferences[0].teams}
    assert east["BBB"].colors.primary is None
    assert east["AAA"].colors.primary == "#007ac1"


@pytest.mark.anyio
async def test_a_stored_feed_is_never_rebuilt_even_years_later_or_after_a_restart(
    kit: StandingsKit,
) -> None:
    first = await kit.serve("1996")
    second = await kit.serve("1996")
    later = await kit.serve("1996", NOW + YEARS)
    kit.start()
    restarted = await kit.serve("1996", NOW + 2 * YEARS)

    assert first == second == later == restarted
    assert kit.seasons == [1996]
    assert read_by_id(kit.path, KIND, "1996") == first


@pytest.mark.anyio
async def test_a_failed_build_with_nothing_stored_answers_unavailable(
    kit: StandingsKit,
) -> None:
    kit.failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve("1996")

    assert read_by_id(kit.path, KIND, "1996") is None


@pytest.mark.anyio
@pytest.mark.parametrize("season", ["1993", "2027", "2028", "abc", "2027\n"])
async def test_an_invalid_id_answers_unknown_with_no_source_request(
    kit: StandingsKit, season: str
) -> None:
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, season)

    assert kit.seasons == [] and kit.info_codes == []


@pytest.mark.anyio
async def test_an_unknown_current_season_answers_unavailable_with_no_source_request(
    kit: StandingsKit,
) -> None:
    kit.stars.season = None

    with pytest.raises(FeedUnavailableError):
        await kit.cache.serve(KIND, "1996")

    assert kit.seasons == []


@pytest.mark.anyio
async def test_the_cleanup_keeps_the_feed(kit: StandingsKit) -> None:
    body = await kit.serve("1996")

    kit.cache.cleanup()

    assert read_by_id(kit.path, KIND, "1996") == body


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_feed_with_an_older_or_missing_version_is_rebuilt_on_its_next_request(
    kit: StandingsKit, version: int | None
) -> None:
    await kit.serve("1996")
    stored = StandingsFeed.model_validate_json(
        read_by_id(kit.path, KIND, "1996") or b""
    )
    old = stored.model_copy(update={"build_version": version})
    publish_by_id(kit.path, KIND, StandingsFeed, "1996", old)
    kit.seasons.clear()

    served = StandingsFeed.model_validate_json(await kit.serve("1996", NOW + YEARS))

    assert served.build_version == version
    assert kit.seasons == [1996]
    rebuilt = StandingsFeed.model_validate_json(
        read_by_id(kit.path, KIND, "1996") or b""
    )
    assert rebuilt.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_a_stored_feed_with_the_current_version_is_served_with_no_source_request(
    kit: StandingsKit,
) -> None:
    await kit.serve("1996")
    kit.calls.clear()

    await kit.serve("1996", NOW + YEARS)

    assert kit.calls == []
