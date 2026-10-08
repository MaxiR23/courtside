# api/tests/sources/test_player_draft.py
#
# Tests for the player draft adapter.
#
# Tested:
# - Maps a recorded draft with the drafting team's provider id from its link
# - Returns no draft for an undrafted player
# - Raises the source error on a draft link without a team id, an unknown team id, a pick that is not positive, an invalid payload, a timeout, an error status and a missing URL
# - Requests the URL built from the player id
# - Reuses a draft for one hour
#
# What is covered:
# - A valid response mapped (drafted and undrafted), an invalid payload rejected, upstream failures handled
#
# The fixtures are a recorded drafted player and a recorded undrafted player,
# trimmed to the fields the adapter reads.
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_player_draft.py
#
# SEE: api/app/sources/player_draft.py

import datetime as dt
import json
from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
import pytest
import respx

from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.sources.player_draft import DraftPick, fetch_player_draft
from app.storage.state import StateStore

FIXTURES = Path(__file__).parent / "fixtures" / "player_draft"
TEMPLATE = "https://example.com/athletes/{player_id}"
URL = "https://example.com/athletes/4278073"

Payload = dict[str, Any]


def load(name: str = "drafted.json") -> Payload:
    payload: Payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, player_draft_url=TEMPLATE)  # type: ignore[call-arg]


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock as router:
        yield router


async def fetch(settings: Settings, player_id: str = "4278073") -> DraftPick | None:
    with TemporaryDirectory() as directory:
        store = StateStore(Path(directory))
        store.migrate()
        async with create_client(store) as client:
            return await fetch_player_draft(client, player_id, settings)


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
async def test_maps_a_recorded_draft_with_the_drafting_teams_id_from_its_link(
    mock: respx.MockRouter, settings: Settings
) -> None:
    route = mock.get(URL).respond(json=load())

    pick = await fetch(settings)

    assert route.call_count == 1
    assert pick is not None
    assert (pick.year, pick.round, pick.pick, pick.team_code) == (2018, 1, 11, "CHA")


@pytest.mark.anyio
async def test_returns_no_draft_for_an_undrafted_player(
    mock: respx.MockRouter, settings: Settings
) -> None:
    mock.get("https://example.com/athletes/2991350").respond(
        json=load("undrafted.json")
    )

    assert await fetch(settings, "2991350") is None


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_draft_link_without_a_team_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["draft"]["team"]["$ref"] = "https://example.com/v2/seasons/2018/draft"

    error = await fetch_error_of(mock, settings, payload)

    assert error.source == "player_draft"
    assert error.reason == "draft link has no team id"


@pytest.mark.anyio
async def test_raises_the_source_error_on_an_unknown_team_id(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["draft"]["team"]["$ref"] = "https://example.com/seasons/2018/teams/99?a=1"

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason == "unknown team id '99'"


@pytest.mark.anyio
async def test_raises_the_source_error_on_a_pick_that_is_not_positive(
    mock: respx.MockRouter, settings: Settings
) -> None:
    payload = load()
    payload["draft"]["selection"] = 0

    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("player 4278073 is invalid: ")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [[], {"draft": 3}, {"draft": {"year": 2018}}],
    ids=["not an object", "not a draft", "missing fields"],
)
async def test_raises_the_source_error_on_an_invalid_payload(
    mock: respx.MockRouter, settings: Settings, payload: Any
) -> None:
    error = await fetch_error_of(mock, settings, payload)

    assert error.reason.startswith("invalid payload: ")


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
async def test_raises_the_source_error_when_the_url_is_not_configured() -> None:
    unset = Settings(_env_file=None, player_draft_url=None)  # type: ignore[call-arg]
    with respx.mock:
        error = await fetch_error(unset)

    assert error.reason == "player draft URL is not configured"


@pytest.mark.anyio
async def test_reuses_a_draft_for_one_hour(
    mock: respx.MockRouter, settings: Settings, tmp_path: Path
) -> None:
    start = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
    clock = [start]
    route = mock.get(URL).respond(json=load())
    store = StateStore(tmp_path)
    store.migrate()
    async with create_client(store, clock=lambda: clock[0]) as client:
        await fetch_player_draft(client, "4278073", settings)
        clock[0] = start + dt.timedelta(hours=1) - dt.timedelta(seconds=1)
        await fetch_player_draft(client, "4278073", settings)
        assert route.call_count == 1
        clock[0] = start + dt.timedelta(hours=1)
        await fetch_player_draft(client, "4278073", settings)

    assert route.call_count == 2
