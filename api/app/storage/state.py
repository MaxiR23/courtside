# api/app/storage/state.py
#
# Job state in SQLite: game dates, final times and whether they were first seen, highlight attempts, failed stats attempts, matched highlights, team stars, discovered All-Star editions, the video of each edition and the time each All-Star game was first seen final, the date and box-score players of past games, the highlights backfill's resume point, the targets the running sweep reads for and swept targets, source cache entries, feed build times and failures and per-job outcomes.
# Schema versioned with PRAGMA user_version; MIGRATIONS run once each on startup.
# One connection per operation, so sync endpoints can use it from the threadpool.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/adr/0011-state-retention.md, docs/source-rules.md

import datetime as dt
import json
import logging
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import closing
from pathlib import Path
from typing import Annotated

from pydantic import Field

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
    (
        (
            "CREATE TABLE feed_builds ("
            "kind TEXT NOT NULL, feed_id TEXT NOT NULL, last_build TEXT, "
            "last_failure TEXT, last_failure_reason TEXT, "
            "PRIMARY KEY (kind, feed_id))"
        ),
    ),
    # Removes the jobs row of the game detail job removed in issue 154.
    (("DELETE FROM jobs WHERE name = 'game-detail'"),),
    # The All-Star editions the discovery job found, one per season (ADR 0036).
    (
        (
            "CREATE TABLE all_star_editions ("
            "season INTEGER PRIMARY KEY, game_date TEXT NOT NULL, "
            "game_ids TEXT NOT NULL)"
        ),
    ),
    # The time the All-Star feed first saw each All-Star game final (ADR 0036).
    (
        (
            "CREATE TABLE all_star_finals ("
            "game_id TEXT PRIMARY KEY, seen_at TEXT NOT NULL)"
        ),
    ),
    # The highlights backfill and the All-Star edition video (ADR 0048).
    (
        (
            "CREATE TABLE all_star_edition_highlights ("
            "season INTEGER PRIMARY KEY, highlight TEXT NOT NULL)"
        ),
        (
            "CREATE TABLE highlights_backfill ("
            "id INTEGER PRIMARY KEY CHECK (id = 1), "
            "page_token TEXT NOT NULL, oldest TEXT NOT NULL)"
        ),
        (
            "CREATE TABLE highlights_backfill_swept ("
            "kind TEXT NOT NULL, target_id TEXT NOT NULL, "
            "PRIMARY KEY (kind, target_id))"
        ),
        (
            "CREATE TABLE highlights_backfill_members ("
            "kind TEXT NOT NULL, target_id TEXT NOT NULL, "
            "PRIMARY KEY (kind, target_id))"
        ),
    ),
    # The date and box-score players of past games (ADR 0053).
    (
        (
            "CREATE TABLE past_games ("
            "game_id TEXT PRIMARY KEY, game_date TEXT NOT NULL, players TEXT)"
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


class FeedBuildState(FeedModel):
    kind: NonEmptyStr
    feed_id: NonEmptyStr
    last_build: UtcDatetime | None
    last_failure: UtcDatetime | None
    last_failure_reason: NonEmptyStr | None


class AllStarEditionRecord(FeedModel):
    """An All-Star edition the discovery job found. Never reaches a feed."""

    season: int
    game_date: dt.date
    game_ids: Annotated[list[NonEmptyStr], Field(min_length=1)]


class BackfillSweep(FeedModel):
    """The running sweep of the highlights backfill: the page token to continue
    from and the oldest upload time reached. Never reaches a feed."""

    page_token: NonEmptyStr
    oldest: UtcDatetime


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


def _to_feed_build(
    row: tuple[str, str, str | None, str | None, str | None],
) -> FeedBuildState:
    kind, feed_id, build, failure, reason = row
    return FeedBuildState(
        kind=kind,
        feed_id=feed_id,
        last_build=_from_text(build),
        last_failure=_from_text(failure),
        last_failure_reason=reason,
    )


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

    def record_build(self, kind: str, feed_id: str, at: dt.datetime) -> None:
        text = _to_text(at)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO feed_builds (kind, feed_id, last_build) VALUES (?, ?, ?) "
                "ON CONFLICT(kind, feed_id) DO UPDATE SET "
                "last_build = excluded.last_build",
                (kind, feed_id, text),
            )

    def record_build_failure(
        self, kind: str, feed_id: str, at: dt.datetime, reason: str
    ) -> None:
        text = _to_text(at)
        if not reason.strip():
            reason = NO_REASON
        logger.error("feed %s %s build failed: %s", kind, feed_id, reason)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO feed_builds (kind, feed_id, last_failure, "
                "last_failure_reason) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(kind, feed_id) DO UPDATE SET "
                "last_failure = excluded.last_failure, "
                "last_failure_reason = excluded.last_failure_reason",
                (kind, feed_id, text, reason),
            )

    def feed_build(self, kind: str, feed_id: str) -> FeedBuildState | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT kind, feed_id, last_build, last_failure, "
                "last_failure_reason FROM feed_builds "
                "WHERE kind = ? AND feed_id = ?",
                (kind, feed_id),
            ).fetchone()
        return _to_feed_build(row) if row else None

    def failed_feed_builds(self) -> list[FeedBuildState]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT kind, feed_id, last_build, last_failure, "
                "last_failure_reason FROM feed_builds "
                "WHERE last_failure IS NOT NULL ORDER BY kind, feed_id"
            ).fetchall()
        return [_to_feed_build(row) for row in rows]

    def feed_build_ids(self, kind: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT feed_id FROM feed_builds WHERE kind = ?", (kind,)
            ).fetchall()
        return {row[0] for row in rows}

    def delete_feed_build(self, kind: str, feed_id: str) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM feed_builds WHERE kind = ? AND feed_id = ?",
                (kind, feed_id),
            )

    def set_all_star_edition(
        self, season: int, game_date: dt.date, game_ids: list[str]
    ) -> None:
        record = AllStarEditionRecord(
            season=season, game_date=game_date, game_ids=game_ids
        )
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO all_star_editions (season, game_date, game_ids) "
                "VALUES (?, ?, ?) ON CONFLICT(season) DO UPDATE SET "
                "game_date = excluded.game_date, game_ids = excluded.game_ids",
                (season, record.game_date.isoformat(), json.dumps(record.game_ids)),
            )

    def all_star_edition(self, season: int) -> AllStarEditionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT game_date, game_ids FROM all_star_editions WHERE season = ?",
                (season,),
            ).fetchone()
        if row is None:
            return None
        return AllStarEditionRecord(
            season=season,
            game_date=dt.date.fromisoformat(row[0]),
            game_ids=json.loads(row[1]),
        )

    def record_all_star_final(self, game_id: str, at: dt.datetime) -> None:
        """Stores the time an All-Star game was first seen final; a stored time
        is never overwritten."""
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO all_star_finals (game_id, seen_at) "
                "VALUES (?, ?)",
                (game_id, _to_text(at)),
            )

    def all_star_final_time(self, game_id: str) -> dt.datetime | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT seen_at FROM all_star_finals WHERE game_id = ?", (game_id,)
            ).fetchone()
        return _from_text(row[0]) if row else None

    def set_all_star_edition_highlight(self, season: int, highlight: Highlight) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO all_star_edition_highlights (season, highlight) "
                "VALUES (?, ?) ON CONFLICT(season) DO UPDATE SET "
                "highlight = excluded.highlight",
                (season, highlight.model_dump_json()),
            )

    def all_star_edition_highlight(self, season: int) -> Highlight | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT highlight FROM all_star_edition_highlights WHERE season = ?",
                (season,),
            ).fetchone()
        return Highlight.model_validate_json(row[0]) if row else None

    def all_star_editions(self) -> list[AllStarEditionRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT season, game_date, game_ids FROM all_star_editions "
                "ORDER BY season"
            ).fetchall()
        return [
            AllStarEditionRecord(
                season=season,
                game_date=dt.date.fromisoformat(game_date),
                game_ids=json.loads(game_ids),
            )
            for season, game_date, game_ids in rows
        ]

    def set_past_game_dates(self, dates: Mapping[str, dt.date]) -> None:
        """Registers the dates of past games; a stored row and its players are
        never overwritten."""
        with self._connect() as connection, connection:
            connection.executemany(
                "INSERT OR IGNORE INTO past_games (game_id, game_date) VALUES (?, ?)",
                [(game_id, day.isoformat()) for game_id, day in dates.items()],
            )

    def set_past_game_players(
        self, game_id: str, game_date: dt.date, players: str
    ) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO past_games (game_id, game_date, players) "
                "VALUES (?, ?, ?) ON CONFLICT(game_id) DO UPDATE SET "
                "players = excluded.players",
                (game_id, game_date.isoformat(), players),
            )

    def past_game_players(self, game_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT players FROM past_games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return None if row is None else row[0]

    def past_game_date(self, game_id: str) -> dt.date | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT game_date FROM past_games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return None if row is None else dt.date.fromisoformat(row[0])

    def backfill_sweep(self) -> BackfillSweep | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT page_token, oldest FROM highlights_backfill WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        oldest = _from_text(row[1])
        assert oldest is not None
        return BackfillSweep(page_token=row[0], oldest=oldest)

    def set_backfill_sweep(
        self,
        page_token: str,
        oldest: dt.datetime,
        members: Iterable[tuple[str, str]],
    ) -> None:
        text = _to_text(oldest)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO highlights_backfill (id, page_token, oldest) "
                "VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                "page_token = excluded.page_token, oldest = excluded.oldest",
                (page_token, text),
            )
            connection.execute("DELETE FROM highlights_backfill_members")
            connection.executemany(
                "INSERT OR IGNORE INTO highlights_backfill_members "
                "(kind, target_id) VALUES (?, ?)",
                list(members),
            )

    def backfill_members(self) -> set[tuple[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT kind, target_id FROM highlights_backfill_members"
            ).fetchall()
        return {(row[0], row[1]) for row in rows}

    def end_backfill_sweep(self) -> None:
        with self._connect() as connection, connection:
            connection.execute("DELETE FROM highlights_backfill")
            connection.execute("DELETE FROM highlights_backfill_members")

    def mark_backfill_swept(self, kind: str, target_ids: Iterable[str]) -> None:
        with self._connect() as connection, connection:
            connection.executemany(
                "INSERT OR IGNORE INTO highlights_backfill_swept (kind, target_id) "
                "VALUES (?, ?)",
                [(kind, target_id) for target_id in target_ids],
            )

    def backfill_swept(self, kind: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT target_id FROM highlights_backfill_swept WHERE kind = ?",
                (kind,),
            ).fetchall()
        return {row[0] for row in rows}
