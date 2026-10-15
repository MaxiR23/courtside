# api/tests/jobs/test_team_names.py
#
# Tests for the franchise names builder and its feed kind.
#
# Tested:
# - One run for a franchise whose every season is equal, open at the current season
# - Four runs for four identities, oldest first, past runs closed and the last open
# - A skipped season does not split a run, and a run that does not hold the current season stays closed
# - A provider code becomes its standard code and a historical code stays as sent
# - The kind: every season from 1994 to the current one is read once; a season whose read fails is skipped with a log line that carries the code and season and no URL; a no-team and an inactive season are skipped
# - The kind: a second request within 7 days makes no read and one at 7 days reads again
# - The kind: a build with no readable season keeps the stored list
# - The kind: a failed, missing or inactive current season fails the build and keeps the stored list
# - The kind: a code outside the 30 is unknown and an unknown current season is not ready
# - The kind: the cleanup keeps the 30 codes
#
# What is covered:
# - Pure conversions: happy path, edges and errors
# - Feed kind: success publishes a valid list, failure keeps the last valid list, expiry edges
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_team_names.py
#
# SEE: api/app/jobs/team_names.py

import asyncio
import datetime as dt
import logging
from pathlib import Path
from typing import cast

import pytest

from app.jobs.on_demand import (
    FeedCache,
    FeedUnavailableError,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.jobs.team_names import (
    KIND,
    NAMES_LIFETIME,
    TeamNamesFeeds,
    build_name_runs,
)
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client
from app.sources.season_team import SeasonTeam
from app.storage.state import StateStore

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
CURRENT = 2027


def team(
    name: str = "Thunder",
    location: str = "Oklahoma City",
    abbreviation: str = "OKC",
    active: bool = True,
) -> SeasonTeam:
    return SeasonTeam(
        team_id="25",
        abbreviation=abbreviation,
        display_name=f"{location} {name}",
        name=name,
        location=location,
        active=active,
    )


def identities(runs: list) -> list[tuple[int, int | None, str, str, str]]:  # type: ignore[type-arg]
    return [(r.from_, r.to, r.name, r.location, r.code) for r in runs]


def test_one_run_for_a_franchise_whose_every_season_is_equal_is_open() -> None:
    seasons = [(season, team()) for season in range(1994, CURRENT + 1)]

    runs = build_name_runs(seasons, CURRENT)

    assert identities(runs) == [(1994, None, "Thunder", "Oklahoma City", "OKC")]


def test_four_identities_make_four_runs_oldest_first_with_the_last_open() -> None:
    seasons = (
        [(s, team("Harbor Gulls", "Seattle", "SEA")) for s in range(1994, 2008)]
        + [(s, team("Thunder", "Oklahoma City", "OKC")) for s in range(2008, 2012)]
        + [(s, team("Thunder", "OKC Metro", "OKC")) for s in range(2012, 2020)]
        + [(s, team("Storm", "Oklahoma City", "OKC")) for s in range(2020, CURRENT + 1)]
    )

    runs = build_name_runs(list(reversed(seasons)), CURRENT)

    assert identities(runs) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (2008, 2011, "Thunder", "Oklahoma City", "OKC"),
        (2012, 2019, "Thunder", "OKC Metro", "OKC"),
        (2020, None, "Storm", "Oklahoma City", "OKC"),
    ]


def test_a_skipped_season_does_not_split_a_run() -> None:
    seasons = [(s, team()) for s in (1994, 1995, 1997, 1998)]

    runs = build_name_runs(seasons, CURRENT)

    assert identities(runs) == [(1994, 1998, "Thunder", "Oklahoma City", "OKC")]


def test_a_provider_code_becomes_its_standard_code_and_a_historical_one_stays() -> None:
    seasons = [
        (1994, team("Warriors", "Golden State", "GS")),
        (1995, team(abbreviation="VAN")),
    ]

    runs = build_name_runs(seasons, CURRENT)

    assert [run.code for run in runs] == ["GSW", "VAN"]


class FakeStars:
    def __init__(self) -> None:
        self.season: int | None = CURRENT

    def current_season(self) -> int | None:
        return self.season


class NamesKit:
    """A feed cache and the names kind over one client and one clock, with a fake
    season team adapter that counts its calls."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [NOW]
        self.store = StateStore(path)
        self.store.migrate()
        self.settings = Settings(_env_file=None, data_dir=path)  # type: ignore[call-arg]
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.calls: list[tuple[str, int]] = []
        self.failing: set[int] = set()
        self.missing: set[int] = set()
        self.inactive: set[int] = set()
        self.all_failing = False
        self.stars = FakeStars()
        self.cache = FeedCache(path, self.store, clock=lambda: self.clock[0])
        self.names = TeamNamesFeeds(
            self.settings,
            self.store,
            self.client,
            self.cache,
            cast(StarsJob, self.stars),
            fetch_season_team=self.fetch_season_team,
        )

    async def fetch_season_team(
        self, client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        self.calls.append((code, season))
        if self.all_failing or season in self.failing:
            raise SourceError("test", "season team is down")
        if season in self.missing:
            return None
        if season in self.inactive:
            return team(active=False)
        return team("Harbor Gulls", "Seattle", "SEA") if season < 2008 else team()

    async def settle(self) -> None:
        while self.cache.in_flight:
            await next(iter(self.cache.in_flight.values()))
            await asyncio.sleep(0)
        await asyncio.sleep(0)

    async def serve(self, code: str = "okc", at: dt.datetime | None = None) -> bytes:
        if at is not None:
            self.clock[0] = at
        body = await self.cache.serve(KIND, code)
        await self.settle()
        return body


@pytest.fixture
def kit(tmp_path: Path) -> NamesKit:
    return NamesKit(tmp_path)


@pytest.mark.anyio
async def test_every_season_from_1994_to_the_current_one_is_read_once(
    kit: NamesKit,
) -> None:
    await kit.serve()

    assert sorted(kit.calls) == [("OKC", s) for s in range(1994, CURRENT + 1)]
    runs = kit.names.stored("okc")
    assert runs is not None
    assert identities(runs) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (2008, None, "Thunder", "Oklahoma City", "OKC"),
    ]


@pytest.mark.anyio
async def test_a_failed_a_missing_and_an_inactive_season_are_skipped_and_the_runs_merge(
    kit: NamesKit, caplog: pytest.LogCaptureFixture
) -> None:
    kit.failing = {2000}
    kit.missing = {2001}
    kit.inactive = {2002}

    with caplog.at_level(logging.WARNING):
        await kit.serve()

    runs = kit.names.stored("okc")
    assert runs is not None
    assert [(r.from_, r.to) for r in runs] == [(1994, 2007), (2008, None)]
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 3
    assert any("okc season 2000 skipped" in m for m in messages)
    assert any("okc season 2001 skipped: no team" in m for m in messages)
    assert any("okc season 2002 skipped: no team" in m for m in messages)
    assert not any("http" in m for m in messages)


@pytest.mark.anyio
async def test_a_second_request_within_7_days_makes_no_read_and_one_at_7_days_reads_again(
    kit: NamesKit,
) -> None:
    await kit.serve()
    first = len(kit.calls)

    await kit.serve(at=NOW + NAMES_LIFETIME - dt.timedelta(seconds=1))
    assert len(kit.calls) == first

    await kit.serve(at=NOW + NAMES_LIFETIME)
    assert len(kit.calls) == 2 * first


@pytest.mark.anyio
async def test_a_build_with_no_readable_season_keeps_the_stored_list(
    kit: NamesKit,
) -> None:
    await kit.serve()
    before = kit.names.stored("okc")
    kit.all_failing = True

    await kit.serve(at=NOW + NAMES_LIFETIME)

    assert kit.names.stored("okc") == before
    state = kit.store.feed_build(KIND, "okc")
    assert state is not None
    assert state.last_failure is not None


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["failing", "missing", "inactive"])
async def test_a_current_season_that_cannot_be_read_keeps_the_stored_list(
    kit: NamesKit, mode: str
) -> None:
    await kit.serve()
    before = kit.names.stored("okc")
    getattr(kit, mode).add(CURRENT)

    await kit.serve(at=NOW + NAMES_LIFETIME)

    assert kit.names.stored("okc") == before
    assert before is not None
    assert before[-1].to is None
    state = kit.store.feed_build(KIND, "okc")
    assert state is not None
    assert state.last_failure is not None


@pytest.mark.anyio
async def test_a_current_season_that_cannot_be_read_and_nothing_stored_is_unavailable(
    kit: NamesKit,
) -> None:
    kit.failing = {CURRENT}

    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.names.stored("okc") is None


@pytest.mark.anyio
async def test_a_build_with_no_readable_season_and_nothing_stored_is_unavailable(
    kit: NamesKit,
) -> None:
    kit.all_failing = True

    with pytest.raises(FeedUnavailableError):
        await kit.serve()

    assert kit.names.stored("okc") is None


@pytest.mark.anyio
async def test_a_code_outside_the_30_is_unknown_and_an_unknown_season_is_not_ready(
    kit: NamesKit,
) -> None:
    assert kit.names.check("xyz") is IdStatus.UNKNOWN
    assert kit.names.check("OKC") is IdStatus.UNKNOWN
    assert kit.names.check("okc") is IdStatus.KNOWN
    with pytest.raises(UnknownFeedError):
        await kit.cache.serve(KIND, "xyz")
    kit.stars.season = None
    assert kit.names.check("okc") is IdStatus.NOT_READY
    assert kit.calls == []


def test_the_cleanup_keeps_the_30_codes_only(kit: NamesKit) -> None:
    assert kit.names.keep("okc") is True
    assert kit.names.keep("xyz") is False
