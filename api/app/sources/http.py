# api/app/sources/http.py
#
# Shared HTTP client for the source adapters, and the single error they raise.
# The error reason never carries the request URL: it comes from configuration.
# A timeout, a transport failure or an error status is marked as a failed request.
#
# A 429 or 503 answer is a rate limit (is_rate_limited, ADR 0056).
#
# The shared client keeps at most MAX_REQUESTS_IN_FLIGHT requests in flight,
# budgeted or not, and pauses every request after a 429 or 503 until its
# Retry-After (ADR 0062). A paused read raises SourcePausedError.
#
# A build can run under a ReadBudget (within_budget, ADR 0058): every request
# that reaches the network counts, at most MAX_PAST_READS_IN_FLIGHT are in
# flight, a request past the limit is refused before it is sent, and a rate
# limit stops the build. cached_json reads the source cache and sends nothing.
#
# A budget can grow while a build runs (ReadBudget.extend) and can give the
# reads made inside wide_reads their own, wider in-flight limit (ADR 0061).
#
# get_json reads through the shared source cache (rule A). with_query adds
# query values to a URL that may already have a query: adapters use it instead
# of passing params.
#
# SEE: docs/architecture.md (Source adapters), docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/source-rules.md, docs/adr/0020-source-rules.md, docs/adr/0056-paced-past-builds-and-one-edition-mvp-path.md, docs/adr/0058-bounded-past-competition-reads.md, docs/adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md, docs/adr/0062-bounded-upstream-reads-and-on-demand-builds.md

import asyncio
import datetime as dt
import email.utils
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar

import httpx

from app.storage.state import StateStore

logger = logging.getLogger(__name__)

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


# Statuses that mean the source is limiting us: 429 (RFC 6585) and 503, a
# temporary overload (RFC 9110, 15.6.4).
RATE_LIMIT_STATUSES = frozenset({429, 503})


SOURCE_PAUSED = "source paused"


class SourcePausedError(SourceError):
    """The client is paused after a rate limit: the read sent no request."""

    def __init__(self, source: str) -> None:
        super().__init__(source, SOURCE_PAUSED, request_failed=True)


def is_rate_limited(error: SourceError) -> bool:
    return (
        isinstance(error, SourcePausedError) or error.status_code in RATE_LIMIT_STATUSES
    )


# Requests the shared client keeps in flight at once (ADR 0062).
MAX_REQUESTS_IN_FLIGHT = 8

# How long a rate limit pauses the client: the default, and the most.
PAUSE_DEFAULT = dt.timedelta(seconds=60)
PAUSE_MAX = dt.timedelta(minutes=15)


# Requests one budgeted build keeps in flight at once (ADR 0058).
MAX_PAST_READS_IN_FLIGHT = 4


class ReadBudget:
    """The reads one build may send. A read is a request that reaches the
    network; a cache hit is not one. Once a read is refused or rate limited,
    every later read of the build is refused too."""

    def __init__(self, limit: int, *, wide_in_flight: int | None = None) -> None:
        self.limit = limit
        self.reads = 0
        self.stopped: SourceError | None = None
        self._semaphore = asyncio.Semaphore(MAX_PAST_READS_IN_FLIGHT)
        self._wide = (
            asyncio.Semaphore(wide_in_flight) if wide_in_flight else self._semaphore
        )

    def extend(self, reads: int) -> None:
        """More reads for the rest of the build; a stopped budget stays stopped."""
        self.limit += reads

    @asynccontextmanager
    async def slot(self, source: str, *, wide: bool = False) -> AsyncIterator[None]:
        async with self._wide if wide else self._semaphore:
            if self.stopped is not None:
                raise self.stopped
            if self.reads >= self.limit:
                self.stopped = SourceError(
                    source, f"read budget of {self.limit} reached"
                )
                raise self.stopped
            self.reads += 1
            try:
                yield
            except SourceError as error:
                if is_rate_limited(error):
                    self.stopped = SourceError(
                        error.source,
                        "rate limited",
                        status_code=error.status_code,
                        request_failed=True,
                    )
                    raise self.stopped from None
                raise


_BUDGET: ContextVar[ReadBudget | None] = ContextVar("read_budget", default=None)
_WIDE: ContextVar[bool] = ContextVar("wide_reads", default=False)


@contextmanager
def wide_reads() -> Iterator[None]:
    """Reads started inside use the budget's wide lane."""
    token = _WIDE.set(True)
    try:
        yield
    finally:
        _WIDE.reset(token)


async def within_budget[T](
    budget: ReadBudget, label: str, build: Callable[[], Awaitable[T]]
) -> T:
    """Run a build under a read budget. A stop the build swallowed is raised
    after it, with its reason logged."""
    token = _BUDGET.set(budget)
    try:
        try:
            result = await build()
        except Exception:
            if budget.stopped is not None:
                logger.warning("%s not built: %s", label, budget.stopped.reason)
                raise budget.stopped from None
            raise
    finally:
        _BUDGET.reset(token)
    if budget.stopped is not None:
        logger.warning("%s not built: %s", label, budget.stopped.reason)
        raise budget.stopped
    return result


class SourceClient(httpx.AsyncClient):
    """The shared client. JSON reads go through the source cache in the state database."""

    def __init__(
        self, store: StateStore, *, clock: Callable[[], dt.datetime] = _utc_now
    ) -> None:
        super().__init__(timeout=TIMEOUT)
        self.store = store
        self.clock = clock
        self.requests = asyncio.Semaphore(MAX_REQUESTS_IN_FLIGHT)
        self.paused_until: dt.datetime | None = None
        # One fetch per URL: its send time and its task, removed when done.
        self.in_flight: dict[str, tuple[dt.datetime, asyncio.Task[object]]] = {}


def create_client(
    store: StateStore, *, clock: Callable[[], dt.datetime] = _utc_now
) -> SourceClient:
    """Return a client with fixed timeouts and the source cache.
    The caller owns its lifetime."""
    return SourceClient(store, clock=clock)


def _pause_length(response: httpx.Response, now: dt.datetime) -> dt.timedelta:
    """The pause a rate-limit answer asks for, from its Retry-After."""
    value = response.headers.get("Retry-After")
    if value is None:
        return PAUSE_DEFAULT
    value = value.strip()
    if value.isascii() and value.isdigit():
        length = dt.timedelta(seconds=min(int(value), int(PAUSE_MAX.total_seconds())))
    else:
        try:
            date = email.utils.parsedate_to_datetime(value)
        except ValueError, TypeError:
            return PAUSE_DEFAULT
        if date.tzinfo is None:
            date = date.replace(tzinfo=dt.UTC)
        length = date - now
    if length < dt.timedelta(0):
        return PAUSE_DEFAULT
    return min(length, PAUSE_MAX)


def _is_paused(client: SourceClient) -> bool:
    return client.paused_until is not None and client.clock() < client.paused_until


def _check_pause(client: SourceClient, source: str) -> None:
    if _is_paused(client):
        raise SourcePausedError(source)


def _note_rate_limit(
    client: SourceClient, source: str, response: httpx.Response
) -> None:
    if response.status_code not in RATE_LIMIT_STATUSES:
        return
    now = client.clock()
    length = _pause_length(response, now)
    if length <= dt.timedelta(0):
        return
    until = now + length
    if client.paused_until is not None and now < client.paused_until:
        client.paused_until = max(client.paused_until, until)
        return
    client.paused_until = until
    logger.warning(
        "%s: source paused for %d seconds", source, int(length.total_seconds())
    )


async def _send(
    client: SourceClient,
    method: str,
    url: str,
    *,
    source: str,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    """Send one request under the client's slots and pause (ADR 0062)."""
    _check_pause(client, source)
    async with client.requests:
        _check_pause(client, source)
        response = await client.request(method, url, headers=headers)
    _note_rate_limit(client, source, response)
    return response


async def _get(
    client: SourceClient,
    url: str,
    *,
    source: str,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    try:
        response = await _send(client, "GET", url, source=source, headers=headers)
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


async def is_served(client: SourceClient, url: str, *, source: str) -> bool:
    """HEAD a URL: True when it answers with success, False on an error
    status. Raises SourceError on a timeout or a transport failure."""
    try:
        response = await _send(client, "HEAD", url, source=source)
    except httpx.TimeoutException:
        raise SourceError(source, "request timed out", request_failed=True) from None
    except httpx.TransportError:
        raise SourceError(source, "request failed", request_failed=True) from None
    return response.is_success


async def get_text(client: SourceClient, url: str, *, source: str) -> str:
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
    budget = _BUDGET.get()
    if budget is None:
        response = await _get(client, key, source=source, headers=headers)
    else:
        async with budget.slot(source, wide=_WIDE.get()):
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


def with_query(url: str, query: Mapping[str, str | int]) -> str:
    """Return the URL with the values added to its own query.

    A value the URL already has is replaced; the rest of its query is kept.
    Adapters use this instead of passing `params`."""
    return str(httpx.URL(url).copy_merge_params(query))


def cached_json(client: SourceClient, url: str) -> object | None:
    """Return the decoded body the source cache holds for a URL, whatever its
    age, or None. It sends no request."""
    entry = client.store.source_entry(url)
    return None if entry is None else json.loads(entry.body)


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
