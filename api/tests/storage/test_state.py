# api/tests/storage/test_state.py
#
# Tests for the SQLite job state.
#
# Tested:
# - Creates the tables more than once without error
# - Stores a game's final time in UTC
# - Reports no final time and no attempts for an unknown game
# - Keeps the first final time and never overwrites it, nor its first-seen flag
# - Fills the final time of a game row that has none
# - Counts failed stats attempts per game
# - Counts highlight attempts per game
# - Keeps a job's last success when it fails and its last failure when it succeeds
# - Logs a recorded failure with its reason
# - Rejects a naive time
# - Stores a fallback reason when a failure has an empty reason
# - Rejects an empty job name
# - Keeps job state across store instances over the same data directory
# - Lists job states by name
# - Stores a team's star and replaces it on the next store
# - Reports no stars when none is stored
# - Deletes a team's star
# - Keeps stars across store instances over the same data directory
# - Stores a game's highlight and replaces it on the next store
# - Reports no highlights when none is stored
# - Keeps highlights across store instances over the same data directory
#
# What is covered:
# - Happy path, edge cases (unknown game, repeat table creation, restart, no jobs, no stars), error case (naive time)
#
# Run with: cd api && .venv/bin/python -m pytest tests/storage/test_state.py
#
# SEE: api/app/storage/state.py

import datetime as dt
import logging
from pathlib import Path

import pytest
from pydantic import HttpUrl

from app.feeds.games import Highlight, Star
from app.storage.state import NO_REASON, StateStore

NOON = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 1, 10, 13, 0, tzinfo=dt.UTC)


def make_star(code: str, player_id: str) -> Star:
    return Star(
        player_id=player_id,
        first_name="Ann",
        last_name="Bee",
        team_code=code,
        photo_url=HttpUrl("https://example.com/p.png"),
        short_name="A. Bee",
    )


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
    assert store.failed_stats_attempts("nope") == 0
    assert store.first_seen_final("nope") is False


def test_keeps_the_first_final_time_and_never_overwrites_it(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.set_final_time("g1", NOON)
    store.set_final_time("g1", LATER)

    assert store.final_time("g1") == NOON


def test_stores_whether_the_final_time_was_first_seen(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.set_final_time("g1", NOON)
    store.set_final_time("g2", NOON, first_seen=True)
    store.set_final_time("g2", LATER, first_seen=False)

    assert store.first_seen_final("g1") is False
    assert store.first_seen_final("g2") is True


def test_stores_a_final_time_on_a_game_row_that_has_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_highlight_attempt("g1")

    store.set_final_time("g1", NOON, first_seen=True)

    assert store.final_time("g1") == NOON
    assert store.first_seen_final("g1") is True


def test_counts_failed_stats_attempts_per_game(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.record_failed_stats_attempt("g1") == 1
    assert store.record_failed_stats_attempt("g1") == 2
    assert store.record_failed_stats_attempt("g2") == 1
    assert store.failed_stats_attempts("g1") == 2


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
    first.set_final_time("g1", NOON, first_seen=True)
    first.record_highlight_attempt("g1")
    first.record_failed_stats_attempt("g1")
    first.record_failure("games", LATER, "source down")

    second = make_store(tmp_path)

    assert second.final_time("g1") == NOON
    assert second.highlight_attempts("g1") == 1
    assert second.failed_stats_attempts("g1") == 1
    assert second.first_seen_final("g1") is True
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


def test_stores_a_team_star_and_replaces_it_on_the_next_store(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.set_star(make_star("BOS", "1"))
    store.set_star(make_star("NYK", "2"))
    store.set_star(make_star("BOS", "3"))

    stars = store.stars()
    assert set(stars) == {"BOS", "NYK"}
    assert stars["BOS"] == make_star("BOS", "3")
    assert stars["NYK"] == make_star("NYK", "2")


def test_reports_no_stars_when_none_is_stored(tmp_path: Path) -> None:
    assert make_store(tmp_path).stars() == {}


def test_deletes_a_team_star(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.set_star(make_star("BOS", "1"))
    store.set_star(make_star("NYK", "2"))

    store.delete_star("BOS")
    store.delete_star("LAL")

    assert set(store.stars()) == {"NYK"}


def test_keeps_stars_across_store_instances_over_the_same_directory(
    tmp_path: Path,
) -> None:
    make_store(tmp_path).set_star(make_star("BOS", "1"))

    assert make_store(tmp_path).stars() == {"BOS": make_star("BOS", "1")}


def make_highlight(title: str) -> Highlight:
    return Highlight(
        title=title,
        channel="Channel",
        thumbnail_url=HttpUrl("https://example.com/t.jpg"),
        embed_url=HttpUrl("https://example.com/e"),
    )


def test_stores_a_game_highlight_and_replaces_it_on_the_next_store(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    store.set_highlight("g1", make_highlight("one"))
    store.set_highlight("g2", make_highlight("two"))
    store.set_highlight("g1", make_highlight("three"))

    assert store.highlights() == {
        "g1": make_highlight("three"),
        "g2": make_highlight("two"),
    }


def test_reports_no_highlights_when_none_is_stored(tmp_path: Path) -> None:
    assert make_store(tmp_path).highlights() == {}


def test_keeps_highlights_across_store_instances_over_the_same_directory(
    tmp_path: Path,
) -> None:
    make_store(tmp_path).set_highlight("g1", make_highlight("one"))

    assert make_store(tmp_path).highlights() == {"g1": make_highlight("one")}
