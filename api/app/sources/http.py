# api/app/sources/http.py
#
# Shared HTTP client for the source adapters, and the single error they raise.
# The error reason never carries the request URL: it comes from configuration.
# A timeout, a transport failure or an error status is marked as a failed request.
#
# get_json reads through the shared source cache (rule A).
#
# SEE: docs/architecture.md (Source adapters), docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/source-rules.md, docs/adr/0020-source-rules.md

import asyncio
import datetime as dt
import json
from collections.abc import Callable, Mapping

import httpx

from app.storage.state import StateStore

TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# A maximum age, or a time the fetch must not be older than.
type Freshness = dt.timedelta | dt.datetime


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class SourceError(Exception):
    """A data source failed or sent data the adapter cannot map."""

    def __init__(
        self,
        source: str,
        reason: str,
        *,
        status_code: int | None = None,
        request_failed: bool = False,
    ) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason
        self.status_code = status_code
        self.request_failed = request_failed


class SourceClient(httpx.AsyncClient):
    """The shared client. JSON reads go through the source cache in the state database."""

    def __init__(
        self, store: StateStore, *, clock: Callable[[], dt.datetime] = _utc_now
    ) -> None:
        super().__init__(timeout=TIMEOUT)
        self.store = store
        self.clock = clock
        # One fetch per URL: its send time and its task, removed when done.
        self.in_flight: dict[str, tuple[dt.datetime, asyncio.Task[object]]] = {}


def create_client(
    store: StateStore, *, clock: Callable[[], dt.datetime] = _utc_now
) -> SourceClient:
    """Return a client with fixed timeouts and the source cache.
    The caller owns its lifetime."""
    return SourceClient(store, clock=clock)


async def _get(
    client: httpx.AsyncClient,
    url: str,
    *,
    source: str,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    try:
        response = await client.get(url, headers=headers)
    except httpx.TimeoutException:
        raise SourceError(source, "request timed out", request_failed=True) from None
    except httpx.TransportError:
        raise SourceError(source, "request failed", request_failed=True) from None
    if not response.is_success:
        raise SourceError(
            source,
            f"responded with status {response.status_code}",
            status_code=response.status_code,
            request_failed=True,
        )
    return response


async def is_served(client: httpx.AsyncClient, url: str, *, source: str) -> bool:
    """HEAD a URL: True when it answers with success, False on an error
    status. Raises SourceError on a timeout or a transport failure."""
    try:
        response = await client.head(url)
    except httpx.TimeoutException:
        raise SourceError(source, "request timed out", request_failed=True) from None
    except httpx.TransportError:
        raise SourceError(source, "request failed", request_failed=True) from None
    return response.is_success


async def get_text(client: httpx.AsyncClient, url: str, *, source: str) -> str:
    """GET a URL and return its body as text, or raise SourceError."""
    response = await _get(client, url, source=source)
    return response.text


def _is_fresh(fetched_at: dt.datetime, fresh: Freshness, now: dt.datetime) -> bool:
    if isinstance(fresh, dt.timedelta):
        return now - fetched_at < fresh
    return fetched_at >= fresh


async def _fetch(
    client: SourceClient,
    key: str,
    *,
    source: str,
    headers: Mapping[str, str] | None,
    sent_at: dt.datetime,
) -> object:
    response = await _get(client, key, source=source, headers=headers)
    try:
        body: object = response.json()
    except json.JSONDecodeError:
        raise SourceError(source, "response is not JSON") from None
    client.store.set_source_entry(key, response.text, sent_at)
    return body


def _forget(
    client: SourceClient, key: str, task: asyncio.Task[object]
) -> Callable[[asyncio.Task[object]], None]:
    def done(finished: asyncio.Task[object]) -> None:
        flight = client.in_flight.get(key)
        if flight is not None and flight[1] is task:
            del client.in_flight[key]
        if not finished.cancelled():
            finished.exception()  # consume it: callers that left never retrieve it

    return done


async def get_json(
    client: SourceClient,
    url: str,
    *,
    source: str,
    fresh: Freshness,
    params: Mapping[str, str | int] | None = None,
    headers: Mapping[str, str] | None = None,
) -> object:
    """GET a URL and return its decoded JSON body, or raise SourceError.

    The body comes from the source cache while the entry is fresh: younger than
    `fresh` when it is a maximum age, or fetched at or after `fresh` when it is
    a time. Callers of one URL share a single request."""
    if isinstance(fresh, dt.datetime) and fresh.utcoffset() is None:
        raise ValueError("time must be timezone aware")
    key = str(httpx.URL(url).copy_merge_params(params)) if params else url
    while True:
        entry = client.store.source_entry(key)
        if entry is not None and _is_fresh(entry.fetched_at, fresh, client.clock()):
            return json.loads(entry.body)
        flight = client.in_flight.get(key)
        if flight is not None and isinstance(fresh, dt.datetime) and flight[0] < fresh:
            # Sent before the time this caller needs: wait for it, do not take it.
            await asyncio.wait({flight[1]})
            continue
        if flight is None:
            sent_at = client.clock()
            task = asyncio.create_task(
                _fetch(client, key, source=source, headers=headers, sent_at=sent_at)
            )
            client.in_flight[key] = (sent_at, task)
            task.add_done_callback(_forget(client, key, task))
            flight = (sent_at, task)
        return await asyncio.shield(flight[1])
