# api/tests/jobs/test_team_names.py
#
# Tests for the franchise names builder and its feed kind.
#
# Tested:
# - One run for a franchise whose every season is equal, open at the current season
# - Four runs for four identities, oldest first, past runs closed and the last open
# - A skipped season does not split a run, and a run that does not hold the current season stays closed
# - A provider code becomes its standard code and a historical code stays as sent
# - The kind: every season from 1994 to the current one is read once; a season whose read fails is skipped with a log line that carries the code and season and no URL; a season with no team object is skipped
# - The kind: a season whose team object is inactive is read, and a relocated franchise has one run per identity
# - The kind: a stored list is fresh for 24 hours and then only the current season is read again
# - The kind: the built list carries the current build version; a stored list of an older or missing version is rebuilt in full on its next request and one of the current version makes no read inside 24 hours (ADR 0055, ADR 0065)
# - The kind: a current season that cannot be read (failed or no team object) is named by the open run of the stored list, else the latest season read, else the team code, and the list is stored incomplete with one log line (ADR 0064)
# - The kind: a current season that cannot be read keeps the stored runs unchanged, also when an earlier season fails with it; a current season 404 records no absence and is read again after the retry window (real adapter, ADR 0064)
# - The kind: an incomplete list is fresh for the 10 minute retry window only, then reads the current season again
# - season_identity: always reads the season team object and ignores a stored run, none on a 404
# - season_names: the season code and not historical for an unchanged franchise, a relocated franchise historical with its season code, a provider code mapped before the comparison, a code with no team left out (ADR 0054)
# - The code of a historical identity is the source's own abbreviation, never mapped; an identity equal to today's keeps the standard code, in the runs and in season_names (ADR 0055)
# - season_named: renames a league side with its season code and flag and leaves a guest and an unknown code
# - league_codes and named_sides: every non-guest side found in nested models and lists, and every side renamed with the rest kept identical
# - run_code: the open run for the current season, a closed run inside its span and on both ends, none before 1994 and with no runs; with_career_codes: the code of each team of a season row from the runs, null where no run holds the season, every other field identical (ADR 0055)
# - league_codes and named_sides: the team code of a coded model (a leader, an award winner, the Finals MVP) is found and gets its season code, and a model without the field stays identical (ADR 0055)
# - payload_names: a payload name equal to today's keeps the standard code and is not historical, another name keeps the payload's abbreviation and is historical, no stored list gives the mapped code and not historical, and a code with no payload is left out (ADR 0058)
# - identities_of: the season codes, names, cities and flags a named feed already carries on its league sides, the first side of a code wins, a guest and an unnamed side are left out (ADR 0058)
# - with_current_season: unchanged runs for an unchanged identity, the open run closed and a new one opened on a new identity, and the cases with no open run
# - The kind: a full build runs only without a list of the current build version, and a stored one reads the current season alone
# - The kind: a full build stays within its read budget of the seasons plus 2 through the real adapter, and one past it fails and keeps the stored list
# - The kind: a failed current season re-read keeps the stored runs incomplete
# - The kind: a list records the past seasons whose read failed (not a season with no team object); the next re-read reads the current season and each missing season, merges them into the stored runs, keeps a season that fails again missing, and stays within the missing count plus 3 reads (ADR 0065)
# - career_runs never starts a build and reads no source
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
from typing import Any, cast

import httpx
import pytest
import respx

from app.feeds.base import FeedModel
from app.feeds.opponent import Opponent
from app.feeds.player import PlayerFeed
from app.feeds.playoffs import AwardWinner, PlayoffLeader
from app.feeds.playoffs_finals import FinalsMvp
from app.feeds.team import NameRun, TeamNames
from app.jobs.on_demand import (
    RETRY_AFTER,
    SEASON_BUILD_VERSION,
    FeedCache,
    IdStatus,
    UnknownFeedError,
)
from app.jobs.stars import StarsJob
from app.jobs.team_names import (
    CURRENT_SEASON_LIFETIME,
    KIND,
    SeasonIdentity,
    TeamNamesFeeds,
    build_name_runs,
    career_team_codes,
    identities_of,
    league_codes,
    named_sides,
    payload_names,
    run_code,
    season_named,
    with_career_codes,
    with_current_season,
)
from app.settings import Settings
from app.sources.http import SourceClient, SourceError, create_client, get_json
from app.sources.season_team import SeasonTeam
from app.sources.teams import SeasonTeamName
from app.storage.feeds import publish_by_id, read_by_id
from app.storage.state import StateStore
from tests.feeds.test_player import season_row, valid_player

NOW = dt.datetime(2026, 10, 8, 15, 0, tzinfo=dt.UTC)
CURRENT = 2027


def team(
    name: str = "Thunder",
    location: str = "Oklahoma City",
    abbreviation: str = "OKC",
) -> SeasonTeam:
    return SeasonTeam(
        team_id="25",
        abbreviation=abbreviation,
        display_name=f"{location} {name}",
        name=name,
        location=location,
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


def test_the_code_of_a_historical_identity_is_the_source_abbreviation_and_today_is_mapped() -> (
    None
):
    seasons = [
        (2005, team("Delta Herons", "New Orleans", "NO")),
        (2006, team("Delta Herons", "New Orleans", "NO")),
        (2027, team("River Kings", "New Orleans", "NO")),
    ]

    runs = build_name_runs(seasons, CURRENT)

    assert [(r.name, r.code, r.from_, r.to) for r in runs] == [
        ("Delta Herons", "NO", 2005, 2006),
        ("River Kings", "NOP", 2027, None),
    ]


def test_an_identity_with_todays_name_and_city_keeps_the_standard_code() -> None:
    seasons = [
        (2005, team("River Kings", "New Orleans", "NO")),
        (2027, team("River Kings", "New Orleans", "NO")),
    ]

    runs = build_name_runs(seasons, CURRENT)

    assert [(r.code, r.from_, r.to) for r in runs] == [("NOP", 2005, None)]


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
        self.all_failing = False
        self.provider_code = False
        self.current_team: SeasonTeam | None = None
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
        if self.current_team is not None and season == CURRENT:
            return self.current_team
        if self.provider_code:
            return team(abbreviation="GS" if season < 2008 else "GSW")
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
async def test_a_failed_and_a_missing_season_are_skipped_and_the_runs_merge(
    kit: NamesKit, caplog: pytest.LogCaptureFixture
) -> None:
    kit.failing = {2000}
    kit.missing = {2001}

    with caplog.at_level(logging.WARNING):
        await kit.serve()

    runs = kit.names.stored("okc")
    assert runs is not None
    assert [(r.from_, r.to) for r in runs] == [(1994, 2007), (2008, None)]
    messages = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(messages) == 2
    assert any("okc season 2000 skipped" in m for m in messages)
    assert any("okc season 2001 skipped: no team" in m for m in messages)
    assert not any("http" in m for m in messages)


@pytest.mark.anyio
async def test_a_stored_list_is_fresh_for_24_hours_and_then_only_the_current_season_is_read_again(
    kit: NamesKit,
) -> None:
    await kit.serve()
    first = len(kit.calls)
    assert CURRENT_SEASON_LIFETIME == dt.timedelta(hours=24)

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME - dt.timedelta(seconds=1))
    assert len(kit.calls) == first

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)
    assert kit.calls[first:] == [("OKC", CURRENT)]
    assert stored_names(kit).complete is True


@pytest.mark.anyio
async def test_the_built_list_carries_the_current_build_version(kit: NamesKit) -> None:
    await kit.serve()

    body = read_by_id(kit.path, KIND, "okc")
    assert body is not None
    assert TeamNames.model_validate_json(body).build_version == SEASON_BUILD_VERSION
    assert kit.names.outdated("okc") is False
    assert kit.names.outdated("bos") is False


@pytest.mark.anyio
@pytest.mark.parametrize("version", [None, SEASON_BUILD_VERSION + 1])
async def test_a_stored_list_of_an_older_or_missing_version_is_rebuilt_in_full_on_its_next_request(
    kit: NamesKit, version: int | None
) -> None:
    await kit.serve()
    stored = kit.names.stored("okc")
    assert stored is not None
    publish_by_id(
        kit.path,
        KIND,
        TeamNames,
        "okc",
        TeamNames(runs=stored, build_version=version),
    )
    assert kit.names.outdated("okc") is True
    reads = len(kit.calls)

    await kit.serve(at=NOW + dt.timedelta(days=1))

    assert len(kit.calls) == 2 * reads
    assert kit.names.outdated("okc") is False


@pytest.mark.anyio
async def test_a_list_of_the_current_version_inside_24_hours_makes_no_read(
    kit: NamesKit,
) -> None:
    await kit.serve()
    reads = len(kit.calls)

    await kit.serve(at=NOW + dt.timedelta(hours=23))

    assert len(kit.calls) == reads


def stored_names(kit: NamesKit) -> TeamNames:
    body = read_by_id(kit.path, KIND, "okc")
    assert body is not None
    return TeamNames.model_validate_json(body)


@pytest.mark.anyio
async def test_a_build_with_no_readable_season_names_the_current_run_from_the_stored_list(
    kit: NamesKit, caplog: pytest.LogCaptureFixture
) -> None:
    await kit.serve()
    assert stored_names(kit).complete is True
    kit.all_failing = True

    with caplog.at_level(logging.WARNING, logger="app.jobs.team_names"):
        await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    names = stored_names(kit)
    assert names.complete is False
    assert identities(names.runs) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (2008, None, "Thunder", "Oklahoma City", "OKC"),
    ]
    assert any(
        r.getMessage()
        == f"team names: okc current season {CURRENT} not read; built from stored list"
        for r in caplog.records
    )
    state = kit.store.feed_build(KIND, "okc")
    assert state is not None and state.last_failure is None


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["failing", "missing"])
async def test_a_failed_current_season_read_takes_the_current_run_from_the_stored_list(
    kit: NamesKit, mode: str
) -> None:
    await kit.serve()
    before = kit.names.stored("okc")
    getattr(kit, mode).add(CURRENT)

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    assert before is not None
    assert before[-1].to is None
    names = stored_names(kit)
    assert names.runs == before
    assert names.complete is False


@pytest.mark.anyio
async def test_a_partial_read_keeps_the_stored_runs_when_the_current_season_and_an_earlier_one_fail(
    kit: NamesKit,
) -> None:
    await kit.serve()
    before = kit.names.stored("okc")
    kit.failing = {CURRENT, 2000, 2010}

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    names = stored_names(kit)
    assert before is not None and len(before) == 2
    assert names.runs == before
    assert names.complete is False


@pytest.mark.anyio
async def test_a_failed_current_season_read_with_nothing_stored_takes_the_latest_read_season(
    kit: NamesKit, caplog: pytest.LogCaptureFixture
) -> None:
    kit.failing = {CURRENT}

    with caplog.at_level(logging.WARNING, logger="app.jobs.team_names"):
        await kit.serve()

    names = stored_names(kit)
    assert names.complete is False
    assert identities(names.runs) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (2008, None, "Thunder", "Oklahoma City", "OKC"),
    ]
    assert any(
        r.getMessage()
        == f"team names: okc current season {CURRENT} not read; built from season {CURRENT - 1}"
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_with_no_season_read_the_current_run_is_named_by_the_team_code(
    kit: NamesKit, caplog: pytest.LogCaptureFixture
) -> None:
    kit.all_failing = True

    with caplog.at_level(logging.WARNING, logger="app.jobs.team_names"):
        await kit.serve()

    names = stored_names(kit)
    assert names.complete is False
    assert identities(names.runs) == [(CURRENT, None, "OKC", "OKC", "OKC")]
    assert any(
        r.getMessage().endswith("not read; built from team code")
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_an_incomplete_list_is_stale_after_the_retry_window_and_reads_the_current_season_again(
    kit: NamesKit,
) -> None:
    kit.failing = {CURRENT}
    await kit.serve()
    first = len(kit.calls)

    await kit.serve(at=NOW + RETRY_AFTER - dt.timedelta(seconds=1))
    assert len(kit.calls) == first

    kit.failing = set()
    await kit.serve(at=NOW + RETRY_AFTER)
    assert kit.calls[first:] == [("OKC", CURRENT)]
    assert stored_names(kit).complete is True

    await kit.serve(
        at=NOW + RETRY_AFTER + CURRENT_SEASON_LIFETIME - dt.timedelta(seconds=1)
    )
    assert len(kit.calls) == first + 1


@pytest.mark.anyio
async def test_a_current_season_404_is_not_recorded_so_the_retry_reads_it_again(
    tmp_path: Path,
) -> None:
    template = "https://example.com/seasons/{season}/teams/{team_id}"
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=tmp_path, season_team_url=template
    )
    clock = [NOW]
    store = StateStore(tmp_path)
    store.migrate()
    cache = FeedCache(tmp_path, store, clock=lambda: clock[0])
    TeamNamesFeeds(
        settings,
        store,
        create_client(store, clock=lambda: clock[0]),
        cache,
        cast(StarsJob, FakeStars()),
    )
    body = {
        "id": "25",
        "abbreviation": "OKC",
        "displayName": "Oklahoma City Thunder",
        "name": "Thunder",
        "location": "Oklahoma City",
    }
    with respx.mock as mock:
        current = mock.get(f"https://example.com/seasons/{CURRENT}/teams/25").respond(
            404
        )
        mock.get(url__regex=r"https://example\.com/seasons/\d+/teams/25").respond(
            json=body
        )
        await cache.serve(KIND, "okc")
        while cache.in_flight:
            await next(iter(cache.in_flight.values()))
            await asyncio.sleep(0)
        assert current.call_count == 1
        assert not store.season_team_absent("OKC", CURRENT, NOW - dt.timedelta(days=1))

        clock[0] = NOW + RETRY_AFTER + dt.timedelta(hours=2)
        await cache.serve(KIND, "okc")
        while cache.in_flight:
            await next(iter(cache.in_flight.values()))
            await asyncio.sleep(0)

    assert current.call_count == 2


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


@pytest.mark.anyio
async def test_a_season_is_read_whatever_the_provider_says_of_its_team_being_active(
    kit: NamesKit,
) -> None:
    await kit.serve()

    assert ("OKC", 2002) in kit.calls

    runs = kit.names.stored("okc")
    assert runs is not None
    assert [(r.from_, r.to) for r in runs] == [(1994, 2007), (2008, None)]


def test_a_relocated_franchise_has_one_run_per_identity_from_1994_to_today() -> None:
    seasons = [(s, team("Harbor Gulls", "Seattle", "SEA")) for s in range(1994, 2009)]
    seasons += [(s, team()) for s in range(2009, CURRENT + 1)]

    runs = build_name_runs(seasons, CURRENT)

    assert identities(runs) == [
        (1994, 2008, "Harbor Gulls", "Seattle", "SEA"),
        (2009, None, "Thunder", "Oklahoma City", "OKC"),
    ]


@pytest.mark.anyio
async def test_season_identity_ignores_a_stored_run_that_bridges_a_gap(
    kit: NamesKit,
) -> None:
    bridged = TeamNames(
        runs=[
            NameRun.model_validate(
                {
                    "from": 1994,
                    "to": None,
                    "name": "Hornets",
                    "location": "Charlotte",
                    "code": "CHA",
                }
            )
        ]
    )
    assert publish_by_id(kit.path, KIND, TeamNames, "okc", bridged)

    assert await kit.names.season_identity("OKC", 2000) == ("Harbor Gulls", "Seattle")
    assert await kit.names.season_identity("okc", 2020) == ("Thunder", "Oklahoma City")
    assert kit.calls == [("OKC", 2000), ("OKC", 2020)]


@pytest.mark.anyio
async def test_season_identity_reads_the_season_team_object(
    kit: NamesKit,
) -> None:
    assert await kit.names.season_identity("OKC", 2000) == ("Harbor Gulls", "Seattle")
    assert kit.calls == [("OKC", 2000)]


@pytest.mark.anyio
async def test_season_identity_is_none_on_a_404(kit: NamesKit) -> None:
    kit.missing = {2000}

    assert await kit.names.season_identity("OKC", 2000) is None


@pytest.mark.anyio
async def test_season_names_leaves_out_the_codes_with_no_team(kit: NamesKit) -> None:
    kit.missing = {2000}

    assert await kit.names.season_names(["OKC"], 2000) == {}
    assert await kit.names.season_names(["OKC", "OKC"], 2001) == {
        "OKC": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True)
    }


@pytest.mark.anyio
async def test_season_names_gives_the_season_code_and_not_historical_for_an_unchanged_franchise(
    kit: NamesKit,
) -> None:
    assert await kit.names.season_names(["OKC"], 2015) == {
        "OKC": SeasonIdentity("Thunder", "Oklahoma City", "OKC", False)
    }


@pytest.mark.anyio
async def test_season_names_marks_a_relocated_franchise_historical_with_its_season_code(
    kit: NamesKit,
) -> None:
    names = await kit.names.season_names(["OKC"], 2000)

    assert (names["OKC"].code, names["OKC"].historical) == ("SEA", True)


@pytest.mark.anyio
async def test_a_provider_code_maps_to_its_standard_code_before_the_comparison(
    kit: NamesKit,
) -> None:
    kit.provider_code = True

    names = await kit.names.season_names(["GSW"], 2000)

    assert names["GSW"] == SeasonIdentity("Thunder", "Oklahoma City", "GSW", False)


@pytest.mark.anyio
async def test_season_names_is_not_historical_when_the_current_season_has_no_team(
    kit: NamesKit,
) -> None:
    kit.missing = {CURRENT}

    names = await kit.names.season_names(["OKC"], 2000)

    assert names["OKC"].historical is False


def test_season_named_renames_a_league_side_and_leaves_a_guest_and_an_unknown_code() -> (
    None
):
    names = {"OKC": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True)}
    league = Opponent(code="OKC", name="Thunder", city="Oklahoma City")
    guest = Opponent(code="OKC", name="Guests", city=None, guest=True)
    other = Opponent(code="BOS", name="Celtics", city="Boston")

    renamed = season_named(league, names)

    assert (renamed.code, renamed.name, renamed.city) == (
        "OKC",
        "Harbor Gulls",
        "Seattle",
    )
    assert (renamed.season_code, renamed.historical) == ("SEA", True)
    assert season_named(guest, names) is guest
    assert season_named(other, names) is other


class Pair(FeedModel):
    away: Opponent
    home: Opponent


class Holder(FeedModel):
    label: str
    pair: Pair
    others: list[Opponent]


def holder() -> Holder:
    return Holder(
        label="kept",
        pair=Pair(
            away=Opponent(code="OKC", name="Thunder", city="Oklahoma City"),
            home=Opponent(code="BOS", name="Celtics", city="Boston"),
        ),
        others=[
            Opponent(code="OKC", name="Thunder", city="Oklahoma City"),
            Opponent(code="HCM", name="Guests", city=None, guest=True),
        ],
    )


def test_league_codes_finds_every_non_guest_side_in_nested_models_and_lists() -> None:
    assert league_codes(holder()) == ["BOS", "OKC"]


def test_named_sides_renames_every_side_of_a_feed_and_keeps_the_rest_identical() -> (
    None
):
    names = {"OKC": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True)}

    renamed = named_sides(holder(), names)

    assert renamed.label == "kept"
    assert (renamed.pair.away.name, renamed.pair.away.season_code) == (
        "Harbor Gulls",
        "SEA",
    )
    assert renamed.others[0].historical is True
    assert renamed.pair.home == holder().pair.home
    assert renamed.others[1] == holder().others[1]


def career_feed(seasons: list[str]) -> dict[str, Any]:
    """A valid player payload whose season rows, regular and playoffs, list TOR
    and BKN for each of the seasons, newest first."""
    player = valid_player()

    def rows(per_game: bool) -> list[dict[str, Any]]:
        return [
            {**season_row(label, per_game), "teams": ["TOR", "BKN"]}
            for label in seasons
        ]

    for kind in ("regular", "playoffs"):
        player["seasons"][kind] = {
            "perGame": rows(True),
            "totals": rows(False),
            "career": None,
        }
    player["profile"]["debutSeason"] = seasons[-1]
    player["profile"]["seasons"] = len(seasons)
    return player


def career_runs() -> dict[str, list[NameRun]]:
    return {
        "BKN": [
            NameRun(
                from_=1994,
                to=2012,
                name="Harbor Nets",
                location="New Jersey",
                code="NJ",
            ),
            NameRun(
                from_=2013,
                to=None,
                name="Harbor Nets",
                location="Brooklyn",
                code="BKN",
            ),
        ],
        "TOR": [
            NameRun(from_=1994, to=None, name="Raptors", location="Toronto", code="TOR")
        ],
    }


def test_run_code_gives_the_open_run_for_the_current_season_and_a_closed_run_on_its_ends() -> (
    None
):
    runs = career_runs()["BKN"]

    assert run_code(runs, CURRENT) == "BKN"
    assert run_code(runs, 2013) == "BKN"
    assert run_code(runs, 2012) == "NJ"
    assert run_code(runs, 1994) == "NJ"
    assert run_code(runs, 2005) == "NJ"


def test_run_code_gives_none_before_1994_and_with_no_runs() -> None:
    assert run_code(career_runs()["BKN"], 1993) is None
    assert run_code([], 2005) is None


def test_with_career_codes_sets_the_code_of_each_team_in_its_season() -> None:
    feed = PlayerFeed.model_validate(career_feed(["2004-05", "1992-93"]))

    coded = with_career_codes(feed, career_runs())

    per_game = coded.seasons.regular.per_game
    assert per_game[0].season_codes == ["TOR", "NJ"]
    assert per_game[1].season_codes == [None, None]
    assert coded.seasons.regular.totals[0].season_codes == ["TOR", "NJ"]
    assert coded.seasons.playoffs.per_game[0].season_codes == ["TOR", "NJ"]


def test_with_career_codes_gives_none_to_a_code_with_no_runs_and_changes_nothing_else() -> (
    None
):
    feed = PlayerFeed.model_validate(career_feed(["2004-05"]))

    coded = with_career_codes(feed, {"TOR": career_runs()["TOR"]})

    assert coded.seasons.regular.per_game[0].season_codes == ["TOR", None]
    assert coded.model_dump(exclude={"seasons"}) == feed.model_dump(exclude={"seasons"})
    for before, after in zip(
        feed.seasons.regular.per_game, coded.seasons.regular.per_game, strict=True
    ):
        assert after.model_dump(exclude={"season_codes"}) == before.model_dump(
            exclude={"season_codes"}
        )
    assert career_team_codes(feed) == ["BKN", "TOR"]


class Coded(FeedModel):
    label: str
    leaders: list[PlayoffLeader]
    mvp: FinalsMvp | None
    winner: AwardWinner


def coded() -> Coded:
    return Coded(
        label="kept",
        leaders=[
            PlayoffLeader(
                rank=1,
                player_id="1",
                name="Ada Example",
                photo_url=None,
                team_code="OKC",
                value="30.0",
            )
        ],
        mvp=FinalsMvp(
            player_id="1",
            name="Ada Example",
            photo_url=None,
            team_code="BOS",
            games=None,
            points=None,
            rebounds=None,
            assists=None,
            best_game=None,
        ),
        winner=AwardWinner(
            player_id="2", name="Ben Sample", photo_url=None, team_code=None
        ),
    )


def test_league_codes_also_finds_the_team_code_of_a_coded_model() -> None:
    assert league_codes(coded()) == ["BOS", "OKC"]


def test_named_sides_sets_the_season_code_of_a_coded_model_and_leaves_the_rest() -> (
    None
):
    names = {"OKC": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True)}

    renamed = named_sides(coded(), names)

    assert renamed.leaders[0].season_code == "SEA"
    assert renamed.mvp is not None and renamed.mvp.season_code is None
    assert renamed.winner.season_code is None
    assert renamed.leaders[0].model_dump(exclude={"season_code"}) == coded().leaders[
        0
    ].model_dump(exclude={"season_code"})
    assert renamed.label == "kept"


def test_named_sides_leaves_a_model_without_a_season_code_field_identical() -> None:
    assert named_sides(holder(), {}) == holder()


def new_orleans(name: str, abbreviation: str = "NO") -> SeasonTeam:
    return team(name, "New Orleans", abbreviation)


@pytest.mark.anyio
async def test_season_names_gives_a_historical_identity_the_source_abbreviation(
    tmp_path: Path,
) -> None:
    store = StateStore(tmp_path)
    store.migrate()
    seen: dict[int, SeasonTeam] = {
        2005: new_orleans("Delta Herons"),
        2010: new_orleans("River Kings"),
        CURRENT: new_orleans("River Kings"),
    }

    async def fetch(
        client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        return seen.get(season)

    names = TeamNamesFeeds(
        Settings(_env_file=None, data_dir=tmp_path),  # type: ignore[call-arg]
        store,
        create_client(store),
        FeedCache(tmp_path, store),
        cast(StarsJob, FakeStars()),
        fetch_season_team=fetch,
    )

    old = await names.season_names(["NOP"], 2005)
    same = await names.season_names(["NOP"], 2010)

    assert old["NOP"] == SeasonIdentity("Delta Herons", "New Orleans", "NO", True)
    assert same["NOP"] == SeasonIdentity("River Kings", "New Orleans", "NOP", False)


def today_run(name: str, location: str, code: str) -> list[NameRun]:
    return [
        NameRun.model_validate(
            {"from": 1994, "to": None, "name": name, "location": location, "code": code}
        )
    ]


def payload(abbreviation: str, name: str, location: str) -> SeasonTeamName:
    return SeasonTeamName(abbreviation=abbreviation, name=name, location=location)


def test_payload_names_keeps_the_standard_code_when_the_name_is_the_one_of_today() -> (
    None
):
    names = payload_names(
        {"GSW": payload("GS", "Warriors", "Golden State")},
        {"GSW": today_run("Warriors", "Golden State", "GSW")},
    )

    assert names["GSW"] == SeasonIdentity("Warriors", "Golden State", "GSW", False)


def test_payload_names_keeps_the_payload_abbreviation_and_flags_another_name_as_historical() -> (
    None
):
    names = payload_names(
        {"OKC": payload("SEA", "Harbor Gulls", "Seattle")},
        {"OKC": today_run("Thunder", "Oklahoma City", "OKC")},
    )

    assert names["OKC"] == SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True)


def test_payload_names_flags_a_same_name_whose_code_differs_from_todays_stored_code() -> (
    None
):
    names = payload_names(
        {"OKC": payload("OKC", "Thunder", "Oklahoma City")},
        {"OKC": today_run("Thunder", "Oklahoma City", "ZZZ")},
    )

    assert names["OKC"] == SeasonIdentity("Thunder", "Oklahoma City", "OKC", True)


def test_payload_names_without_a_stored_list_maps_the_code_and_is_not_historical() -> (
    None
):
    names = payload_names(
        {
            "GSW": payload("GS", "Warriors", "Golden State"),
            "OKC": payload("SEA", "G", "S"),
        },
        {},
    )

    assert names["GSW"] == SeasonIdentity("Warriors", "Golden State", "GSW", False)
    assert (names["OKC"].code, names["OKC"].historical) == ("SEA", False)
    assert (
        payload_names({}, {"OKC": today_run("Thunder", "Oklahoma City", "OKC")}) == {}
    )


def test_payload_names_takes_today_from_the_open_run_only() -> None:
    closed = [
        NameRun.model_validate(
            {
                "from": 1994,
                "to": 2008,
                "name": "Harbor Gulls",
                "location": "Seattle",
                "code": "SEA",
            }
        ),
        *today_run("Thunder", "Oklahoma City", "OKC"),
    ]

    names = payload_names(
        {"OKC": payload("SEA", "Harbor Gulls", "Seattle")}, {"OKC": closed}
    )

    assert names["OKC"].historical is True


def test_identities_of_reads_the_identities_a_named_feed_carries_on_its_sides() -> None:
    feed = holder()
    named = named_sides(
        feed,
        {
            "OKC": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True),
            "BOS": SeasonIdentity("Celtics", "Boston", "BOS", False),
        },
    )

    assert identities_of(named) == {
        "OKC": SeasonIdentity("Harbor Gulls", "Seattle", "SEA", True),
        "BOS": SeasonIdentity("Celtics", "Boston", "BOS", False),
    }
    # A side with no season code and a guest are left out.
    assert identities_of(feed) == {}


# Group: the current season read again, the full build and the read budget


def open_runs() -> list[NameRun]:
    return build_name_runs(
        [
            *((s, team("Harbor Gulls", "Seattle", "SEA")) for s in range(1994, 2008)),
            *((s, team()) for s in range(2008, CURRENT + 1)),
        ],
        CURRENT,
    )


def test_with_current_season_keeps_the_runs_when_the_identity_is_unchanged() -> None:
    runs = open_runs()

    assert with_current_season(runs, CURRENT, team()) == runs
    assert with_current_season(runs, CURRENT, team(abbreviation="OKC")) == runs


def test_with_current_season_closes_the_open_run_and_opens_one_on_a_new_identity() -> (
    None
):
    runs = with_current_season(
        open_runs(), CURRENT, team("Storm", "Oklahoma City", "OKC")
    )

    assert identities(runs) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (2008, CURRENT - 1, "Thunder", "Oklahoma City", "OKC"),
        (CURRENT, None, "Storm", "Oklahoma City", "OKC"),
    ]

    started_now = [
        *open_runs()[:1],
        NameRun.model_validate(
            {
                "from": CURRENT,
                "to": None,
                "name": "Thunder",
                "location": "Oklahoma City",
                "code": "OKC",
            }
        ),
    ]
    renamed = with_current_season(started_now, CURRENT, team("Storm", "OKC", "OKC"))
    assert identities(renamed) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (CURRENT, None, "Storm", "OKC", "OKC"),
    ]


def test_with_current_season_maps_a_provider_code_before_comparing() -> None:
    runs = open_runs()

    assert with_current_season(runs, CURRENT, team(abbreviation="OKC")) == runs
    gs = [NameRun.model_validate(_run(1994, None, "Warriors", "Golden State", "GSW"))]
    assert (
        with_current_season(gs, CURRENT, team("Warriors", "Golden State", "GS")) == gs
    )


def _run(
    from_: int, to: int | None, name: str, location: str, code: str
) -> dict[str, Any]:
    return {"from": from_, "to": to, "name": name, "location": location, "code": code}


def test_with_current_season_without_an_open_run() -> None:
    closed = [
        NameRun.model_validate(
            _run(1994, CURRENT - 1, "Thunder", "Oklahoma City", "OKC")
        )
    ]
    stale = [
        NameRun.model_validate(
            _run(1994, CURRENT - 3, "Thunder", "Oklahoma City", "OKC")
        )
    ]

    assert identities(with_current_season(closed, CURRENT, team())) == [
        (1994, None, "Thunder", "Oklahoma City", "OKC")
    ]
    assert identities(
        with_current_season(closed, CURRENT, team("Storm", "Oklahoma City", "OKC"))
    ) == [
        (1994, CURRENT - 1, "Thunder", "Oklahoma City", "OKC"),
        (CURRENT, None, "Storm", "Oklahoma City", "OKC"),
    ]
    assert identities(with_current_season(stale, CURRENT, team())) == [
        (1994, CURRENT - 3, "Thunder", "Oklahoma City", "OKC"),
        (CURRENT, None, "Thunder", "Oklahoma City", "OKC"),
    ]
    assert identities(with_current_season([], CURRENT, team())) == [
        (CURRENT, None, "Thunder", "Oklahoma City", "OKC")
    ]


@pytest.mark.anyio
async def test_a_full_build_runs_only_without_a_list_of_the_current_build_version(
    kit: NamesKit,
) -> None:
    seasons = CURRENT - 1994 + 1

    await kit.serve()
    assert len(kit.calls) == seasons

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)
    assert len(kit.calls) == seasons + 1

    stored = kit.names.stored("okc")
    assert stored is not None
    publish_by_id(
        kit.path, KIND, TeamNames, "okc", TeamNames(runs=stored, build_version=None)
    )
    await kit.serve(at=NOW + 2 * CURRENT_SEASON_LIFETIME)
    assert len(kit.calls) == 2 * seasons + 1


@pytest.mark.anyio
async def test_a_failed_current_season_reread_keeps_the_stored_runs_incomplete(
    kit: NamesKit,
) -> None:
    await kit.serve()
    before = kit.names.stored("okc")
    kit.failing = {CURRENT}
    reads = len(kit.calls)

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    assert kit.calls[reads:] == [("OKC", CURRENT)]
    names = stored_names(kit)
    assert names.runs == before
    assert names.complete is False
    assert names.build_version == SEASON_BUILD_VERSION


@pytest.mark.anyio
async def test_a_rename_of_the_current_season_closes_the_stored_open_run(
    kit: NamesKit,
) -> None:
    await kit.serve()
    kit.current_team = team("Storm", "Oklahoma City", "OKC")
    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    assert identities(stored_names(kit).runs)[-2:] == [
        (2008, CURRENT - 1, "Thunder", "Oklahoma City", "OKC"),
        (CURRENT, None, "Storm", "Oklahoma City", "OKC"),
    ]


@pytest.mark.anyio
async def test_a_total_outage_is_healed_by_the_retry_after_the_retry_window(
    kit: NamesKit,
) -> None:
    kit.all_failing = True
    await kit.serve()
    names = stored_names(kit)
    assert names.complete is False
    assert names.missing == list(range(1994, CURRENT))
    first = len(kit.calls)

    kit.all_failing = False
    await kit.serve(at=NOW + RETRY_AFTER)

    assert sorted(kit.calls[first:]) == [("OKC", s) for s in range(1994, CURRENT + 1)]
    healed = stored_names(kit)
    assert healed.complete is True
    assert healed.missing == []
    assert identities(healed.runs) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (2008, None, "Thunder", "Oklahoma City", "OKC"),
    ]


@pytest.mark.anyio
async def test_a_partial_first_build_is_healed_by_the_24_hour_reread(
    kit: NamesKit,
) -> None:
    kit.failing = set(range(1994, 2008))
    await kit.serve()
    names = stored_names(kit)
    assert names.complete is True
    assert names.missing == list(range(1994, 2008))
    assert identities(names.runs) == [(2008, None, "Thunder", "Oklahoma City", "OKC")]
    first = len(kit.calls)

    kit.failing = set()
    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    assert len(kit.calls[first:]) == 15
    healed = stored_names(kit)
    assert healed.missing == []
    assert identities(healed.runs) == [
        (1994, 2007, "Harbor Gulls", "Seattle", "SEA"),
        (2008, None, "Thunder", "Oklahoma City", "OKC"),
    ]


@pytest.mark.anyio
async def test_a_missing_season_that_fails_again_stays_missing(kit: NamesKit) -> None:
    kit.failing = {2000, 2001}
    await kit.serve()
    first = len(kit.calls)
    kit.failing = {2000}

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    assert sorted(kit.calls[first:]) == [("OKC", 2000), ("OKC", 2001), ("OKC", CURRENT)]
    names = stored_names(kit)
    assert names.missing == [2000]
    assert [(r.from_, r.to) for r in names.runs] == [(1994, 2007), (2008, None)]


@pytest.mark.anyio
async def test_a_season_with_no_team_object_is_not_missing_and_is_not_read_again(
    kit: NamesKit,
) -> None:
    kit.missing = {2001}
    await kit.serve()
    assert stored_names(kit).missing == []
    first = len(kit.calls)

    await kit.serve(at=NOW + CURRENT_SEASON_LIFETIME)

    assert kit.calls[first:] == [("OKC", CURRENT)]


@pytest.mark.anyio
async def test_the_reread_stays_within_the_missing_count_plus_3_reads(
    tmp_path: Path,
) -> None:
    cache, _, clock = real_names(tmp_path)
    body = {
        "id": "25",
        "abbreviation": "OKC",
        "displayName": "Oklahoma City Thunder",
        "name": "Thunder",
        "location": "Oklahoma City",
    }
    with respx.mock as mock:
        down = mock.get(
            url__regex=r"https://example\.com/seasons/(2000|2001)/teams/25"
        ).respond(404)
        down.side_effect = httpx.ConnectError("down")
        mock.get(url__regex=r"https://example\.com/seasons/\d+/teams/25").respond(
            json=body
        )
        await cache.serve(KIND, "okc")
        await drain(cache)
        stored = TeamNames.model_validate_json(read_by_id(tmp_path, KIND, "okc") or b"")
        assert stored.missing == [2000, 2001]

        down.side_effect = None
        down.respond(json=body)
        mock.calls.reset()
        clock[0] = NOW + CURRENT_SEASON_LIFETIME
        await cache.serve(KIND, "okc")
        await drain(cache)

    assert len(mock.calls) <= len(stored.missing) + 3
    healed = TeamNames.model_validate_json(read_by_id(tmp_path, KIND, "okc") or b"")
    assert healed.missing == []


def test_career_runs_never_starts_a_build(kit: NamesKit) -> None:
    assert kit.names.career_runs(["okc", "bos"]) == {}
    assert kit.cache.in_flight == {}
    assert kit.calls == []


@pytest.mark.anyio
async def test_career_runs_gives_an_outdated_list_and_starts_no_build(
    kit: NamesKit,
) -> None:
    await kit.serve()
    stored = kit.names.stored("okc")
    assert stored is not None
    publish_by_id(
        kit.path, KIND, TeamNames, "okc", TeamNames(runs=stored, build_version=None)
    )
    reads = len(kit.calls)

    found = kit.names.career_runs(["okc", "okc", "bos"])

    assert found == {"okc": stored}
    assert kit.cache.in_flight == {}
    assert len(kit.calls) == reads


def real_names(
    tmp_path: Path, fetch: Any = None
) -> tuple[FeedCache, StateStore, list[dt.datetime]]:
    template = "https://example.com/seasons/{season}/teams/{team_id}"
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=tmp_path, season_team_url=template
    )
    clock = [NOW]
    store = StateStore(tmp_path)
    store.migrate()
    cache = FeedCache(tmp_path, store, clock=lambda: clock[0])
    kwargs = {} if fetch is None else {"fetch_season_team": fetch}
    TeamNamesFeeds(
        settings,
        store,
        create_client(store, clock=lambda: clock[0]),
        cache,
        cast(StarsJob, FakeStars()),
        **kwargs,
    )
    return cache, store, clock


async def drain(cache: FeedCache) -> None:
    while cache.in_flight:
        await next(iter(cache.in_flight.values()))
        await asyncio.sleep(0)


@pytest.mark.anyio
async def test_a_full_build_stays_within_its_read_budget_with_a_counting_fake_client(
    tmp_path: Path,
) -> None:
    cache, _, _ = real_names(tmp_path)
    body = {
        "id": "25",
        "abbreviation": "OKC",
        "displayName": "Oklahoma City Thunder",
        "name": "Thunder",
        "location": "Oklahoma City",
    }
    with respx.mock as mock:
        route = mock.get(
            url__regex=r"https://example\.com/seasons/\d+/teams/25"
        ).respond(json=body)
        await cache.serve(KIND, "okc")
        await drain(cache)

    seasons = CURRENT - 1994 + 1
    assert route.call_count == seasons
    assert route.call_count <= seasons + 2
    assert read_by_id(tmp_path, KIND, "okc") is not None


@pytest.mark.anyio
async def test_a_full_build_past_its_budget_fails_and_keeps_the_stored_list(
    tmp_path: Path,
) -> None:
    async def twice(
        client: SourceClient, code: str, season: int, settings: Settings
    ) -> SeasonTeam | None:
        for part in ("a", "b"):
            await get_json(
                client,
                f"https://example.com/{part}/{season}",
                source="test",
                fresh=dt.timedelta(hours=1),
            )
        return team()

    cache, store, clock = real_names(tmp_path, fetch=twice)
    stored = open_runs()
    publish_by_id(
        tmp_path, KIND, TeamNames, "okc", TeamNames(runs=stored, build_version=None)
    )
    with respx.mock as mock:
        route = mock.get(url__regex=r"https://example\.com/[ab]/\d+").respond(json={})
        body = await cache.serve(KIND, "okc")
        await drain(cache)

    assert TeamNames.model_validate_json(body).runs == stored
    stored_after = read_by_id(tmp_path, KIND, "okc")
    assert stored_after is not None
    assert TeamNames.model_validate_json(stored_after).runs == stored
    assert TeamNames.model_validate_json(stored_after).build_version is None
    assert route.call_count == CURRENT - 1994 + 1 + 2
    state = store.feed_build(KIND, "okc")
    assert state is not None and state.last_failure is not None
    del clock
