# api/tests/jobs/test_presence.py
#
# Tests for the presence of feed requests (rule B).
#
# Tested:
# - Nobody is present before any request
# - Someone is present under five minutes after the last request
# - Nobody is present five minutes after the last request
# - A new request extends the presence
#
# What is covered:
# - Pure logic: happy path, edge cases
#
# The clock is injected, so no test uses the real clock.
#
# Run with: cd api && .venv/bin/python -m pytest tests/jobs/test_presence.py
#
# SEE: api/app/jobs/presence.py

import datetime as dt

from app.jobs.presence import PRESENT_FOR, Presence

T = dt.datetime(2026, 10, 5, 16, 0, tzinfo=dt.UTC)


def test_nobody_is_present_before_any_request() -> None:
    assert not Presence(clock=lambda: T).present(T)


def test_someone_is_present_under_five_minutes_after_the_last_request() -> None:
    presence = Presence(clock=lambda: T)
    presence.seen()

    assert presence.present(T)
    assert presence.present(T + dt.timedelta(minutes=4, seconds=59))


def test_nobody_is_present_five_minutes_after_the_last_request() -> None:
    presence = Presence(clock=lambda: T)
    presence.seen()

    assert PRESENT_FOR == dt.timedelta(minutes=5)
    assert not presence.present(T + dt.timedelta(minutes=5))
    assert not presence.present(T + dt.timedelta(hours=1))


def test_a_new_request_extends_the_presence() -> None:
    now = [T]
    presence = Presence(clock=lambda: now[0])
    presence.seen()
    now[0] = T + dt.timedelta(minutes=4)
    presence.seen()

    assert presence.present(T + dt.timedelta(minutes=8))
    assert not presence.present(T + dt.timedelta(minutes=9))
