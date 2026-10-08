# api/tests/storage/test_state.py
#
# Tests for the SQLite job state.
#
# Tested:
# - Migrates a new database to the latest version
# - Brings a database created before migrations to the latest version and keeps its rows
# - Migrating twice runs nothing the second time
# - Runs each migration once across restarts
# - Runs only the pending migrations, in order
# - A failed migration leaves the database unchanged
# - A failed first migration leaves a new database empty
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
# - Stores the game date on the first write of each writer and keeps it on later writes
# - Reports no game date for an unknown game
# - Prunes the final time, first-seen flag and stats attempts of games before the cutoff, and keeps the cutoff day
# - Pruning never deletes highlights, highlight attempts or the game date, and does nothing on an empty table
# - Setting a star twice, and recording a job success or failure twice, leaves one row
# - Migrates a database at the previous version with its rows to the source cache version
# - Stores a source entry and replaces it on the next store
# - Reports no source entry for an unknown URL
# - Keeps source entries across store instances over the same data directory
# - Rejects a naive fetch time
# - Migrates a database at the previous version with its rows to the feed builds version
# - Records a feed's build time in UTC and replaces it on the next build
# - Keeps a feed's last build when its build fails and its last failure when it builds
# - Logs a recorded build failure with its kind, id and reason
# - Stores the fallback reason for a build failure with an empty reason
# - Rejects a naive build time and a naive failure time
# - Reports no build state for an unknown feed
# - Lists only feeds with a recorded failure, ordered by kind and id
# - Lists the stored ids of one kind only
# - Deletes a feed's build state and leaves the other kinds' rows alone
# - Keeps feed build state across store instances over the same data directory
# - Recording a build twice leaves one row
#
# What is covered:
# - Happy path, edge cases (unknown game, repeat migration, restart, no jobs, no stars, pre-migration database), error case (naive time, failed migration)
#
# Run with: cd api && .venv/bin/python -m pytest tests/storage/test_state.py
#
# SEE: api/app/storage/state.py

import datetime as dt
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from pydantic import HttpUrl

from app.feeds.games import Highlight, Star
from app.storage import state
from app.storage.state import (
    MIGRATIONS,
    NO_REASON,
    STATE_FILE,
    StateMigrationError,
    StateStore,
)

NOON = dt.datetime(2026, 1, 10, 12, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 1, 10, 13, 0, tzinfo=dt.UTC)
DAY = dt.date(2026, 1, 9)

LEGACY_SCHEMA = (
    (
        "CREATE TABLE IF NOT EXISTS games ("
        "game_id TEXT PRIMARY KEY, game_date TEXT NOT NULL, final_time TEXT, "
        "highlight_attempts INTEGER NOT NULL DEFAULT 0, "
        "first_seen_final INTEGER NOT NULL DEFAULT 0, "
        "failed_stats_attempts INTEGER NOT NULL DEFAULT 0)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS stars (team_code TEXT PRIMARY KEY, star TEXT NOT NULL)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS highlights ("
        "game_id TEXT PRIMARY KEY, highlight TEXT NOT NULL)"
    ),
    (
        "CREATE TABLE IF NOT EXISTS jobs ("
        "name TEXT PRIMARY KEY, last_success TEXT, "
        "last_failure TEXT, last_failure_reason TEXT)"
    ),
)


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
    store.migrate()
    return store


def user_version(path: Path) -> int:
    with closing(sqlite3.connect(path / STATE_FILE)) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def query(path: Path, sql: str) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path / STATE_FILE)) as connection:
        return connection.execute(sql).fetchall()


def table_names(path: Path) -> set[str]:
    return {str(row[0]) for row in query(path, "SELECT name FROM sqlite_master")}


def test_migrates_a_new_database_to_the_latest_version(tmp_path: Path) -> None:
    make_store(tmp_path)

    assert user_version(tmp_path) == len(MIGRATIONS)
    assert {
        "games",
        "highlights",
        "jobs",
        "source_cache",
        "stars",
        "feed_builds",
    } <= table_names(tmp_path)


def test_brings_a_database_created_before_migrations_to_the_latest_version_and_keeps_its_rows(
    tmp_path: Path,
) -> None:
    star = make_star("AAA", "p1")
    highlight = Highlight(
        title="Recap",
        channel="NBA",
        thumbnail_url=HttpUrl("https://example.com/t.png"),
        embed_url=HttpUrl("https://example.com/e"),
    )
    with closing(sqlite3.connect(tmp_path / STATE_FILE)) as connection, connection:
        for statement in LEGACY_SCHEMA:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO games (game_id, game_date, final_time) VALUES (?, ?, ?)",
            ("g1", DAY.isoformat(), NOON.isoformat()),
        )
        connection.execute(
            "INSERT INTO stars (team_code, star) VALUES (?, ?)",
            ("AAA", star.model_dump_json()),
        )
        connection.execute(
            "INSERT INTO highlights (game_id, highlight) VALUES (?, ?)",
            ("g1", highlight.model_dump_json()),
        )
        connection.execute(
            "INSERT INTO jobs (name, last_success) VALUES (?, ?)",
            ("games", NOON.isoformat()),
        )
    assert user_version(tmp_path) == 0

    store = StateStore(tmp_path)
    store.migrate()

    assert user_version(tmp_path) == len(MIGRATIONS)
    assert store.final_time("g1") == NOON
    assert store.game_date("g1") == DAY
    assert store.stars() == {"AAA": star}
    assert store.highlights() == {"g1": highlight}
    assert [(j.name, j.last_success) for j in store.job_states()] == [("games", NOON)]


def test_migrating_twice_runs_nothing_the_second_time(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.migrate()

    assert store.job_states() == []
    assert user_version(tmp_path) == len(MIGRATIONS)


def test_runs_each_migration_once_across_restarts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrations = (
        *MIGRATIONS,
        ("CREATE TABLE counter (n INTEGER)",),
        ("INSERT INTO counter VALUES (1)",),
    )
    monkeypatch.setattr(state, "MIGRATIONS", migrations)

    StateStore(tmp_path).migrate()
    StateStore(tmp_path).migrate()

    assert query(tmp_path, "SELECT COUNT(*) FROM counter") == [(1,)]
    assert user_version(tmp_path) == len(migrations)


def test_runs_only_the_pending_migrations_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_store(tmp_path)
    store.record_success("games", NOON)
    monkeypatch.setattr(
        state,
        "MIGRATIONS",
        (
            *MIGRATIONS,
            ("CREATE TABLE seq (n INTEGER)",),
            ("INSERT INTO seq VALUES (2)",),
        ),
    )

    store.migrate()

    assert user_version(tmp_path) == len(MIGRATIONS) + 2
    assert query(tmp_path, "SELECT n FROM seq") == [(2,)]
    assert [job.name for job in store.job_states()] == ["games"]


def test_a_failed_migration_leaves_the_database_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_store(tmp_path)
    store.record_success("games", NOON)
    monkeypatch.setattr(
        state,
        "MIGRATIONS",
        (
            *MIGRATIONS,
            ("CREATE TABLE extra (a)",),
            ("INSERT INTO missing_table VALUES (1)",),
        ),
    )

    with pytest.raises(
        StateMigrationError, match=f"state migration {len(MIGRATIONS) + 2} failed"
    ):
        store.migrate()

    assert user_version(tmp_path) == len(MIGRATIONS)
    assert "extra" not in table_names(tmp_path)
    assert [job.name for job in store.job_states()] == ["games"]


def test_a_failed_first_migration_leaves_a_new_database_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        state,
        "MIGRATIONS",
        ((MIGRATIONS[0][0], "INSERT INTO missing_table VALUES (1)"),),
    )

    with pytest.raises(StateMigrationError, match="state migration 1 failed"):
        StateStore(tmp_path).migrate()

    assert user_version(tmp_path) == 0
    assert query(tmp_path, "SELECT name FROM sqlite_master") == []


def test_stores_a_final_time_in_utc(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    plus_two = dt.timezone(dt.timedelta(hours=2))

    store.set_final_time("g1", DAY, dt.datetime(2026, 1, 10, 14, 0, tzinfo=plus_two))

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

    store.set_final_time("g1", DAY, NOON)
    store.set_final_time("g1", DAY, LATER)

    assert store.final_time("g1") == NOON


def test_stores_whether_the_final_time_was_first_seen(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.set_final_time("g1", DAY, NOON)
    store.set_final_time("g2", DAY, NOON, first_seen=True)
    store.set_final_time("g2", DAY, LATER, first_seen=False)

    assert store.first_seen_final("g1") is False
    assert store.first_seen_final("g2") is True


def test_stores_a_final_time_on_a_game_row_that_has_none(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_highlight_attempt("g1", DAY)

    store.set_final_time("g1", DAY, NOON, first_seen=True)

    assert store.final_time("g1") == NOON
    assert store.first_seen_final("g1") is True


def test_counts_failed_stats_attempts_per_game(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.record_failed_stats_attempt("g1", DAY) == 1
    assert store.record_failed_stats_attempt("g1", DAY) == 2
    assert store.record_failed_stats_attempt("g2", DAY) == 1
    assert store.failed_stats_attempts("g1") == 2


def test_counts_highlight_attempts_per_game(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.record_highlight_attempt("g1", DAY) == 1
    assert store.record_highlight_attempt("g1", DAY) == 2
    assert store.record_highlight_attempt("g2", DAY) == 1
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
        store.set_final_time("g1", DAY, naive)
    with pytest.raises(ValueError):
        store.record_success("games", naive)
    with pytest.raises(ValueError):
        store.record_failure("games", naive, "x")


def test_keeps_state_across_store_instances_over_the_same_directory(
    tmp_path: Path,
) -> None:
    first = make_store(tmp_path)
    first.set_final_time("g1", DAY, NOON, first_seen=True)
    first.record_highlight_attempt("g1", DAY)
    first.record_failed_stats_attempt("g1", DAY)
    first.record_failure("games", LATER, "source down")

    second = make_store(tmp_path)

    assert second.final_time("g1") == NOON
    assert second.highlight_attempts("g1") == 1
    assert second.failed_stats_attempts("g1") == 1
    assert second.first_seen_final("g1") is True
    assert second.game_date("g1") == DAY
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


def test_stores_the_game_date_on_the_first_write_of_each_writer(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    store.set_final_time("a", dt.date(2026, 1, 1), NOON)
    store.record_highlight_attempt("b", dt.date(2026, 1, 2))
    store.record_failed_stats_attempt("c", dt.date(2026, 1, 3))

    assert store.game_date("a") == dt.date(2026, 1, 1)
    assert store.game_date("b") == dt.date(2026, 1, 2)
    assert store.game_date("c") == dt.date(2026, 1, 3)


def test_keeps_the_game_date_of_the_first_write(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    other = dt.date(2026, 2, 2)
    store.set_final_time("a", DAY, NOON)
    store.record_highlight_attempt("b", DAY)
    store.record_failed_stats_attempt("c", DAY)

    store.set_final_time("a", other, LATER)
    store.record_highlight_attempt("a", other)
    store.record_highlight_attempt("b", other)
    store.record_failed_stats_attempt("b", other)
    store.record_failed_stats_attempt("c", other)
    store.set_final_time("c", other, LATER)

    assert [store.game_date(g) for g in "abc"] == [DAY, DAY, DAY]


def test_reports_no_game_date_for_an_unknown_game(tmp_path: Path) -> None:
    assert make_store(tmp_path).game_date("nope") is None


def test_prunes_the_final_time_and_stats_attempts_of_games_before_the_cutoff(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    cutoff = dt.date(2026, 1, 10)
    for game_id, day in [("old", dt.date(2026, 1, 9)), ("edge", cutoff)]:
        store.set_final_time(game_id, day, NOON, first_seen=True)
        store.record_failed_stats_attempt(game_id, day)

    store.prune_final_times(cutoff)

    assert store.final_time("old") is None
    assert store.first_seen_final("old") is False
    assert store.failed_stats_attempts("old") == 0
    assert store.final_time("edge") == NOON
    assert store.first_seen_final("edge") is True
    assert store.failed_stats_attempts("edge") == 1


def test_pruning_never_deletes_highlights_or_highlight_attempts(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    highlight = Highlight(
        title="Full game",
        channel="Channel",
        thumbnail_url=HttpUrl("https://example.com/t.jpg"),
        embed_url=HttpUrl("https://example.com/e"),
    )
    store.set_final_time("old", DAY, NOON)
    store.record_highlight_attempt("old", DAY)
    store.record_highlight_attempt("old", DAY)
    store.set_highlight("old", highlight)

    store.prune_final_times(dt.date(2026, 3, 1))

    assert store.highlight_attempts("old") == 2
    assert store.highlights() == {"old": highlight}
    assert store.game_date("old") == DAY


def test_pruning_with_no_games_does_nothing(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.prune_final_times(dt.date(2026, 3, 1))

    assert store.game_date("any") is None


def test_setting_a_team_star_twice_leaves_one_row(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.set_star(make_star("BOS", "p1"))
    store.set_star(make_star("BOS", "p2"))

    with closing(sqlite3.connect(tmp_path / STATE_FILE)) as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM stars WHERE team_code = 'BOS'"
        ).fetchone()

    assert row[0] == 1


def test_recording_a_job_success_twice_leaves_one_row(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_success("games", NOON)
    store.record_success("games", LATER)

    assert len(store.job_states()) == 1


def test_recording_a_job_failure_twice_leaves_one_row(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_failure("games", NOON, "x")
    store.record_failure("games", LATER, "y")

    assert len(store.job_states()) == 1


def test_migrates_a_database_at_the_previous_version_with_its_rows_to_the_source_cache_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = state.MIGRATIONS
    monkeypatch.setattr(state, "MIGRATIONS", real[:1])
    store = make_store(tmp_path)
    star = make_star("AAA", "p1")
    store.set_final_time("g1", DAY, NOON)
    store.set_star(star)
    highlight = make_highlight("Recap")
    store.set_highlight("g1", highlight)
    store.record_success("games", NOON)
    assert user_version(tmp_path) == 1
    assert "source_cache" not in table_names(tmp_path)
    monkeypatch.setattr(state, "MIGRATIONS", real)

    store.migrate()

    assert user_version(tmp_path) == len(real)
    assert store.final_time("g1") == NOON
    assert store.stars() == {"AAA": star}
    assert store.highlights() == {"g1": highlight}
    assert [(j.name, j.last_success) for j in store.job_states()] == [("games", NOON)]
    assert query(tmp_path, "SELECT COUNT(*) FROM source_cache") == [(0,)]
    store.set_source_entry("https://example.com/a", "{}", NOON)
    entry = store.source_entry("https://example.com/a")
    assert entry is not None
    assert entry.body == "{}"


def test_stores_a_source_entry_and_replaces_it_on_the_next_store(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    url = "https://example.com/a?x=1"

    store.set_source_entry(url, '{"n": 1}', NOON)
    first = store.source_entry(url)
    store.set_source_entry(
        url, '{"n": 2}', LATER.astimezone(dt.timezone(dt.timedelta(hours=2)))
    )
    second = store.source_entry(url)

    assert first is not None
    assert (first.url, first.body, first.fetched_at) == (url, '{"n": 1}', NOON)
    assert second is not None
    assert (second.body, second.fetched_at) == ('{"n": 2}', LATER)
    assert second.fetched_at.utcoffset() == dt.timedelta(0)
    assert query(tmp_path, "SELECT COUNT(*) FROM source_cache") == [(1,)]


def test_reports_no_source_entry_for_an_unknown_url(tmp_path: Path) -> None:
    assert make_store(tmp_path).source_entry("https://example.com/none") is None


def test_keeps_source_entries_across_store_instances_over_the_same_directory(
    tmp_path: Path,
) -> None:
    make_store(tmp_path).set_source_entry("https://example.com/a", "[]", NOON)

    entry = StateStore(tmp_path).source_entry("https://example.com/a")

    assert entry is not None
    assert (entry.body, entry.fetched_at) == ("[]", NOON)


def test_rejects_a_naive_fetch_time(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(ValueError, match="timezone aware"):
        store.set_source_entry("https://example.com/a", "{}", NOON.replace(tzinfo=None))

    assert store.source_entry("https://example.com/a") is None


def test_migrates_a_database_at_the_previous_version_with_its_rows_to_the_feed_builds_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = state.MIGRATIONS
    monkeypatch.setattr(state, "MIGRATIONS", real[:2])
    store = make_store(tmp_path)
    star = make_star("AAA", "p1")
    store.set_final_time("g1", DAY, NOON)
    store.set_star(star)
    highlight = make_highlight("Recap")
    store.set_highlight("g1", highlight)
    store.record_success("games", NOON)
    store.set_source_entry("https://example.com/a", "{}", NOON)
    assert user_version(tmp_path) == 2
    assert "feed_builds" not in table_names(tmp_path)
    monkeypatch.setattr(state, "MIGRATIONS", real)

    store.migrate()

    assert user_version(tmp_path) == len(real)
    assert store.final_time("g1") == NOON
    assert store.stars() == {"AAA": star}
    assert store.highlights() == {"g1": highlight}
    assert [(j.name, j.last_success) for j in store.job_states()] == [("games", NOON)]
    entry = store.source_entry("https://example.com/a")
    assert entry is not None
    assert entry.body == "{}"
    assert query(tmp_path, "SELECT COUNT(*) FROM feed_builds") == [(0,)]
    store.record_build("players", "p1", NOON)
    build = store.feed_build("players", "p1")
    assert build is not None
    assert build.last_build == NOON


def test_records_a_feed_build_time_in_utc_and_replaces_it_on_the_next_build(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    store.record_build("players", "p1", NOON)
    first = store.feed_build("players", "p1")
    store.record_build(
        "players", "p1", LATER.astimezone(dt.timezone(dt.timedelta(hours=2)))
    )
    second = store.feed_build("players", "p1")

    assert first is not None
    assert first.last_build == NOON
    assert first.last_failure is None
    assert second is not None
    assert second.last_build == LATER
    assert second.last_build is not None
    assert second.last_build.utcoffset() == dt.timedelta(0)


def test_keeps_a_feeds_last_build_on_failure_and_its_last_failure_on_build(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    store.record_build("players", "p1", NOON)

    store.record_build_failure("players", "p1", LATER, "source down")
    failed = store.feed_build("players", "p1")
    store.record_build("players", "p1", LATER + dt.timedelta(hours=1))
    built = store.feed_build("players", "p1")

    assert failed is not None
    assert (failed.last_build, failed.last_failure) == (NOON, LATER)
    assert failed.last_failure_reason == "source down"
    assert built is not None
    assert built.last_build == LATER + dt.timedelta(hours=1)
    assert (built.last_failure, built.last_failure_reason) == (LATER, "source down")


def test_logs_a_recorded_build_failure_with_its_kind_id_and_reason(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = make_store(tmp_path)

    with caplog.at_level(logging.ERROR):
        store.record_build_failure("players", "p1", NOON, "source down")

    assert "feed players p1 build failed: source down" in caplog.text


def test_stores_the_fallback_reason_for_a_build_failure_with_an_empty_reason(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)

    store.record_build_failure("players", "p1", NOON, "  ")

    build = store.feed_build("players", "p1")
    assert build is not None
    assert build.last_failure_reason == NO_REASON


def test_rejects_a_naive_build_time_and_a_naive_failure_time(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    naive = NOON.replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone aware"):
        store.record_build("players", "p1", naive)
    with pytest.raises(ValueError, match="timezone aware"):
        store.record_build_failure("players", "p1", naive, "x")


def test_reports_no_build_state_for_an_unknown_feed(tmp_path: Path) -> None:
    assert make_store(tmp_path).feed_build("players", "none") is None


def test_lists_only_feeds_with_a_recorded_failure_ordered_by_kind_and_id(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    store.record_build("players", "ok", NOON)
    store.record_build_failure("teams", "b", NOON, "x")
    store.record_build_failure("players", "b", NOON, "x")
    store.record_build_failure("players", "a", NOON, "x")

    failed = store.failed_feed_builds()

    assert [(f.kind, f.feed_id) for f in failed] == [
        ("players", "a"),
        ("players", "b"),
        ("teams", "b"),
    ]


def test_lists_the_stored_ids_of_one_kind_only(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.record_build("players", "a", NOON)
    store.record_build_failure("players", "b", NOON, "x")
    store.record_build("teams", "c", NOON)

    assert store.feed_build_ids("players") == {"a", "b"}
    assert store.feed_build_ids("none") == set()


def test_deletes_a_feeds_build_state_and_leaves_the_other_kinds_rows_alone(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    store.record_build("players", "a", NOON)
    store.record_build("teams", "a", NOON)

    store.delete_feed_build("players", "a")
    store.delete_feed_build("players", "missing")

    assert store.feed_build("players", "a") is None
    assert store.feed_build("teams", "a") is not None


def test_keeps_feed_build_state_across_store_instances_over_the_same_directory(
    tmp_path: Path,
) -> None:
    make_store(tmp_path).record_build_failure("players", "a", NOON, "x")

    build = StateStore(tmp_path).feed_build("players", "a")

    assert build is not None
    assert build.last_failure == NOON


def test_recording_a_build_twice_leaves_one_row(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    store.record_build("players", "a", NOON)
    store.record_build("players", "a", LATER)
    store.record_build_failure("players", "a", NOON, "x")
    store.record_build_failure("players", "a", LATER, "y")

    assert query(tmp_path, "SELECT COUNT(*) FROM feed_builds") == [(1,)]
