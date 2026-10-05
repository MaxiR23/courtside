# 0011. State retention

- Status: Accepted
- Date: 2026-10-05

## Context

Nothing in the job state was ever deleted, and the `games` table had no
date, so old rows could not be told apart. Raised in #60. ADR 0010 left
"Retention of final times and attempts" as a separate decision.

## Decision

- The `games` table holds each game's US Eastern date, set on the row's first
  write and never changed.
- With the games job's daily fetch, the final time, first-seen flag and
  failed stats attempts of games dated more than 30 days before the current
  US Eastern date are deleted. A game 31 days old is cleaned, one 30 days old
  is kept.
- Highlights and highlight attempts are never deleted.
- Stars keep one row per team and job health one row per job, replaced on
  every write.

## Consequences

- The cleanup also runs on the first run after a start, and a day whose daily
  fetch keeps failing does not clean until it succeeds.
- A state file written before this change lacks the date column and must be
  cleared: there is no migration.
- The `games` rows themselves are kept, since they hold the highlight
  attempts, so the table grows by one row per game seen.
- ADR 0010 is not superseded.
