# api/tests/test_rate_limit.py
#
# Tests for the per-visitor rate limit.
#
# Tested:
# - Refuses request 121 within a minute with the seconds left
# - Does not let a refused visitor affect another
# - Resets the window a minute after its first request, Retry-After at least 1
# - A limit of 0 allows everything and tracks nothing
# - Holds the tracked visitor cap and drops expired windows
# - Keys a visitor on x-real-ip (first address), else the client address
# - Answers 429 with Retry-After and a JSON detail on the feed routes
# - Never limits /health, a limit of 0 never answers 429
# - A refused request records no presence; no log line holds an address
#
# What is covered:
# - Happy path, other key, window reset, Retry-After floor, limit 0, cap
#   eviction, expired drop, listed and empty x-real-ip, refusal, /health,
#   presence order, log content
#
# Run with: cd api && .venv/bin/python -m pytest tests/test_rate_limit.py
#
# SEE: api/app/rate_limit.py

import datetime as dt
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.jobs.presence import Presence
from app.main import create_app
from app.rate_limit import RateLimiter, visitor_key
from app.settings import Settings

START = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
A = "192.0.2.1"
B = "198.51.100.7"
C = "203.0.113.9"
FEED = "/feeds/teams/xyz.json"


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> dt.datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + dt.timedelta(seconds=seconds)


def limiter(limit: int, clock: Clock, **kwargs: int) -> RateLimiter:
    return RateLimiter(limit, clock=clock, **kwargs)


def test_refuses_request_121_within_a_minute_with_the_seconds_left() -> None:
    clock = Clock()
    rate = limiter(120, clock)

    assert all(rate.hit(A) is None for _ in range(120))
    clock.advance(15)

    assert rate.hit(A) == 45


def test_another_key_is_not_affected_by_a_refused_one() -> None:
    rate = limiter(1, Clock())
    rate.hit(A)

    assert rate.hit(A) is not None
    assert rate.hit(B) is None


def test_the_window_resets_a_minute_after_its_first_request() -> None:
    clock = Clock()
    rate = limiter(120, clock)
    for _ in range(120):
        rate.hit(A)
    clock.advance(59)
    assert rate.hit(A) == 1

    clock.advance(1)

    assert all(rate.hit(A) is None for _ in range(120))
    assert rate.hit(A) is not None


def test_retry_after_is_at_least_one_second() -> None:
    clock = Clock()
    rate = limiter(1, clock)
    rate.hit(A)
    clock.advance(59.5)

    assert rate.hit(A) == 1


def test_a_limit_of_zero_allows_every_request_and_tracks_nothing() -> None:
    rate = limiter(0, Clock())

    assert all(rate.hit(A) is None for _ in range(1000))
    assert len(rate) == 0


def test_the_tracked_visitor_cap_holds_by_dropping_the_oldest_window() -> None:
    clock = Clock()
    rate = limiter(1, clock, max_visitors=3)
    keys = [f"192.0.2.{n}" for n in range(1, 6)]
    rate.hit(keys[0])
    assert rate.hit(keys[0]) is not None
    for key in keys[1:]:
        clock.advance(1)
        rate.hit(key)

    assert len(rate) == 3
    assert rate.hit(keys[0]) is None


def test_expired_windows_are_dropped() -> None:
    clock = Clock()
    rate = limiter(5, clock)
    rate.hit(A)
    clock.advance(61)
    rate.hit(B)

    assert len(rate) == 1


def request(headers: list[tuple[bytes, bytes]], client: bool = True) -> Request:
    scope = {
        "type": "http",
        "headers": headers,
        "client": (A, 50000) if client else None,
    }
    return Request(scope)


def test_the_key_is_x_real_ip_over_the_client_address() -> None:
    assert visitor_key(request([(b"x-real-ip", C.encode())])) == C


def test_the_key_is_the_first_address_of_a_listed_x_real_ip() -> None:
    listed = f"{C}, {B}".encode()

    assert visitor_key(request([(b"x-real-ip", listed)])) == C


def test_the_key_is_the_client_address_without_x_real_ip_or_with_an_empty_one() -> None:
    assert visitor_key(request([])) == A
    assert visitor_key(request([(b"x-real-ip", b"  ")])) == A
    assert visitor_key(request([], client=False)) == ""


def make_client(path: Path, limit: int = 120) -> TestClient:
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, data_dir=path, rate_limit_per_minute=limit
    )
    return TestClient(create_app(settings, run_jobs=False))


def visitor(address: str) -> dict[str, str]:
    return {"x-real-ip": address}


def test_feed_request_121_within_a_minute_answers_429_with_retry_after(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        for _ in range(120):
            assert client.get(FEED, headers=visitor(C)).status_code != 429
        response = client.get(FEED, headers=visitor(C))

    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert response.json() == {"detail": "too many requests"}


def test_a_refused_visitor_does_not_affect_another(tmp_path: Path) -> None:
    with make_client(tmp_path, 1) as client:
        client.get(FEED, headers=visitor(C))
        assert client.get(FEED, headers=visitor(C)).status_code == 429

        assert client.get(FEED, headers=visitor(B)).status_code != 429


def test_the_window_resets_on_the_feed_routes(tmp_path: Path) -> None:
    clock = Clock()
    with make_client(tmp_path, 1) as client:
        client.app.state.rate_limiter = RateLimiter(1, clock=clock)  # type: ignore[attr-defined]
        client.get(FEED, headers=visitor(C))
        assert client.get(FEED, headers=visitor(C)).status_code == 429

        clock.advance(60)

        assert client.get(FEED, headers=visitor(C)).status_code != 429


def test_health_is_never_limited(tmp_path: Path) -> None:
    with make_client(tmp_path, 1) as client:
        client.get(FEED, headers=visitor(C))
        assert client.get(FEED, headers=visitor(C)).status_code == 429

        for _ in range(5):
            assert client.get("/health", headers=visitor(C)).status_code == 200


def test_x_real_ip_wins_over_the_client_address(tmp_path: Path) -> None:
    with make_client(tmp_path, 1) as client:
        assert client.get(FEED, headers=visitor(C)).status_code != 429
        assert client.get(FEED).status_code != 429
        assert client.get(FEED, headers=visitor(C)).status_code == 429


def test_a_limit_of_zero_never_answers_429(tmp_path: Path) -> None:
    with make_client(tmp_path, 0) as client:
        for _ in range(200):
            assert client.get(FEED, headers=visitor(C)).status_code != 429


def test_a_refused_request_does_not_record_presence(tmp_path: Path) -> None:
    clock = Clock()
    with make_client(tmp_path, 1) as client:
        client.get(FEED, headers=visitor(C))
        client.app.state.presence = Presence(clock=clock)  # type: ignore[attr-defined]

        assert client.get(FEED, headers=visitor(C)).status_code == 429

        assert not client.app.state.presence.present(clock())  # type: ignore[attr-defined]


def test_no_log_line_contains_the_visitor_address(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG), make_client(tmp_path, 1) as client:
        client.get(FEED, headers=visitor(C))
        client.get(FEED, headers=visitor(C))
        client.get(FEED)
        client.get(FEED)

    assert C not in caplog.text
    assert "testclient" not in caplog.text
