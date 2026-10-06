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
#
# What is covered:
# - Happy path and every upstream failure, with no real network call
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_http.py
#
# SEE: api/app/sources/http.py

from collections.abc import Awaitable, Callable

import httpx
import pytest
import respx

from app.sources.http import (
    TIMEOUT,
    SourceError,
    create_client,
    get_json,
    get_text,
    is_served,
)

URL = "https://example.com/data?key=secret-value"


@pytest.mark.anyio
async def test_returns_the_decoded_json_body() -> None:
    with respx.mock:
        respx.get(URL).respond(json={"games": [1, 2]})
        async with create_client() as client:
            body = await get_json(client, URL, source="test")

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
    effect: httpx.Response | Exception, reason: str
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test")

    assert raised.value.source == "test"
    assert raised.value.reason == reason
    assert str(raised.value) == f"test: {reason}"


@pytest.mark.anyio
async def test_returns_the_body_text() -> None:
    with respx.mock:
        respx.get(URL).respond(text="<feed></feed>")
        async with create_client() as client:
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
    effect: httpx.Response | Exception, reason: str
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await get_text(client, URL, source="test")

    assert raised.value.reason == reason
    assert "secret-value" not in str(raised.value)


@pytest.mark.anyio
@pytest.mark.parametrize("read", [get_json, get_text])
async def test_keeps_the_status_code_of_an_error_status(
    read: Callable[..., Awaitable[object]],
) -> None:
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(503))
        async with create_client() as client:
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
    effect: httpx.Response | Exception,
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test")

    assert raised.value.status_code is None


@pytest.mark.anyio
async def test_does_not_leak_the_url_into_the_error() -> None:
    with respx.mock:
        respx.get(URL).mock(side_effect=httpx.ConnectError(f"failed for {URL}"))
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test")

    assert "secret-value" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__


@pytest.mark.anyio
async def test_creates_a_client_with_fixed_timeouts() -> None:
    async with create_client() as client:
        assert client.timeout == TIMEOUT


@pytest.mark.anyio
async def test_sends_the_given_query_parameters_and_headers() -> None:
    seen: list[httpx.Request] = []

    def capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    with respx.mock:
        respx.get("https://example.com/list").mock(side_effect=capture)
        async with create_client() as client:
            await get_json(
                client,
                "https://example.com/list?a=1",
                source="test",
                params={"maxResults": 50},
                headers={"X-Test-Key": "secret-value"},
            )

    assert seen[0].url.params["maxResults"] == "50"
    assert seen[0].url.params["a"] == "1"
    assert seen[0].headers["x-test-key"] == "secret-value"


@pytest.mark.anyio
async def test_does_not_leak_header_values_into_the_error() -> None:
    with respx.mock:
        respx.get("https://example.com/list").respond(
            503, headers={"X-Test-Key": "secret-value"}
        )
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await get_json(
                    client,
                    "https://example.com/list",
                    source="test",
                    headers={"X-Test-Key": "secret-value"},
                )

    assert "secret-value" not in str(raised.value)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "served"), [(200, True), (404, False), (503, False)]
)
async def test_tells_with_a_head_request_whether_a_url_is_served(
    status: int, served: bool
) -> None:
    with respx.mock:
        route = respx.head(URL).respond(status)
        async with create_client() as client:
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
    effect: Exception, reason: str
) -> None:
    with respx.mock:
        respx.head(URL).mock(side_effect=effect)
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await is_served(client, URL, source="test")

    assert raised.value.reason == reason
    assert "secret-value" not in str(raised.value)


@pytest.mark.anyio
@pytest.mark.parametrize("read", [get_json, get_text])
@pytest.mark.parametrize(
    "effect",
    [
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("down"),
        httpx.Response(503),
    ],
)
async def test_marks_a_timeout_a_transport_failure_and_an_error_status_as_a_failed_request(
    read: Callable[..., Awaitable[object]], effect: httpx.Response | Exception
) -> None:
    with respx.mock:
        route = respx.get(URL)
        if isinstance(effect, Exception):
            route.mock(side_effect=effect)
        else:
            route.mock(return_value=effect)
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await read(client, URL, source="test")

    assert raised.value.request_failed is True


@pytest.mark.anyio
async def test_does_not_mark_a_body_that_is_not_json_as_a_failed_request() -> None:
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, text="<html>"))
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await get_json(client, URL, source="test")

    assert raised.value.request_failed is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    "effect", [httpx.ReadTimeout("slow"), httpx.ConnectError("down")]
)
async def test_marks_a_timeout_and_a_transport_failure_when_checking_a_url_as_a_failed_request(
    effect: Exception,
) -> None:
    with respx.mock:
        respx.head(URL).mock(side_effect=effect)
        async with create_client() as client:
            with pytest.raises(SourceError) as raised:
                await is_served(client, URL, source="test")

    assert raised.value.request_failed is True


def test_a_source_error_is_not_a_failed_request_by_default() -> None:
    assert SourceError("test", "x").request_failed is False
