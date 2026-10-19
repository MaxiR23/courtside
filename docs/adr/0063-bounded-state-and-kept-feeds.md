# 0063. Bounded state and kept feeds

- Status: Accepted
- Date: 2026-10-19

## Context

Issue 293 and findings D1, D2, D3, D4, G1 and G3 of the audit of commit
2927a09. The state database and the kept feeds only grew: ADR 0011 kept every
`games` row, and the kept feeds were never deleted. SQLite ran in
rollback-journal mode, with concurrent writers from the event loop and the
threadpool.

The decision recorded in the issue's comment: deleting unserved kept feeds must
not make a known past player answer 404.

## Decision

- The state database runs in WAL mode, set by `migrate()`, and every connection
  waits up to 5 seconds on a lock.
- Each game's US Eastern date is still stored with its job state.
- With the games job's daily fetch (and the first run after a start):
  - source cache entries fetched more than 7 days ago are deleted;
  - `games` rows dated more than 10 days before the current US Eastern date (the
    3 days around today plus 7) are deleted, with their final time, first-seen
    flag and highlight and stats attempts;
  - `past_games` and `player_identities` rows not touched in 90 days are deleted
    (touched when written and when found);
  - the stored file and build row of every id of the ten kinds `days`,
    `past-games`, `season-players`, `season-teams`, `season-playoffs`,
    `season-playoffs-finals`, `season-cup`, `season-cup-matchups`,
    `season-all-star` and `calendars`, not served in 90 days (or, never served,
    not built or failed in 90 days), or stored with no build row, are deleted. An
    id with a build in flight is skipped. A deleted feed is built again on its
    next request. A feed's served time is set on every successful answer.
  - Before any file is deleted, `PastPlayerIds` reads every stored file and keeps
    the player ids they name (see below).
- A past game detail build registers its game's date in `past_games`, and a
  request for it touches the row, so its id stays known while its day feed is
  gone.
- Highlights, edition highlights, swept rows and past player ids are never
  deleted. Stars keep one row per team and job health one row per job.
  `PastPlayerIds` writes each player id it learns from a stored past feed (with
  its scope, `known` or `in_season`, and the time it was learned) to
  `past_player_ids`, and reads them back with the stored files after a start. A
  known past player therefore stays known when the feeds that named him are
  deleted. The table holds one row per player and scope ever seen, bounded by
  the league's history.
- The day, past game detail, season Finals and Finals feeds read only the
  highlights of their games.
- `/health` lists at most 50 failed builds, newest failure first.

It supersedes ADR 0011, and ADR 0040, 0041, 0043, 0045, 0046, 0047 and 0053 for
the deletion rules only.

## Consequences

- A day whose daily fetch keeps failing does not prune.
- Current-season expiries are unaffected: `feed_expired` ends every feed 7 days
  after its build, before a 10-day-old final time is gone.
- A past player stays known after the feeds that named him are deleted, and a
  request for him builds his feed again. The `past_player_ids` table only
  grows, by at most two rows per player ever seen. The daily cleanup saves the
  ids of every stored file before it deletes any, so no file is deleted before
  its ids are kept. A player learned before this change and whose files are
  deleted before any cleanup or request reads them is not in the table; this
  cannot happen on the first upgrade, since every file is younger than 90 days
  from the migration.
- A past game whose day feed, row and file are all older than 90 days answers
  404 until its day is requested.
- The highlights backfill no longer targets the games of deleted day, `season-cup` and `season-playoffs` feeds.
- Serving a `season-teams` or `season-players` feed refreshes the touched time of the `past_games` rows of the games it marks with a detail available, one write per serve. A row lives as long as a served page links it, and a page not served in 90 days is deleted with its rows.
- Past builds read team colors only from source cache entries younger than 7
  days.
- The current Finals reads, with the 1-hour freshness, a Finals game whose row
  is gone.
- The state file must be on a local file system, as WAL requires (ADR 0016
  hosting already uses a local Docker volume). WAL adds `-wal` and `-shm` files
  next to the database.
