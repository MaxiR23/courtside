# 0024. Search feed

- Status: Accepted
- Date: 2026-10-09

## Context

The search overlay of `docs/design-standings-search.md` needs an index of the
teams and the players. The stars job already fetches every roster each day.
ADR 0020 adopts rules A to K and is not edited. ADR 0023 set the precedent
for a single-id feed built on demand.

## Decision

- `/feeds/search.json` is built on demand under rule G and served under rule
  H through the on-demand cache, stored with the fixed id `league`.
- The players come from the roster entries the stars job keeps in memory. The
  build makes no roster request and no per-player request. The teams come
  from the division standings, the injuries from the league injuries and the
  colors from team info, through the source cache.
- Until the stars job has fetched every roster the feed answers 503.
- The feed expires as set in the rule G row: 1 hour after a final game of the
  league that follows the build, when the stars job fetches a roster after
  the build, and 7 days after the build.
- A failed standings or injuries read fails the build. A failed team info
  read gives null colors.
- `divisionRank` is an integer that the page formats.

## Consequences

- A cold build costs 1 or 2 standings reads, 1 injuries read and 30 team info
  reads, cached for an hour.
- The index follows a trade the same day the stars job fetches the roster.
- After a restart the feed answers 503 until the stars job has fetched every
  roster.
