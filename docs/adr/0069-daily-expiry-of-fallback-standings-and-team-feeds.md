# 0069. Daily expiry of fallback standings and team feeds

- Status: Accepted
- Date: 2026-10-23

## Context

A standings or team feed built with the rule L fallback (ADR 0022) before the
regular season opens shows the last regular season. With no final game seen by
the server, it waited up to 7 days to switch to the new season.

## Decision

Such a build records the fallback with its build in the state store
(`feed_builds.fallback`, migration 14; standings: the division standings
fallback; team: that or the previous season's leaders). The feed also expires at
the first `DAILY_FETCH_TIME` in US Eastern strictly after the build; the
earliest trigger wins. It is checked on request: no setting, no background work.
A build without the fallback, and a stored row from before (no record), keep the
current rule.

## Consequences

- In the preseason and postseason the standings feed and each requested team feed
  are rebuilt at most once more per day (32 and 15 reads under their budgets,
  most from the source cache).
- The player, search, Cup and playoffs feeds and past seasons are unchanged.
- No feed field changes, so no types are regenerated; one state migration.
