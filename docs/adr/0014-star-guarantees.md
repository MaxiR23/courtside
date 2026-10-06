# 0014. Star guarantees

- Status: Accepted
- Date: 2026-10-06

## Context
ADR 0007 picks each team's star once a day from its roster and the provider's
season leaders, and runs every job in one task. Raised in #79: the stars job
shared its task with the live refresh and was cut by a run budget, a fresh
start could publish no feed because the games feed needs both stars of every
game, a team whose season leaders were all gone from its roster got no star,
and a star who left the roster was deleted before a new one was picked.

## Decision
- Every published game has both stars.
- The stars job runs in its own task and fetches all due teams concurrently,
  with no run budget. Its fetches never delay the live refresh.
- After a start, the first games feed waits until every team has a star,
  stored or fetched. The games job keeps fetching meanwhile.
- When no player on the current roster is among the season leaders, the
  individual averages of the roster players for the season in use are
  fetched and the same rule (points plus rebounds plus assists, roster order
  on a tie) picks the star. The source is a new setting, `PLAYER_AVERAGES_URL`.
- A team keeps its last known star: a star is only replaced by a newly
  picked one, and a failed fetch never removes it.

## Consequences
- Until a new star is picked, the last known star may be a player who has
  left the roster.
- A fresh start with a team whose fetch keeps failing publishes no feed; the
  failure is retried every 5 minutes and shown in the health report.
- A new variable, `PLAYER_AVERAGES_URL`, is needed for the fallback.
- The feed contract does not change.
- Refines the "Runtime", "Cadences" and "Stars" of ADR 0007 without
  superseding it as a whole. ADR 0007 is not edited.
