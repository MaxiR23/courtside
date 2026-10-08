# api/app/storage/state.py
#
# Job state in SQLite: game dates, final times and whether they were first seen, highlight attempts, failed stats attempts, matched highlights, team stars, source cache entries and per-job outcomes.
# Schema versioned with PRAGMA user_version; MIGRATIONS run once each on startup.
# One connection per operation, so sync endpoints can use it from the threadpool.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/adr/0011-state-retention.md, docs/source-rules.md

import datetime as dt
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from app.feeds.games import FeedModel, Highlight, NonEmptyStr, Star, UtcDatetime

logger = logging.getLogger(__name__)

STATE_FILE = "state.sqlite3"
NO_REASON = "no reason given"

# One migration is a tuple of SQL statements. Append new ones; never edit,
# reorder or remove one that has shipped. SEE: docs/architecture.md
type Migration = tuple[str, ...]

MIGRATIONS: tuple[Migration, ...] = (
    (
        (
            "CREATE TABLE IF NOT EXISTS games ("
            "game_id TEXT PRIMARY KEY, game_date TEXT NOT NULL, final_time TEXT, "
            "highlight_attempts INTEGER NOT NULL DEFAULT 0, "
            "first_seen_final INTEGER NOT NULL DEFAULT 0, "
            "failed_stats_attempts INTEGER NOT NULL DEFAULT 0)"
        ),
        (
            "CREATE TABLE IF NOT EXISTS stars ("
            "team_code TEXT PRIMARY KEY, star TEXT NOT NULL)"
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
    ),
    (
        (
            "CREATE TABLE source_cache ("
            "url TEXT PRIMARY KEY, body TEXT NOT NULL, fetched_at TEXT NOT NULL)"
        ),
    ),
)


class StateMigrationError(Exception):
    """A state database migration failed and was rolled back."""


class JobState(FeedModel):
    name: NonEmptyStr
    last_success: UtcDatetime | None
    last_failure: UtcDatetime | None
    last_failure_reason: NonEmptyStr | None


class SourceEntry(FeedModel):
    url: NonEmptyStr
    body: str
    fetched_at: UtcDatetime


def _to_text(value: dt.datetime) -> str:
    if value.utcoffset() is None:
        raise ValueError("time must be timezone aware")
    return value.astimezone(dt.UTC).isoformat()


def _require_job(job: str) -> None:
    if not job.strip():
        raise ValueError("job name must not be empty")


def _from_text(value: str | None) -> dt.datetime | None:
    if value is None:
        return None
    return dt.datetime.fromisoformat(value).astimezone(dt.UTC)


class StateStore:
    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / STATE_FILE

    def _connect(self) -> closing[sqlite3.Connection]:
        return closing(sqlite3.connect(self._path))

    def migrate(self) -> None:
        """Runs every pending migration in order, all in one transaction;
        on failure rolls back and raises StateMigrationError."""
        with closing(sqlite3.connect(self._path, isolation_level=None)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                for number, statements in enumerate(
                    MIGRATIONS[version:], start=version + 1
                ):
                    try:
                        for statement in statements:
                            connection.execute(statement)
                    except sqlite3.Error as error:
                        raise StateMigrationError(
                            f"state migration {number} failed: {error}"
                        ) from error
                    connection.execute(f"PRAGMA user_version = {number}")
                connection.execute("COMMIT")
            except BaseException:
                connection.execute("ROLLBACK")
                raise

    def set_star(self, star: Star) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO stars (team_code, star) VALUES (?, ?) "
                "ON CONFLICT(team_code) DO UPDATE SET star = excluded.star",
                (star.team_code, star.model_dump_json()),
            )

    def delete_star(self, team_code: str) -> None:
        with self._connect() as connection, connection:
            connection.execute("DELETE FROM stars WHERE team_code = ?", (team_code,))

    def stars(self) -> dict[str, Star]:
        with self._connect() as connection:
            rows = connection.execute("SELECT team_code, star FROM stars").fetchall()
        return {code: Star.model_validate_json(text) for code, text in rows}

    def set_highlight(self, game_id: str, highlight: Highlight) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO highlights (game_id, highlight) VALUES (?, ?) "
                "ON CONFLICT(game_id) DO UPDATE SET highlight = excluded.highlight",
                (game_id, highlight.model_dump_json()),
            )

    def highlights(self) -> dict[str, Highlight]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT game_id, highlight FROM highlights"
            ).fetchall()
        return {gid: Highlight.model_validate_json(text) for gid, text in rows}

    def set_final_time(
        self,
        game_id: str,
        game_date: dt.date,
        final_time: dt.datetime,
        *,
        first_seen: bool = False,
    ) -> None:
        text = _to_text(final_time)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO games (game_id, game_date, final_time, first_seen_final) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(game_id) DO UPDATE SET "
                "final_time = excluded.final_time, "
                "first_seen_final = excluded.first_seen_final "
                "WHERE games.final_time IS NULL",
                (game_id, game_date.isoformat(), text, int(first_seen)),
            )

    def game_date(self, game_id: str) -> dt.date | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT game_date FROM games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return dt.date.fromisoformat(row[0]) if row else None

    def prune_final_times(self, before: dt.date) -> None:
        """Deletes the final time, first-seen flag and failed stats attempts
        of every game dated before `before`; highlights are kept."""
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE games SET final_time = NULL, first_seen_final = 0, "
                "failed_stats_attempts = 0 WHERE game_date < ?",
                (before.isoformat(),),
            )

    def first_seen_final(self, game_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT first_seen_final FROM games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return bool(row[0]) if row else False

    def final_time(self, game_id: str) -> dt.datetime | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT final_time FROM games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return _from_text(row[0]) if row else None

    def record_highlight_attempt(self, game_id: str, game_date: dt.date) -> int:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO games (game_id, game_date, highlight_attempts) "
                "VALUES (?, ?, 1) "
                "ON CONFLICT(game_id) DO UPDATE SET "
                "highlight_attempts = highlight_attempts + 1",
                (game_id, game_date.isoformat()),
            )
        return self.highlight_attempts(game_id)

    def highlight_attempts(self, game_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT highlight_attempts FROM games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return int(row[0]) if row else 0

    def record_failed_stats_attempt(self, game_id: str, game_date: dt.date) -> int:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO games (game_id, game_date, failed_stats_attempts) "
                "VALUES (?, ?, 1) "
                "ON CONFLICT(game_id) DO UPDATE SET "
                "failed_stats_attempts = failed_stats_attempts + 1",
                (game_id, game_date.isoformat()),
            )
        return self.failed_stats_attempts(game_id)

    def failed_stats_attempts(self, game_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT failed_stats_attempts FROM games WHERE game_id = ?",
                (game_id,),
            ).fetchone()
        return int(row[0]) if row else 0

    def record_success(self, job: str, at: dt.datetime) -> None:
        _require_job(job)
        text = _to_text(at)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO jobs (name, last_success) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET last_success = excluded.last_success",
                (job, text),
            )

    def record_failure(self, job: str, at: dt.datetime, reason: str) -> None:
        _require_job(job)
        text = _to_text(at)
        if not reason.strip():
            reason = NO_REASON
        logger.error("job %s failed: %s", job, reason)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO jobs (name, last_failure, last_failure_reason) "
                "VALUES (?, ?, ?) ON CONFLICT(name) DO UPDATE SET "
                "last_failure = excluded.last_failure, "
                "last_failure_reason = excluded.last_failure_reason",
                (job, text, reason),
            )

    def job_states(self) -> list[JobState]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT name, last_success, last_failure, last_failure_reason "
                "FROM jobs ORDER BY name"
            ).fetchall()
        return [
            JobState(
                name=name,
                last_success=_from_text(success),
                last_failure=_from_text(failure),
                last_failure_reason=reason,
            )
            for name, success, failure, reason in rows
        ]

    def set_source_entry(self, url: str, body: str, fetched_at: dt.datetime) -> None:
        text = _to_text(fetched_at)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO source_cache (url, body, fetched_at) VALUES (?, ?, ?) "
                "ON CONFLICT(url) DO UPDATE SET body = excluded.body, "
                "fetched_at = excluded.fetched_at",
                (url, body, text),
            )

    def source_entry(self, url: str) -> SourceEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT body, fetched_at FROM source_cache WHERE url = ?", (url,)
            ).fetchone()
        if row is None:
            return None
        fetched_at = _from_text(row[1])
        if fetched_at is None:
            raise ValueError("source cache entry has no fetch time")
        return SourceEntry(url=url, body=row[0], fetched_at=fetched_at)
