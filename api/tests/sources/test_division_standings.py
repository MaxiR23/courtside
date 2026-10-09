# api/tests/sources/test_division_standings.py
#
# Tests for the division standings adapter.
#
# Tested:
# - Maps every team's conference, division, entry orders (and the league-wide provider order, West first when the provider sends it first) and stats from a recorded season
# - Maps the standings before the first game: seed 0, streak and games behind as dashes, no last ten record
# - Requests the configured URL as is, adding nothing to its query, and carries the season end year
# - Falls back to one request for the regular season from a preseason (previous season) and from a postseason (same season)
# - Maps an absent, null or empty streak, games behind and seed to null
# - Maps the division and conference records and the clinch code, a missing record to 0-0, an absent, null or empty clincher to null, every known clinch code and an unknown one to null with a log of the team code
# - Reports whether the standings came from the rule L fallback
# - Raises the source error on a fallback that is not of the regular season, an unknown season type, mixed seasons, without both conferences, with an unknown conference, an unknown team code, a missing stat, an invalid payload, a timeout, an error status (on both requests) and a missing URL
# - Reuses the standings and the fallback for one hour
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixtures are the standings of the finished 2025-26 regular season, of the
# 2026-27 regular season before its first game and of the 2026-27 preseason,
# trimmed to the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_division_standings.py
#
# SEE: api/app/sources/division_standings.py

import datetime as dt
import json
import logging
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.feeds.game_detail import Conference
from app.feeds.standings import Clinch
from app.settings import Settings
from app.sources.division_standings import (
    DivisionStandings,
    fetch_division_standings,
)
from app.sources.http import SourceError, create_client
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "division_standings"
URL = "https://example.com/standings?level=3&seasontype=2"
FALLBACK_URL = "https://example.com/standings?level=3&seasontype=2&season=2026"

Payload = dict[str, Any]


def load(name: str = "regular-2026.json") -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


def division(payload: Payload, conference: int = 0, index: int = 0) -> Payload:
    found: Payload = payload["children"][conference]["children"][index]
    return found


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, division_standings_url=URL)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> DivisionStandings:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_division_standings(client, settings)


def with_season_type(payload: Payload, season_type: int) -> Payload:
    for conference in payload["children"]:
        for found in conference["children"]:
            found["standings"]["seasonType"] = season_type
    return payload


async def fetch_error_of(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> SourceError:
    mock.get(URL).respond(json=payload)
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


@pytest.mark.anyio
async def test_maps_every_teams_conference_division_entry_order_and_stats(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    standings = await fetch(settings)

    assert len(standings.teams) == 30
    okc = standings.teams["OKC"]
    assert (okc.conference, okc.division) == (Conference.WEST, "Northwest")
    assert (okc.division_order, okc.conference_order) == (5, 5)
    assert (okc.location, okc.name, okc.display_name) == (
        "Oklahoma City",
        "Thunder",
        "Oklahoma City Thunder",
    )
    assert (okc.wins, okc.losses, okc.playoff_seed) == (64, 18, 1)
    assert (okc.home, okc.road, okc.last_ten) == ("34-7", "30-10", "7-3")
    assert (okc.streak, okc.games_behind) == ("L2", "-")
    assert okc.avg_points_for == pytest.approx(119.02, abs=0.01)
    assert okc.points_for == pytest.approx(9760)
    assert okc.point_differential == pytest.approx(914)
    # Divisions in order, entries in order.
    assert standings.teams["LAL"].conference_order == 6
    assert standings.teams["SAS"].conference_order == 11
    assert standings.teams["BOS"].conference_order == 1
    assert standings.teams["GSW"].division_order == 3
    assert "GS" not in standings.teams


@pytest.mark.anyio
async def test_numbers_the_entries_across_the_league_in_the_providers_order(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["children"].reverse()
    mock.get(URL).respond(json=payload)

    standings = await fetch(settings)

    west = [
        e.provider_order
        for e in standings.teams.values()
        if e.conference is Conference.WEST
    ]
    east = [
        e.provider_order
        for e in standings.teams.values()
        if e.conference is Conference.EAST
    ]
    assert max(west) < min(east)
    assert sorted(west + east) == list(range(1, 31))
    assert standings.teams["LAL"].conference_order == 6


@pytest.mark.anyio
async def test_maps_the_standings_before_the_first_game(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("before-first-game.json"))

    team = (await fetch(settings)).teams["OKC"]

    assert (team.wins, team.losses, team.playoff_seed) == (0, 0, 0)
    assert (team.streak, team.games_behind) == ("-", "-")
    assert (team.home, team.road, team.last_ten) == ("0-0", "0-0", "0-0")
    assert team.points_for == 0


@pytest.mark.anyio
async def test_requests_the_configured_url_as_is(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(URL).respond(json=load())

    await fetch(settings)

    assert route.call_count == 1
    assert route.calls.last.request.url == httpx.URL(URL)


@pytest.mark.anyio
async def test_carries_the_season_end_year_of_a_regular_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    standings = await fetch(settings)

    assert standings.season == 2026
    assert standings.fallback is False


@pytest.mark.anyio
async def test_falls_back_to_the_previous_regular_season_from_a_preseason(
    mock: respx.MockRouter, settings: Settings
) -> None:
    first = mock.get(URL).respond(json=load("preseason-2027.json"))
    fallback = mock.get(FALLBACK_URL).respond(json=load())

    standings = await fetch(settings)

    assert standings.season == 2026
    assert standings.fallback is True
    assert standings.teams["OKC"].wins == 64
    assert first.call_count == 1
    assert fallback.call_count == 1


@pytest.mark.anyio
async def test_falls_back_to_the_same_season_from_a_postseason(
    mock: respx.MockRouter, settings: Settings
) -> None:
    first = mock.get(URL).respond(json=with_season_type(load(), 3))
    fallback = mock.get(FALLBACK_URL).respond(json=load())

    standings = await fetch(settings)

    assert (standings.season, standings.teams["OKC"].losses) == (2026, 18)
    assert standings.fallback is True
    assert (first.call_count, fallback.call_count) == (1, 1)


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_fallback_is_not_of_the_regular_season(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("preseason-2027.json"))
    fallback = mock.get(FALLBACK_URL).respond(json=load("preseason-2027.json"))

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.source == "division_standings"
    assert raised.value.reason == "standings are not of the regular season"
    assert fallback.call_count == 1


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_season_type_without_a_fallback(
    mock: respx.MockRouter, settings: Settings
) -> None:
    fallback = mock.get(FALLBACK_URL).respond(json=load())

    error = await fetch_error_of(mock, settings, with_season_type(load(), 4))

    assert error.reason == "standings are not of the regular season"
    assert fallback.call_count == 0


@pytest.mark.anyio
async def test_raises_the_source_error_on_standings_that_mix_seasons(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    division(payload, 1, 2)["standings"]["seasonType"] = 1

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "standings mix seasons"


@pytest.mark.anyio
async def test_raises_the_source_error_on_standings_without_divisions(
    mock: respx.MockRouter, settings: Settings
) -> None:
    error = await fetch_error_of(mock, settings, {"children": []})

    assert error.reason == "standings have no divisions"


@pytest.mark.anyio
@pytest.mark.parametrize("stat", ["streak", "gamesbehind", "playoffseed"])
@pytest.mark.parametrize("form", ["absent", "null", "empty"])
async def test_maps_an_absent_null_or_empty_stat_to_null(
    mock: respx.MockRouter, settings: Settings, stat: str, form: str
) -> None:
    payload = load()
    stats = division(payload)["standings"]["entries"][0]["stats"]
    for item in list(stats):
        if item["type"] != stat:
            continue
        if form == "absent":
            stats.remove(item)
        elif form == "null":
            item["value"] = None
            item["displayValue"] = None
        else:
            item.pop("value", None)
            item["displayValue"] = ""
    mock.get(URL).respond(json=payload)

    teams = (await fetch(settings)).teams

    field = {"gamesbehind": "games_behind", "playoffseed": "playoff_seed"}.get(
        stat, stat
    )
    assert getattr(teams["BOS"], field) is None
    assert getattr(teams["OKC"], field) is not None


@pytest.mark.anyio
async def test_rejects_standings_without_both_conferences(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    del payload["children"][1]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "standings do not have both conferences"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_conference(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["children"][0]["abbreviation"] = "North"

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "unknown conference 'North'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    division(payload)["standings"]["entries"][0]["team"]["abbreviation"] = "XXX"

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "unknown team code 'XXX'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_missing_stat(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    stats = division(payload)["standings"]["entries"][0]["stats"]
    stats[:] = [stat for stat in stats if stat["type"] != "wins"]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "team BOS has no wins stat"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_stat_without_a_value(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    stats = division(payload)["standings"]["entries"][0]["stats"]
    for stat in stats:
        if stat["type"] == "home":
            del stat["displayValue"]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "team BOS has no home stat"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload", [{}, {"children": 3}, {"children": [{"abbreviation": "East"}]}], ids=str
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_empty_team_name(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    division(payload)["standings"]["entries"][0]["team"]["name"] = ""

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("standings are invalid: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("fails", "reason"),
    [
        (
            lambda route: route.mock(side_effect=httpx.ReadTimeout("slow")),
            "request timed out",
        ),
        (lambda route: route.respond(status_code=500), "responded with status 500"),
    ],
    ids=["timeout", "error status"],
)
async def test_raises_the_source_error_on_a_timeout_and_an_error_status(
    mock: respx.MockRouter, settings: Settings, fails: Any, reason: str
) -> None:
    fails(mock.get(URL))

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None, division_standings_url=None)  # type: ignore[call-arg]
    with respx.mock, pytest.raises(SourceError) as raised:
        await fetch(unset)

    assert raised.value.reason == "division standings URL is not configured"


@pytest.mark.anyio
async def test_reuses_the_standings_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_division_standings(client, settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_division_standings(client, settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_division_standings(client, settings)

    assert route.call_count == 2


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_invalid_fallback_payload(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load("preseason-2027.json"))
    mock.get(FALLBACK_URL).respond(json={})

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason.startswith("invalid payload: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("fails", "reason"),
    [
        (
            lambda route: route.mock(side_effect=httpx.ReadTimeout("slow")),
            "request timed out",
        ),
        (lambda route: route.respond(status_code=500), "responded with status 500"),
    ],
    ids=["timeout", "error status"],
)
async def test_raises_the_source_error_when_the_fallback_request_fails(
    mock: respx.MockRouter, settings: Settings, fails: Any, reason: str
) -> None:
    mock.get(URL).respond(json=load("preseason-2027.json"))
    fails(mock.get(FALLBACK_URL))

    with pytest.raises(SourceError) as raised:
        await fetch(settings)

    assert raised.value.reason == reason


@pytest.mark.anyio
async def test_reuses_the_fallback_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 9, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    first = mock.get(URL).respond(json=load("preseason-2027.json"))
    fallback = mock.get(FALLBACK_URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_division_standings(client, settings)
        clock[0] = start + dt.timedelta(minutes=59)
        await fetch_division_standings(client, settings)

    assert (first.call_count, fallback.call_count) == (1, 1)


def add_stats(payload: Payload, *stats: Payload) -> None:
    division(payload)["standings"]["entries"][0]["stats"].extend(stats)


@pytest.mark.anyio
async def test_maps_the_division_and_conference_records_and_the_clinch_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    add_stats(
        payload,
        {"type": "vsdiv", "displayValue": "12-4"},
        {"type": "vsconf", "displayValue": "36-16"},
        {"type": "clincher", "displayValue": "z"},
    )
    mock.get(URL).respond(json=payload)

    team = (await fetch(settings)).teams["BOS"]

    assert (team.vs_division, team.vs_conference) == ("12-4", "36-16")
    assert team.clinch is Clinch.CONFERENCE


@pytest.mark.anyio
async def test_maps_a_missing_division_or_conference_record_to_0_0(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    teams = (await fetch(settings)).teams.values()

    assert {(team.vs_division, team.vs_conference) for team in teams} == {
        ("0-0", "0-0")
    }
    assert {team.clinch for team in teams} == {None}


@pytest.mark.anyio
@pytest.mark.parametrize("form", ["absent", "null", "empty"])
async def test_maps_an_absent_null_or_empty_clincher_to_null(
    mock: respx.MockRouter, settings: Settings, form: str
) -> None:
    payload = load()
    if form == "null":
        add_stats(payload, {"type": "clincher", "displayValue": None})
    elif form == "empty":
        add_stats(payload, {"type": "clincher", "displayValue": ""})
    mock.get(URL).respond(json=payload)

    assert (await fetch(settings)).teams["BOS"].clinch is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("code", "clinch"),
    [
        ("*", Clinch.LEAGUE),
        ("z", Clinch.CONFERENCE),
        ("y", Clinch.DIVISION),
        ("x", Clinch.PLAYOFFS),
        ("xp", Clinch.PLAYIN),
        ("pb", Clinch.PLAYIN_POSITION),
        ("e", Clinch.ELIMINATED),
    ],
)
async def test_maps_every_known_clinch_code(
    mock: respx.MockRouter, settings: Settings, code: str, clinch: Clinch
) -> None:
    payload = load()
    add_stats(payload, {"type": "clincher", "displayValue": code})
    mock.get(URL).respond(json=payload)

    assert (await fetch(settings)).teams["BOS"].clinch is clinch


@pytest.mark.anyio
async def test_maps_an_unknown_clincher_to_null_and_logs_the_team_code(
    mock: respx.MockRouter, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    payload = load()
    add_stats(payload, {"type": "clincher", "displayValue": "q"})
    mock.get(URL).respond(json=payload)

    with caplog.at_level(logging.WARNING):
        team = (await fetch(settings)).teams["BOS"]

    assert team.clinch is None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "BOS" in warnings[0].getMessage()
