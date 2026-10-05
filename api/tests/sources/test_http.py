# api/tests/sources/test_http.py
#
# Tests for the shared HTTP client of the source adapters.
#
# Tested:
# - Returns the decoded JSON body of a successful response
# - Raises the source error on a timeout, a transport failure, an error status and a body that is not JSON
# - Returns the body text of a successful response
# - Raises the source error on a timeout, a transport failure and an error status when reading text
# - Keeps the request URL out of the error
# - Creates a client with fixed timeouts
#
# What is covered:
# - Happy path and every upstream failure, with no real network call
#
# Run with: cd api && .venv/bin/python -m pytest tests/sources/test_http.py
#
# SEE: api/app/sources/http.py

import httpx
import pytest
import respx

from app.sources.http import TIMEOUT, SourceError, create_client, get_json, get_text

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
