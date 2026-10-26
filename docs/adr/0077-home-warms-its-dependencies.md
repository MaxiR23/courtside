# 0077. The home warms its dependencies and never waits on them

- Status: Accepted
- Date: 2026-10-26

## Context

ADR 0074 builds the Cup, All-Star and playoffs feeds first, inside their windows,
before the home build. A home request then waits on those builds, up to
`MISSING_WAIT_SECONDS` when no home is stored. The Cup feed was built first only
once a Cup feed of the season was already stored, so the Cup items of the home never
appeared until someone opened `/cup`.

## Decision

- The home build makes fresh through the cache only the season calendar (and the
  previous one when it has no earlier day) and the day feed of the last-games day
  outside the games window.
- It warms (ADR 0062: starts a build when the feed is missing or not fresh, and never
  waits) the Cup feed in the regular season window when none of this season is stored
  or the stored one is not complete, the All-Star feed from February 1 to March 7, and
  the playoffs feed from the play-in start to the end of the postseason.
- It reads those three feeds only as stored.
- The home is not fresh once a Cup, All-Star or playoffs build other than the one it
  read is recorded. With no memory of what it read (a feed stored by an earlier
  process), it is not fresh once one is newer than the home's build.
- A stale home is served at once and rebuilt in the background.
- Warming happens only inside a requested home build (rule G). It is not a background
  job or a prewarm (ADR 0065).

## Consequences

- No home request waits for those builds.
- A home built before a dependency is stored lacks only that dependency's items or
  scenario until its rebuild.
- Each dependency build causes at most one home rebuild.
- In the regular season the Cup feed is built from a home request with its own budget
  (44), at most once per Cup expiry.
- It supersedes ADR 0074 for its Cup, All-Star and playoffs dependencies only.
