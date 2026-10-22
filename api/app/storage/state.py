# api/app/storage/state.py
#
# Job state in SQLite: game dates, final times and whether they were first seen, highlight attempts, failed stats attempts, matched highlights, team stars, team identities (logo and colors), discovered All-Star editions, the video of each edition and the time each All-Star game was first seen final, the date and box-score players of past games, the player identity cache, the seasons a team did not exist, the targets the highlights search found no video for and its searches per day, source cache entries, feed build times and failures and per-job outcomes.
# Schema versioned with PRAGMA user_version; MIGRATIONS run once each on startup.
# One connection per operation, so sync endpoints can use it from the threadpool.
#
# SEE: docs/adr/0007-backend-runtime-and-data-pipeline.md, docs/adr/0063-bounded-state-and-kept-feeds.md, docs/source-rules.md

import datetime as dt
import json
import logging
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import closing
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from app.feeds.games import (
    FeedModel,
    Highlight,
    NonEmptyStr,
    Star,
    TeamCode,
    UtcDatetime,
)
from app.feeds.opponent import TeamColors, TeamLogo

logger = logging.getLogger(__name__)

STATE_FILE = "state.sqlite3"
NO_REASON = "no reason given"
# Every connection waits this long on a lock instead of relying on the library
# default (ADR 0063).
BUSY_TIMEOUT_SECONDS = 5.0
# The most failed builds /health lists (ADR 0063).
MAX_FAILED_BUILDS = 50
# Which set of PastPlayerIds a learned id belongs to (ADR 0063).
PastPlayerScope = Literal["known", "in_season"]

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
    # The player identity cache of the past playoffs build (ADR 0061).
    (
        (
            "CREATE TABLE player_identities (player_id TEXT PRIMARY KEY, "
            "athlete TEXT NOT NULL, read_at TEXT NOT NULL)"
        ),
    ),
    # The last served and touched times of the bounded state, and the past
    # player ids (ADR 0063).
    (
        "ALTER TABLE feed_builds ADD COLUMN last_served TEXT",
        (
            "UPDATE feed_builds SET last_served = "
            "strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')"
        ),
        "ALTER TABLE past_games ADD COLUMN touched_at TEXT",
        (
            "UPDATE past_games SET touched_at = "
            "strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')"
        ),
        "ALTER TABLE player_identities ADD COLUMN touched_at TEXT",
        (
            "UPDATE player_identities SET touched_at = "
            "strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now')"
        ),
        (
            "CREATE TABLE past_player_ids (player_id TEXT NOT NULL, "
            "scope TEXT NOT NULL, learned_at TEXT NOT NULL, "
            "PRIMARY KEY (player_id, scope))"
        ),
    ),
    # The seasons a team did not exist, honored and kept 30 days (ADR 0064).
    (
        (
            "CREATE TABLE season_team_absences (team_code TEXT NOT NULL, "
            "season INTEGER NOT NULL, recorded_at TEXT NOT NULL, "
            "PRIMARY KEY (team_code, season))"
        ),
    ),
    # The on-demand highlights search replaces the backfill (ADR 0065).
    (
        "DROP TABLE highlights_backfill",
        "DROP TABLE highlights_backfill_swept",
        "DROP TABLE highlights_backfill_members",
        "DELETE FROM jobs WHERE name IN ('highlights-backfill', 'all-star-discovery')",
        (
            "CREATE TABLE highlight_searches (kind TEXT NOT NULL, "
            "target_id TEXT NOT NULL, searched_at TEXT NOT NULL, "
            "PRIMARY KEY (kind, target_id))"
        ),
        (
            "CREATE TABLE highlight_search_counts (day TEXT PRIMARY KEY, "
            "searches INTEGER NOT NULL)"
        ),
    ),
    # The team identities the stars job keeps (ADR 0068).
    (
        "CREATE TABLE team_identities (team_code TEXT PRIMARY KEY, identity TEXT NOT NULL)",
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
    """An All-Star edition the All-Star feeds found. Never reaches a feed."""

    season: int
    game_date: dt.date
    game_ids: Annotated[list[NonEmptyStr], Field(min_length=1)]


class TeamIdentity(FeedModel):
    """A team's logo and colors, as the stars job read them. Never reaches a feed."""

    code: TeamCode
    logo: TeamLogo | None
    colors: TeamColors


class SourceEntry(FeedModel):
    url: NonEmptyStr
    body: str
    fetched_at: UtcDatetime


class PlayerIdentityEntry(FeedModel):
    """A stored player identity and when it was read. Never reaches a feed."""

    body: str
    read_at: UtcDatetime


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
        return closing(sqlite3.connect(self._path, timeout=BUSY_TIMEOUT_SECONDS))

    def migrate(self) -> None:
        """Runs every pending migration in order, all in one transaction;
        on failure rolls back and raises StateMigrationError."""
        with closing(
            sqlite3.connect(
                self._path, isolation_level=None, timeout=BUSY_TIMEOUT_SECONDS
            )
        ) as connection:
            # The journal mode cannot change inside a transaction; it is stored
            # in the database file, so later connections inherit it.
            connection.execute("PRAGMA journal_mode=WAL")
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

    def set_team_identity(self, identity: TeamIdentity) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO team_identities (team_code, identity) VALUES (?, ?) "
                "ON CONFLICT(team_code) DO UPDATE SET identity = excluded.identity",
                (identity.code, identity.model_dump_json()),
            )

    def team_identities(self) -> dict[str, TeamIdentity]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT team_code, identity FROM team_identities"
            ).fetchall()
        return {code: TeamIdentity.model_validate_json(text) for code, text in rows}

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

    def highlights_for(self, game_ids: Iterable[str]) -> dict[str, Highlight]:
        """The stored highlights of the given games only."""
        ids = sorted(set(game_ids))
        if not ids:
            return {}
        marks = ", ".join("?" for _ in ids)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT game_id, highlight FROM highlights WHERE game_id IN ({marks})",
                ids,
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

    def prune_games(self, before: dt.date) -> None:
        """Deletes every game row dated before `before`, with its final time,
        first-seen flag and attempts; highlights are kept."""
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM games WHERE game_date < ?", (before.isoformat(),)
            )

    def prune_source_cache(self, before: dt.datetime) -> None:
        """Deletes the source cache entries fetched before `before`."""
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM source_cache WHERE fetched_at < ?", (_to_text(before),)
            )

    def prune_past_games(self, before: dt.datetime) -> None:
        """Deletes the past games not touched since `before`."""
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM past_games WHERE touched_at < ?", (_to_text(before),)
            )

    def record_season_team_absence(
        self, team_code: str, season: int, at: dt.datetime
    ) -> None:
        """Records that a team had no object in a season at `at`."""
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO season_team_absences (team_code, season, recorded_at) "
                "VALUES (?, ?, ?) ON CONFLICT(team_code, season) "
                "DO UPDATE SET recorded_at = excluded.recorded_at",
                (team_code, season, _to_text(at)),
            )

    def season_team_absent(
        self, team_code: str, season: int, since: dt.datetime
    ) -> bool:
        """Whether a team's absence in a season was recorded after `since`."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM season_team_absences "
                "WHERE team_code = ? AND season = ? AND recorded_at > ?",
                (team_code, season, _to_text(since)),
            ).fetchone()
        return row is not None

    def prune_season_team_absences(self, before: dt.datetime) -> None:
        """Deletes the season team absences recorded before `before`."""
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM season_team_absences WHERE recorded_at < ?",
                (_to_text(before),),
            )

    def prune_player_identities(self, before: dt.datetime) -> None:
        """Deletes the player identities not touched since `before`."""
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM player_identities WHERE touched_at < ?",
                (_to_text(before),),
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

    def set_player_identity(
        self, player_id: str, body: str, read_at: dt.datetime
    ) -> None:
        text = _to_text(read_at)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO player_identities "
                "(player_id, athlete, read_at, touched_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(player_id) DO UPDATE SET "
                "athlete = excluded.athlete, read_at = excluded.read_at, "
                "touched_at = excluded.touched_at",
                (player_id, body, text, text),
            )

    def touch_player_identity(self, player_id: str, at: dt.datetime) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE player_identities SET touched_at = ? WHERE player_id = ?",
                (_to_text(at), player_id),
            )

    def player_identity(self, player_id: str) -> PlayerIdentityEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT athlete, read_at FROM player_identities WHERE player_id = ?",
                (player_id,),
            ).fetchone()
        if row is None:
            return None
        read_at = _from_text(row[1])
        if read_at is None:
            raise ValueError("player identity has no read time")
        return PlayerIdentityEntry(body=row[0], read_at=read_at)

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

    def touch_feed_build(self, kind: str, feed_id: str, at: dt.datetime) -> None:
        """Sets the time a feed was last served; a feed with no build row gets
        none (it is rebuilt, which creates the row)."""
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE feed_builds SET last_served = ? WHERE kind = ? AND feed_id = ?",
                (_to_text(at), kind, feed_id),
            )

    def last_served(self, kind: str, feed_id: str) -> dt.datetime | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT last_served FROM feed_builds WHERE kind = ? AND feed_id = ?",
                (kind, feed_id),
            ).fetchone()
        return None if row is None else _from_text(row[0])

    def stale_feed_build_ids(self, kind: str, before: dt.datetime) -> set[str]:
        """The ids of the kind not served, built or failed since `before`; a
        build never served ages from its build, a failure-only row from its
        failure."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT feed_id FROM feed_builds WHERE kind = ? AND "
                "COALESCE(last_served, last_build, last_failure) < ?",
                (kind, _to_text(before)),
            ).fetchall()
        return {row[0] for row in rows}

    def failed_feed_builds(self) -> list[FeedBuildState]:
        """The newest failed builds first, at most MAX_FAILED_BUILDS."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT kind, feed_id, last_build, last_failure, "
                "last_failure_reason FROM feed_builds "
                "WHERE last_failure IS NOT NULL "
                "ORDER BY last_failure DESC, kind, feed_id LIMIT ?",
                (MAX_FAILED_BUILDS,),
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

    def set_past_game_dates(
        self, dates: Mapping[str, dt.date], *, at: dt.datetime
    ) -> None:
        """Registers the dates of past games and refreshes their touched time; a
        stored date and players are never overwritten."""
        text = _to_text(at)
        with self._connect() as connection, connection:
            connection.executemany(
                "INSERT INTO past_games (game_id, game_date, touched_at) "
                "VALUES (?, ?, ?) ON CONFLICT(game_id) DO UPDATE SET "
                "touched_at = excluded.touched_at",
                [(game_id, day.isoformat(), text) for game_id, day in dates.items()],
            )

    def touch_past_games(self, game_ids: Iterable[str], *, at: dt.datetime) -> None:
        """Refreshes the touched time of the rows that exist; it adds none."""
        text = _to_text(at)
        with self._connect() as connection, connection:
            connection.executemany(
                "UPDATE past_games SET touched_at = ? WHERE game_id = ?",
                [(text, game_id) for game_id in game_ids],
            )

    def set_past_game_players(
        self, game_id: str, game_date: dt.date, players: str, *, at: dt.datetime
    ) -> None:
        text = _to_text(at)
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT INTO past_games (game_id, game_date, players, touched_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(game_id) DO UPDATE SET "
                "players = excluded.players, touched_at = excluded.touched_at",
                (game_id, game_date.isoformat(), players, text),
            )

    def past_game_players(self, game_id: str, *, at: dt.datetime) -> str | None:
        """The stored players of a past game; finding the row touches it."""
        text = _to_text(at)
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE past_games SET touched_at = ? WHERE game_id = ?",
                (text, game_id),
            )
            row = connection.execute(
                "SELECT players FROM past_games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return None if row is None else row[0]

    def past_game_date(self, game_id: str, *, at: dt.datetime) -> dt.date | None:
        """The stored date of a past game; finding the row touches it."""
        text = _to_text(at)
        with self._connect() as connection, connection:
            connection.execute(
                "UPDATE past_games SET touched_at = ? WHERE game_id = ?",
                (text, game_id),
            )
            row = connection.execute(
                "SELECT game_date FROM past_games WHERE game_id = ?", (game_id,)
            ).fetchone()
        return None if row is None else dt.date.fromisoformat(row[0])

    def add_past_player_ids(
        self, player_ids: Iterable[str], scope: PastPlayerScope, at: dt.datetime
    ) -> None:
        """Registers the player ids learned from a stored past feed; a stored
        id keeps the time it was first learned. Never pruned (ADR 0063)."""
        text = _to_text(at)
        ids = sorted(set(player_ids))
        if not ids:
            return
        with self._connect() as connection, connection:
            connection.executemany(
                "INSERT OR IGNORE INTO past_player_ids "
                "(player_id, scope, learned_at) VALUES (?, ?, ?)",
                [(player_id, scope, text) for player_id in ids],
            )

    def past_player_ids(self, scope: PastPlayerScope) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT player_id FROM past_player_ids WHERE scope = ?", (scope,)
            ).fetchall()
        return {row[0] for row in rows}

    def mark_highlight_searched(
        self, kind: str, target_id: str, at: dt.datetime
    ) -> None:
        with self._connect() as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO highlight_searches "
                "(kind, target_id, searched_at) VALUES (?, ?, ?)",
                (kind, target_id, _to_text(at)),
            )

    def highlight_searched(self, kind: str, target_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM highlight_searches WHERE kind = ? AND target_id = ?",
                (kind, target_id),
            ).fetchone()
        return row is not None

    def take_highlight_search(self, day: dt.date, cap: int) -> bool:
        """Counts one search for the day and returns True, or returns False
        without counting once the cap is reached. Earlier days are deleted."""
        text = day.isoformat()
        with self._connect() as connection, connection:
            connection.execute(
                "DELETE FROM highlight_search_counts WHERE day < ?", (text,)
            )
            before = connection.total_changes
            connection.execute(
                "INSERT INTO highlight_search_counts (day, searches) VALUES (?, 1) "
                "ON CONFLICT(day) DO UPDATE SET searches = searches + 1 "
                "WHERE searches < ?",
                (text, cap),
            )
            return connection.total_changes - before > 0

    def highlight_searches_on(self, day: dt.date) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT searches FROM highlight_search_counts WHERE day = ?",
                (day.isoformat(),),
            ).fetchone()
        return 0 if row is None else int(row[0])
