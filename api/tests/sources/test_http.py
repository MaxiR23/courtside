# api/tests/sources/test_http.py
#
# Tests for the shared HTTP client of the source adapters.
#
# Tested:
# - Returns the decoded JSON body of a successful response
# - Raises the source error on a timeout, a transport failure, an error status and a body that is not JSON
# - Returns the body text of a successful response
# - Raises the source error on a timeout, a transport failure and an error status when reading text
# - Keeps the status code of an error status on the error, and none for the other failures
# - Keeps the request URL out of the error
# - Sends the given query parameters and headers, keeping the query of the URL
# - Keeps header values out of the error
# - Tells with a HEAD request whether a URL is served: yes on success, no on an error status
# - Raises the source error on a timeout and a transport failure when checking a URL, keeping the URL out of it
# - Marks a timeout, a transport failure and an error status as a failed request, for JSON and text
# - Does not mark a body that is not JSON as a failed request
# - Marks a timeout and a transport failure when checking a URL as a failed request
# - A source error is not a failed request by default
# - Creates a client with fixed timeouts
# - Serves a URL asked again inside its maximum age from the cache with one request
# - Fetches an expired URL again and replaces its entry
# - Fetches again an entry older than the fetched-at-or-after time, and serves one at or after it
# - Concurrent callers of one URL share one request and leave no task in flight
# - A caller does not take an in-flight fetch sent before its fetched-at-or-after time
# - A failed fetch stores nothing and keeps an existing entry
# - Serves an entry written before a restart without a request
# - Request headers are neither in the key nor stored
# - Keys an entry by the full URL with its parameters
# - Rejects a naive fetched-at-or-after time
#
# What is covered:
# - Happy path and every upstream failure, with no real network call
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_http.py
#
# SEE: api/app/sources/http.py

import asyncio
import datetime as dt
import sqlite3
from collections.abc import Awaitable, Callable
from contextlib import closing
from pathlib import Path

import httpx
import pytest
import respx

from app.sources.http import (
    TIMEOUT,
    Freshness,
    SourceClient,
    SourceError,
    create_client,
    get_json,
    get_text,
    is_served,
)
from app.storage.state import STATE_FILE, StateStore

URL = "https://example.com/data?key=secret-value"
FRESH = dt.timedelta(hours=1)
T = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)


def make_store(path: Path) -> StateStore:
    store = StateStore(path)
    store.migrate()
    return store


async def read_json(client: httpx.AsyncClient, url: str, *, source: str) -> object:
    assert isinstance(client, SourceClient)
    return await get_json(client, url, source=source, fresh=FRESH)


@pytest.mark.anyio
async def test_returns_the_decoded_json_body(tmp_path: Path) -> None:
    with respx.mock:
        respx.get(URL).respond(json={"games": [1, 2]})
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            body = await get_json(client, URL, source="test", fresh=FRESH)

    assert body == {"games": [1, 2]}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("effect", "reason"),
    [
        (httpx.ReadTimeout("slow"), "request timed out"),
        (httpx.ConnectError("down"), "request failed"),
        (httpx.Response(503), "responded with status 503"),
        (httpx.Response(200, text="<html>"), "response is not JSON"),
    ],
)
async def test_raises_the_source_error_on_an_upstream_failure(
    effect: httpx.Response | Exception, reason: str, tmp_path: Path
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test", fresh=FRESH)

    assert raised.value.source == "test"
    assert raised.value.reason == reason
    assert str(raised.value) == f"test: {reason}"


@pytest.mark.anyio
async def test_returns_the_body_text(tmp_path: Path) -> None:
    with respx.mock:
        respx.get(URL).respond(text="<feed></feed>")
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            body = await get_text(client, URL, source="test")

    assert body == "<feed></feed>"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("effect", "reason"),
    [
        (httpx.ReadTimeout("slow"), "request timed out"),
        (httpx.ConnectError("down"), "request failed"),
        (httpx.Response(503), "responded with status 503"),
    ],
)
async def test_raises_the_source_error_when_reading_text_fails(
    effect: httpx.Response | Exception, reason: str, tmp_path: Path
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await get_text(client, URL, source="test")

    assert raised.value.reason == reason
    assert "secret-value" not in str(raised.value)


@pytest.mark.anyio
@pytest.mark.parametrize("read", [read_json, get_text])
async def test_keeps_the_status_code_of_an_error_status(
    read: Callable[..., Awaitable[object]], tmp_path: Path
) -> None:
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(503))
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await read(client, URL, source="test")

    assert raised.value.status_code == 503


@pytest.mark.anyio
@pytest.mark.parametrize(
    "effect",
    [
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("down"),
        httpx.Response(200, text="<html>"),
    ],
)
async def test_carries_no_status_code_when_no_error_status_came_back(
    effect: httpx.Response | Exception, tmp_path: Path
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test", fresh=FRESH)

    assert raised.value.status_code is None


@pytest.mark.anyio
async def test_does_not_leak_the_url_into_the_error(tmp_path: Path) -> None:
    with respx.mock:
        respx.get(URL).mock(side_effect=httpx.ConnectError(f"failed for {URL}"))
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test", fresh=FRESH)

    assert "secret-value" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__


@pytest.mark.anyio
async def test_creates_a_client_with_fixed_timeouts(tmp_path: Path) -> None:
    async with create_client(make_store(tmp_path), clock=lambda: T) as client:
        assert client.timeout == TIMEOUT


@pytest.mark.anyio
async def test_sends_the_given_query_parameters_and_headers(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    with respx.mock:
        respx.get("https://example.com/list").mock(side_effect=capture)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            await get_json(
                client,
                "https://example.com/list?a=1",
                source="test",
                fresh=FRESH,
                params={"maxResults": 50},
                headers={"X-Test-Key": "secret-value"},
            )

    assert seen[0].url.params["maxResults"] == "50"
    assert seen[0].url.params["a"] == "1"
    assert seen[0].headers["x-test-key"] == "secret-value"


@pytest.mark.anyio
async def test_does_not_leak_header_values_into_the_error(tmp_path: Path) -> None:
    with respx.mock:
        respx.get("https://example.com/list").respond(
            503, headers={"X-Test-Key": "secret-value"}
        )
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await get_json(
                    client,
                    "https://example.com/list",
                    source="test",
                    fresh=FRESH,
                    headers={"X-Test-Key": "secret-value"},
                )

    assert "secret-value" not in str(raised.value)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "served"), [(200, True), (404, False), (503, False)]
)
async def test_tells_with_a_head_request_whether_a_url_is_served(
    status: int, served: bool, tmp_path: Path
) -> None:
    with respx.mock:
        route = respx.head(URL).respond(status)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            assert await is_served(client, URL, source="test") is served

    assert route.call_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("effect", "reason"),
    [
        (httpx.ReadTimeout("slow"), "request timed out"),
        (httpx.ConnectError(f"failed for {URL}"), "request failed"),
    ],
)
async def test_raises_the_source_error_when_checking_a_url_fails(
    effect: Exception, reason: str, tmp_path: Path
) -> None:
    with respx.mock:
        respx.head(URL).mock(side_effect=effect)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await is_served(client, URL, source="test")

    assert raised.value.reason == reason
    assert "secret-value" not in str(raised.value)


@pytest.mark.anyio
@pytest.mark.parametrize("read", [read_json, get_text])
@pytest.mark.parametrize(
    "effect",
    [
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("down"),
        httpx.Response(503),
    ],
)
async def test_marks_a_timeout_a_transport_failure_and_an_error_status_as_a_failed_request(
    read: Callable[..., Awaitable[object]],
    effect: httpx.Response | Exception,
    tmp_path: Path,
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await read(client, URL, source="test")

    assert raised.value.request_failed is True


@pytest.mark.anyio
async def test_does_not_mark_a_body_that_is_not_json_as_a_failed_request(
    tmp_path: Path,
) -> None:
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, text="<html>"))
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test", fresh=FRESH)

    assert raised.value.request_failed is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    "effect", [httpx.ReadTimeout("slow"), httpx.ConnectError("down")]
)
async def test_marks_a_timeout_and_a_transport_failure_when_checking_a_url_as_a_failed_request(
    effect: Exception, tmp_path: Path
) -> None:
    with respx.mock:
        respx.head(URL).mock(side_effect=effect)
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(SourceError) as raised:
                await is_served(client, URL, source="test")

    assert raised.value.request_failed is True


def test_a_source_error_is_not_a_failed_request_by_default() -> None:
    assert SourceError("test", "x").request_failed is False


def clocked(path: Path, clock: list[dt.datetime]) -> SourceClient:
    return create_client(make_store(path), clock=lambda: clock[0])


def rows(path: Path) -> list[tuple[str, str, str]]:
    with closing(sqlite3.connect(path / STATE_FILE)) as connection:
        return [
            (str(a), str(b), str(c))
            for a, b, c in connection.execute(
                "SELECT url, body, fetched_at FROM source_cache"
            )
        ]


@pytest.mark.anyio
async def test_serves_a_url_asked_again_inside_its_maximum_age_from_the_cache_with_one_request(
    tmp_path: Path,
) -> None:
    clock = [T]
    with respx.mock:
        route = respx.get(URL).respond(json={"n": 1})
        async with clocked(tmp_path, clock) as client:
            first = await get_json(client, URL, source="test", fresh=FRESH)
            clock[0] = T + FRESH - dt.timedelta(seconds=1)
            second = await get_json(client, URL, source="test", fresh=FRESH)

    assert route.call_count == 1
    assert first == second == {"n": 1}


@pytest.mark.anyio
async def test_fetches_an_expired_url_again_and_replaces_its_entry(
    tmp_path: Path,
) -> None:
    clock = [T]
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=[
                httpx.Response(200, json={"n": 1}),
                httpx.Response(200, json={"n": 2}),
            ]
        )
        async with clocked(tmp_path, clock) as client:
            await get_json(client, URL, source="test", fresh=FRESH)
            clock[0] = T + FRESH
            second = await get_json(client, URL, source="test", fresh=FRESH)
            entry = client.store.source_entry(URL)

    assert route.call_count == 2
    assert second == {"n": 2}
    assert entry is not None
    assert entry.body == '{"n":2}'
    assert entry.fetched_at == T + FRESH


@pytest.mark.anyio
async def test_fetches_again_an_entry_older_than_its_fetched_at_or_after_time_and_serves_one_at_or_after_it(
    tmp_path: Path,
) -> None:
    clock = [T]
    one = dt.timedelta(seconds=1)
    with respx.mock:
        route = respx.get(URL).respond(json={"n": 1})
        async with clocked(tmp_path, clock) as client:
            await get_json(client, URL, source="test", fresh=FRESH)
            await get_json(client, URL, source="test", fresh=T - one)
            await get_json(client, URL, source="test", fresh=T)
            assert route.call_count == 1
            await get_json(client, URL, source="test", fresh=T + one)

    assert route.call_count == 2


@pytest.mark.anyio
async def test_concurrent_callers_of_one_url_share_one_request_and_leave_no_task_in_flight(
    tmp_path: Path,
) -> None:
    with respx.mock:
        route = respx.get(URL).respond(json={"n": 1})
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            bodies = await asyncio.gather(
                *(get_json(client, URL, source="test", fresh=FRESH) for _ in range(5))
            )
            assert client.in_flight == {}

    assert route.call_count == 1
    assert bodies == [{"n": 1}] * 5


@pytest.mark.anyio
async def test_a_caller_does_not_take_an_in_flight_fetch_sent_before_its_fetched_at_or_after_time(
    tmp_path: Path,
) -> None:
    clock = [T]
    with respx.mock:
        route = respx.get(URL).mock(
            side_effect=[
                httpx.Response(200, json={"n": 1}),
                httpx.Response(200, json={"n": 2}),
            ]
        )
        async with clocked(tmp_path, clock) as client:
            older, newer = await asyncio.gather(
                get_json(client, URL, source="test", fresh=FRESH),
                get_json(
                    client,
                    URL,
                    source="test",
                    fresh=T + dt.timedelta(seconds=1),
                ),
            )
            assert client.in_flight == {}

    assert route.call_count == 2
    assert older == {"n": 1}
    assert newer == {"n": 2}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "effect",
    [
        httpx.ReadTimeout("slow"),
        httpx.Response(503),
        httpx.Response(200, text="<html>"),
    ],
)
@pytest.mark.parametrize("seeded", [False, True])
async def test_a_failed_fetch_stores_nothing_and_keeps_an_existing_entry(
    tmp_path: Path, effect: httpx.Response | Exception, seeded: bool
) -> None:
    clock = [T]
    with respx.mock:
        route = respx.get(URL).respond(json={"n": 1})
        async with clocked(tmp_path, clock) as client:
            if seeded:
                await get_json(client, URL, source="test", fresh=FRESH)
                clock[0] = T + FRESH
            route.mock(
                side_effect=effect if isinstance(effect, Exception) else None,
                return_value=None if isinstance(effect, Exception) else effect,
            )
            with pytest.raises(SourceError):
                await get_json(client, URL, source="test", fresh=FRESH)
            entry = client.store.source_entry(URL)
            assert client.in_flight == {}

    if seeded:
        assert entry is not None
        assert (entry.body, entry.fetched_at) == ('{"n":1}', T)
    else:
        assert entry is None


@pytest.mark.anyio
async def test_serves_an_entry_written_before_a_restart_without_a_request(
    tmp_path: Path,
) -> None:
    with respx.mock:
        route = respx.get(URL).respond(json={"n": 1})
        async with create_client(make_store(tmp_path), clock=lambda: T) as first:
            await get_json(first, URL, source="test", fresh=FRESH)
        async with create_client(StateStore(tmp_path), clock=lambda: T) as second:
            body = await get_json(second, URL, source="test", fresh=FRESH)

    assert body == {"n": 1}
    assert route.call_count == 1


@pytest.mark.anyio
async def test_request_headers_are_neither_in_the_key_nor_stored(
    tmp_path: Path,
) -> None:
    list_url = "https://example.com/list"
    with respx.mock:
        route = respx.get(list_url).respond(json={"n": 1})
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            await get_json(
                client,
                list_url,
                source="test",
                fresh=FRESH,
                params={"maxResults": 50},
                headers={"X-Test-Key": "secret-value"},
            )
            await get_json(
                client,
                list_url,
                source="test",
                fresh=FRESH,
                params={"maxResults": 50},
                headers={"X-Test-Key": "other"},
            )

    assert route.call_count == 1
    stored = rows(tmp_path)
    assert [url for url, _, _ in stored] == [f"{list_url}?maxResults=50"]
    assert "secret-value" not in str(stored)
    assert "other" not in str(stored)


@pytest.mark.anyio
async def test_keys_an_entry_by_the_full_url_with_its_parameters(
    tmp_path: Path,
) -> None:
    base = "https://example.com/list?a=1"
    with respx.mock:
        route = respx.get("https://example.com/list").respond(json={})
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            for token in ("a", "b"):
                await get_json(
                    client,
                    base,
                    source="test",
                    fresh=FRESH,
                    params={"pageToken": token},
                )

    assert route.call_count == 2
    assert sorted(url for url, _, _ in rows(tmp_path)) == [
        f"{base}&pageToken=a",
        f"{base}&pageToken=b",
    ]


@pytest.mark.anyio
async def test_rejects_a_naive_fetched_at_or_after_time(tmp_path: Path) -> None:
    fresh: Freshness = T.replace(tzinfo=None)
    with respx.mock:
        route = respx.get(URL).respond(json={})
        async with create_client(make_store(tmp_path), clock=lambda: T) as client:
            with pytest.raises(ValueError, match="timezone aware"):
                await get_json(client, URL, source="test", fresh=fresh)

    assert route.call_count == 0
