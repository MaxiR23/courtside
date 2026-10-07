# api/tests/sources/test_standings.py
#
# Tests for the standings adapter.
#
# Tested:
# - Maps recorded standings of both conferences to rank, record, home, away and last ten
# - Maps the team codes that differ from the standard ones
# - Gives a team with no games and no last ten stat a last ten record of 0-0
# - Requests the standings URL from the settings
# - Raises the source error on an unknown conference, standings without both conferences, a missing record stat, a missing last ten stat of a team that has played, a record that is not wins and losses, an invalid payload, a rank below one, an unknown team code, a timeout, an error status and a missing URL
#
# What is covered:
# - A valid response mapped, an invalid payload rejected, upstream failures handled
#
# The fixture is the recorded standings trimmed to the fields the adapter
# reads: three teams per conference and only the stat types the adapter reads.
# One team, SA, has played no game: as recorded, it has no last ten stat.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_standings.py
#
# SEE: api/app/sources/standings.py

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from app.feeds.game_detail import Conference
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.standings import LeagueStandings, fetch_standings

FIXTURES = Path(__file__).parent / "fixtures" / "standings"
URL = "https://example.com/standings"

Payload = dict[str, Any]


def load() -> Payload:
    payload: Payload = json.loads(
        (FIXTURES / "standings.json").read_text(encoding="utf-8")
    )
    return payload


def entry(payload: Payload, abbreviation: str) -> Payload:
    found: Payload = next(
        e
        for c in payload["children"]
        for e in c["standings"]["entries"]
        if e["team"]["abbreviation"] == abbreviation
    )
    return found


def stat(payload: Payload, abbreviation: str, kind: str) -> Payload:
    found: Payload = next(
        s for s in entry(payload, abbreviation)["stats"] if s["type"] == kind
    )
    return found


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, standings_url=URL)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings) -> LeagueStandings:
    async with create_client() as client:
        return await fetch_standings(client, settings)


async def fetch_error(settings: Settings) -> SourceError:
    with pytest.raises(SourceError) as raised:
        await fetch(settings)
    return raised.value


async def fetch_error_of(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> SourceError:
    mock.get(URL).respond(json=payload)
    return await fetch_error(settings)


@pytest.mark.anyio
async def test_maps_recorded_standings_of_both_conferences(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    standings = await fetch(settings)

    atlanta = standings.teams["ATL"]
    assert atlanta.conference is Conference.EAST
    assert atlanta.conference_rank == 11
    assert (atlanta.record.wins, atlanta.record.losses) == (0, 1)
    assert (atlanta.home_record.wins, atlanta.home_record.losses) == (0, 1)
    assert (atlanta.away_record.wins, atlanta.away_record.losses) == (0, 0)
    assert (atlanta.last_ten.wins, atlanta.last_ten.losses) == (0, 1)
    golden_state = standings.teams["GSW"]
    assert golden_state.conference is Conference.WEST
    assert golden_state.conference_rank == 5
    assert (golden_state.record.wins, golden_state.record.losses) == (1, 1)
    assert (golden_state.home_record.wins, golden_state.home_record.losses) == (1, 0)
    assert (golden_state.away_record.wins, golden_state.away_record.losses) == (0, 0)
    assert (golden_state.last_ten.wins, golden_state.last_ten.losses) == (1, 1)
    assert len(standings.teams) == 7


@pytest.mark.anyio
async def test_maps_the_team_codes_that_differ(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    standings = await fetch(settings)

    assert {"GSW", "NYK", "NOP"} <= set(standings.teams)
    assert not {"GS", "NY", "NO"} & set(standings.teams)


@pytest.mark.anyio
async def test_requests_the_standings_url_from_settings(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(URL).respond(json=load())

    await fetch(settings)

    assert route.call_count == 1


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_conference(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["children"][0]["abbreviation"] = "North"

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "unknown conference 'North'"


@pytest.mark.anyio
async def test_raises_the_source_error_without_both_conferences(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["children"] = payload["children"][:1]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "standings need both conferences"


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["playoffseed", "total", "home", "road"])
async def test_raises_the_source_error_on_a_missing_record_stat(
    mock: respx.MockRouter, settings: Settings, kind: str
) -> None:
    payload = load()
    stats = entry(payload, "ATL")["stats"]
    stats[:] = [s for s in stats if s["type"] != kind]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == f"team ATL has no {kind} stat"


@pytest.mark.anyio
async def test_gives_a_team_without_games_a_last_ten_of_zero_and_zero(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get(URL).respond(json=load())

    san_antonio = (await fetch(settings)).teams["SAS"]

    assert san_antonio.conference is Conference.WEST
    assert san_antonio.conference_rank == 9
    for record in (
        san_antonio.record,
        san_antonio.home_record,
        san_antonio.away_record,
        san_antonio.last_ten,
    ):
        assert (record.wins, record.losses) == (0, 0)


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_missing_last_ten_of_a_team_that_has_played(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    stats = entry(payload, "ATL")["stats"]
    stats[:] = [s for s in stats if s["type"] != "lasttengames"]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "team ATL has no lasttengames stat"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_missing_total_of_a_team_without_last_ten(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    stats = entry(payload, "SA")["stats"]
    stats[:] = [s for s in stats if s["type"] != "total"]

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "team SAS has no total stat"


@pytest.mark.anyio
@pytest.mark.parametrize("value", ["", "7", "a-b", "-1-2", "3-"])
async def test_raises_the_source_error_on_a_record_that_is_not_wins_and_losses(
    mock: respx.MockRouter, settings: Settings, value: str
) -> None:
    payload = load()
    stat(payload, "ATL", "home")["displayValue"] = value

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "team ATL has a record that is not W-L"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload", [{}, {"children": 3}, {"children": [{"abbreviation": "East"}]}]
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("invalid payload: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_rank_below_one(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    stat(payload, "ATL", "playoffseed")["value"] = 0.0

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("standings are invalid: ")


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_code(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    entry(payload, "ATL")["team"]["abbreviation"] = "XXX"

    error = await fetch_error_of(mock, settings, payload)

    assert error.source == "standings"


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

    error = await fetch_error(settings)

    assert error.reason == reason


@pytest.mark.anyio
async def test_raises_the_source_error_when_the_standings_url_is_not_configured() -> (
    None
):
    unset = Settings(_env_file=None, standings_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "standings URL is not configured"
