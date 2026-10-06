# api/app/sources/http.py
#
# Shared HTTP client for the source adapters, and the single error they raise.
# The error reason never carries the request URL: it comes from configuration.
# A timeout, a transport failure or an error status is marked as a failed request.
#
# SEE: docs/architecture.md (Source adapters), docs/adr/0007-backend-runtime-and-data-pipeline.md

import json
from collections.abc import Mapping

import httpx

TIMEOUT = httpx.Timeout(10.0, connect=5.0)


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


def create_client() -> httpx.AsyncClient:
    """Return a client with fixed timeouts. The caller owns its lifetime."""
    return httpx.AsyncClient(timeout=TIMEOUT)


async def _get(
    client: httpx.AsyncClient,
    url: str,
    *,
    source: str,
    params: Mapping[str, str | int] | None = None,
    headers: Mapping[str, str] | None = None,
) -> httpx.Response:
    try:
        target = httpx.URL(url).copy_merge_params(params) if params else url
        response = await client.get(target, headers=headers)
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


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    source: str,
    params: Mapping[str, str | int] | None = None,
    headers: Mapping[str, str] | None = None,
) -> object:
    """GET a URL and return its decoded JSON body, or raise SourceError."""
    response = await _get(client, url, source=source, params=params, headers=headers)
    try:
        body: object = response.json()
    except json.JSONDecodeError:
        raise SourceError(source, "response is not JSON") from None
    return body
