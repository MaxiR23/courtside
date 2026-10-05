# 0010. Final game attempts

- Status: Accepted
- Date: 2026-10-05

## Context

A final game's detail (top performers and team stats) was retried every 5
minutes in memory, and the games feed was rejected as a whole while a final
game lacked it. A game already final when first seen had no final time, so
its highlights were never attempted. Raised in #70.

## Decision

- A final game's detail is fetched when it becomes final; after a failure,
  at 2, 4 and 6 hours after the final time, never after. Failed attempts are
  stored in the job state.
- The feed carries `statsAvailability` on final games: `available`,
  `pending` while attempts remain, `unavailable` after the last one failed.
  `leaders` and `teamStats` are null unless `available`. The feed is no
  longer rejected for a final game without its detail.
- A game already final when first seen gets the moment it is first seen as
  its final time. A stored final time is never overwritten.
- Such a game's highlight attempts run right away, 1 and 2 hours later. A
  game seen going final keeps 1, 2 and 3 hours.

## Consequences

- Replaces the 5-minute retry.
- Refines the "Cadences" of ADR 0007 for final games without superseding it
  as a whole.
- Retention of final times and attempts is a separate decision.
- Details live only in memory: after a restart, a game that had its stats is
  refetched at its next slot.
