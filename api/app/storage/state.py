# api/app/storage/state.py
#
# Job state in SQLite: final times, highlight attempts and per-job outcomes.
# One connection per operation, so sync endpoints can use it from the threadpool.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md

import datetime as dt
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from app.feeds.games import FeedModel, NonEmptyStr, UtcDatetime

logger = logging.getLogger(__name__)

STATE_FILE = "state.sqlite3"
NO_REASON = "no reason given"


class JobState(FeedModel):
    name: NonEmptyStr
    last_success: UtcDatetime | None
    last_failure: UtcDatetime | None
    last_failure_reason: NonEmptyStr | None


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

    def create_tables(self) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS games ("
                "game_id TEXT PRIMARY KEY, final_time TEXT, "
                "highlight_attempts INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS jobs ("
                "name TEXT PRIMARY KEY, last_success TEXT, "
                "last_failure TEXT, last_failure_reason TEXT)"
            )

    def set_final_time(self, game_id: str, final_time: dt.datetime) -> None:
        text = _to_text(final_time)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO games (game_id, final_time) VALUES (?, ?) "
                "ON CONFLICT(game_id) DO UPDATE SET final_time = excluded.final_time",
                (game_id, text),
            )

    def final_time(self, game_id: str) -> dt.datetime | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT final_time FROM games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return _from_text(row[0]) if row else None

    def record_highlight_attempt(self, game_id: str) -> int:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO games (game_id, highlight_attempts) VALUES (?, 1) "
                "ON CONFLICT(game_id) DO UPDATE SET "
                "highlight_attempts = highlight_attempts + 1",
                (game_id,),
            )
        return self.highlight_attempts(game_id)

    def highlight_attempts(self, game_id: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT highlight_attempts FROM games WHERE game_id = ?", (game_id,)
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
