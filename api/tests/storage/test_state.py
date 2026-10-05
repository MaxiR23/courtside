# api/tests/storage/test_state.py
#
# Tests for the SQLite job state.
#
# Tested:
# - Creates the tables more than once without error
# - Stores a game's final time in UTC
# - Reports no final time and no attempts for an unknown game
# - Counts highlight attempts per game
# - Keeps a job's last success when it fails and its last failure when it succeeds
# - Logs a recorded failure with its reason
# - Rejects a naive time
# - Stores a fallback reason when a failure has an empty reason
# - Rejects an empty job name
# - Keeps job state across store instances over the same data directory
# - Lists job states by name
#
# What is covered:
# - Happy path, edge cases (unknown game, repeat table creation, restart, no jobs), error case (naive time)
#
# Run with: cd api && .venv/bin/python -m pytest tests/storage/test_state.py
#
# SEE: api/app/storage/state.py

import datetime as dt
import logging
from pathlib import Path

import pytest

from app.storage.state import NO_REASON, StateStore

NOON = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 1, 10, 13, 0, tzinfo=dt.UTC)


def make_store(path: Path) -> StateStore:
    store = StateStore(path)
    store.create_tables()
    return store


def test_creates_the_tables_more_than_once_without_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.create_tables()

    assert store.job_states() == []


def test_stores_a_final_time_in_utc(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    plus_two = dt.timezone(dt.timedelta(hours=2))

    store.set_final_time("g1", dt.datetime(2026, 1, 10, 14, 0, tzinfo=plus_two))

    assert store.final_time("g1") == NOON
    assert store.final_time("g1") is not None
    assert store.final_time("g1").utcoffset() == dt.timedelta(0)  # type: ignore[union-attr]


def test_reports_no_final_time_and_no_attempts_for_an_unknown_game(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    assert store.final_time("nope") is None
    assert store.highlight_attempts("nope") == 0


def test_counts_highlight_attempts_per_game(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.record_highlight_attempt("g1") == 1
    assert store.record_highlight_attempt("g1") == 2
    assert store.record_highlight_attempt("g2") == 1
    assert store.highlight_attempts("g1") == 2


def test_keeps_last_success_on_failure_and_last_failure_on_success(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    store.record_success("games", NOON)
    store.record_failure("games", LATER, "source down")
    after_failure = store.job_states()[0]
    store.record_success("games", dt.datetime(2026, 1, 10, 14, 0, tzinfo=dt.UTC))
    after_success = store.job_states()[0]

    assert after_failure.last_success == NOON
    assert after_failure.last_failure == LATER
    assert after_failure.last_failure_reason == "source down"
    assert after_success.last_failure == LATER
    assert after_success.last_success == dt.datetime(2026, 1, 10, 14, 0, tzinfo=dt.UTC)


def test_logs_a_recorded_failure_with_its_reason(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = make_store(tmp_path)

    with caplog.at_level(logging.ERROR):
        store.record_failure("games", NOON, "source down")

    assert "games" in caplog.text
    assert "source down" in caplog.text


def test_rejects_a_naive_time(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    naive = NOON.replace(tzinfo=None)

    with pytest.raises(ValueError):
        store.set_final_time("g1", naive)
    with pytest.raises(ValueError):
        store.record_success("games", naive)
    with pytest.raises(ValueError):
        store.record_failure("games", naive, "x")


def test_keeps_state_across_store_instances_over_the_same_directory(
    tmp_path: Path,
) -> None:
    first = make_store(tmp_path)
    first.set_final_time("g1", NOON)
    first.record_highlight_attempt("g1")
    first.record_failure("games", LATER, "source down")

    second = make_store(tmp_path)

    assert second.final_time("g1") == NOON
    assert second.highlight_attempts("g1") == 1
    assert second.job_states()[0].last_failure_reason == "source down"


def test_lists_job_states_by_name(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_success("stars", NOON)
    store.record_success("games", NOON)

    assert [job.name for job in store.job_states()] == ["games", "stars"]


def test_stores_a_fallback_reason_when_a_failure_has_an_empty_reason(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    store.record_failure("games", NOON, str(TimeoutError()))
    store.record_failure("stars", NOON, "   ")

    assert [job.last_failure_reason for job in store.job_states()] == [
        NO_REASON,
        NO_REASON,
    ]


def test_rejects_an_empty_job_name(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(ValueError):
        store.record_success("", NOON)
    with pytest.raises(ValueError):
        store.record_failure("", NOON, "x")
