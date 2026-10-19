# api/tests/jobs/test_player_identities.py
#
# Tests for the shared player identity reader.
#
# Tested:
# - A player is resolved with one athlete read and stored with its read time
# - A second resolve within 30 days reads nothing, and a row older than 30 days is read again
# - A read that fails (404, timeout, 500, invalid payload) gives none and is not stored, and is read again on the next resolve
# - A rate limit (429, 503) is raised
# - At most eight reads are in flight
# - A stored row that is not a valid identity is read again
# - A stored hit touches the identity, and an expired or invalid stored row is not touched by the check (ADR 0063)
# - A repeated id is read once, and the result keeps the first-seen order
#
# What is covered:
# - Success, every failure and the cache rules; no fallback source exists
#
# The real athlete adapter runs over respx with a recorded-shape fixture and an
# example-domain template; no real network call and no real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_player_identities.py
#
# SEE: api/app/jobs/player_identities.py

import asyncio
import datetime as dt
import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import httpx
import pytest
import respx

from app.jobs.player_identities import (
    IDENTITY_LIFETIME,
    IDENTITY_READS_IN_FLIGHT,
    PlayerIdentities,
)
from app.settings import Settings
from app.sources.http import SourceError, create_client
from app.storage.state import STATE_FILE, StateStore

FIXTURE = (
    Path(__file__).parents[1]
    / "sources"
    / "fixtures"
    / "player_draft"
    / "athlete-2005.json"
)
TEMPLATE = "https://example.com/athletes/{player_id}"
START = dt.datetime(2027, 4, 20, 15, 0, tzinfo=dt.UTC)


def athlete_url(player_id: str) -> str:
    return TEMPLATE.format(player_id=player_id)


class Kit:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.clock = [START]
        self.store = StateStore(path)
        self.store.migrate()
        self.client = create_client(self.store, clock=lambda: self.clock[0])
        self.identities = PlayerIdentities(
            Settings(_env_file=None, player_draft_url=TEMPLATE),  # type: ignore[call-arg]
            self.store,
            self.client,
        )
        self.body = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def answer(self, player_id: str) -> respx.Route:
        return respx.get(athlete_url(player_id)).respond(json=self.body)


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    with respx.mock:
        yield


@pytest.fixture
def kit(tmp_path: Path) -> Kit:
    return Kit(tmp_path)


@pytest.mark.anyio
async def test_resolves_a_player_with_one_athlete_read_and_stores_it(kit: Kit) -> None:
    route = kit.answer("11")

    found = await kit.identities.resolve(["11"])

    assert route.call_count == 1
    athlete = found["11"]
    assert athlete is not None and athlete.entry.display_name == "Cy Veteran"
    stored = kit.store.player_identity("11")
    assert stored is not None and stored.read_at == START


@pytest.mark.anyio
async def test_a_second_resolve_within_30_days_reads_nothing(kit: Kit) -> None:
    route = kit.answer("11")
    first = await kit.identities.resolve(["11"])
    kit.clock[0] = START + IDENTITY_LIFETIME - dt.timedelta(seconds=1)

    second = await kit.identities.resolve(["11"])

    assert route.call_count == 1
    assert second == first


@pytest.mark.anyio
async def test_a_row_older_than_30_days_is_read_again(kit: Kit) -> None:
    route = kit.answer("11")
    await kit.identities.resolve(["11"])
    kit.clock[0] = START + IDENTITY_LIFETIME

    await kit.identities.resolve(["11"])

    assert route.call_count == 2
    stored = kit.store.player_identity("11")
    assert stored is not None and stored.read_at == START + IDENTITY_LIFETIME


def failures() -> list[httpx.Response | Exception]:
    return [
        httpx.Response(404),
        httpx.ReadTimeout("slow"),
        httpx.Response(500),
        httpx.Response(200, json={"active": "maybe"}),
    ]


@pytest.mark.anyio
@pytest.mark.parametrize("effect", failures(), ids=["404", "timeout", "500", "invalid"])
async def test_a_failed_read_gives_none_and_is_not_stored(
    kit: Kit, effect: httpx.Response | Exception
) -> None:
    respx.get(athlete_url("11")).mock(side_effect=[effect])
    kit.answer("12")

    found = await kit.identities.resolve(["11", "12"])

    assert found["11"] is None and found["12"] is not None
    assert kit.store.player_identity("11") is None
    assert kit.store.player_identity("12") is not None


@pytest.mark.anyio
async def test_a_failed_read_is_read_again_on_the_next_resolve(kit: Kit) -> None:
    route = respx.get(athlete_url("11")).mock(
        side_effect=[httpx.Response(404), httpx.Response(200, json=kit.body)]
    )

    first = await kit.identities.resolve(["11"])
    kit.clock[0] = START + dt.timedelta(hours=2)
    second = await kit.identities.resolve(["11"])

    assert first["11"] is None and second["11"] is not None
    assert route.call_count == 2


@pytest.mark.anyio
@pytest.mark.parametrize("status", [429, 503])
async def test_a_rate_limit_is_raised(kit: Kit, status: int) -> None:
    respx.get(athlete_url("11")).respond(status)

    with pytest.raises(SourceError) as raised:
        await kit.identities.resolve(["11"])

    assert raised.value.status_code == status
    assert kit.store.player_identity("11") is None


@pytest.mark.anyio
async def test_at_most_eight_reads_are_in_flight(kit: Kit) -> None:
    running = 0
    peak = 0
    gate = asyncio.Event()

    async def answer(request: httpx.Request) -> httpx.Response:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await gate.wait()
        running -= 1
        return httpx.Response(200, json=kit.body)

    async def release() -> None:
        for _ in range(100):
            await asyncio.sleep(0)
        gate.set()

    respx.get(url__startswith="https://example.com/athletes/").mock(side_effect=answer)
    releasing = asyncio.create_task(release())

    found = await kit.identities.resolve([str(n) for n in range(20)])
    await releasing

    assert peak == IDENTITY_READS_IN_FLIGHT == 8
    assert len(found) == 20 and all(found.values())


@pytest.mark.anyio
async def test_an_invalid_stored_row_is_read_again(kit: Kit) -> None:
    kit.store.set_player_identity("11", '{"active": "maybe"}', START)
    route = kit.answer("11")

    found = await kit.identities.resolve(["11"])

    assert route.call_count == 1 and found["11"] is not None
    stored = kit.store.player_identity("11")
    assert stored is not None and "Cy Veteran" in stored.body


@pytest.mark.anyio
async def test_repeated_ids_are_read_once(kit: Kit) -> None:
    first = kit.answer("11")
    second = kit.answer("12")

    found = await kit.identities.resolve(["12", "11", "12", "11"])

    assert (first.call_count, second.call_count) == (1, 1)
    assert list(found) == ["12", "11"]


def touched_at(kit: Kit, player_id: str) -> str:
    with closing(sqlite3.connect(kit.path / STATE_FILE)) as connection:
        row = connection.execute(
            "SELECT touched_at FROM player_identities WHERE player_id = ?",
            (player_id,),
        ).fetchone()
    return str(row[0])


@pytest.mark.anyio
async def test_a_stored_hit_touches_the_identity_and_a_miss_does_not(kit: Kit) -> None:
    kit.answer("11")
    await kit.identities.resolve(["11"])
    assert touched_at(kit, "11") == START.isoformat()
    hit = START + dt.timedelta(days=2)
    kit.clock[0] = hit

    await kit.identities.resolve(["11"])

    assert touched_at(kit, "11") == hit.isoformat()
    kit.store.set_player_identity("12", '{"active": "maybe"}', START)
    kit.clock[0] = START + dt.timedelta(days=3)
    respx.get(athlete_url("12")).mock(return_value=httpx.Response(404))

    found = await kit.identities.resolve(["12"])

    assert found["12"] is None
    assert touched_at(kit, "12") == START.isoformat()
