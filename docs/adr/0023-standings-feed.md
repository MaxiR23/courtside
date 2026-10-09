# 0023. Standings feed

- Status: Accepted
- Date: 2026-10-09

## Context

The `/standings` page of `docs/design-standings-search.md` needs a feed.
Standings had no job and no cadence. ADR 0020 adopts rules A to K and is not
edited. ADR 0021 set the precedent for feeds built on demand and their
expiry.

## Decision

- `/feeds/standings.json` is built on demand under rule G and served under
  rule H through the on-demand cache. Its expiry is set in rule G.
- The feed is stored as one feed with the fixed id `league`.
- Colors come from team info, one read per team through the source cache, and
  are null on failure.
- `state` is `final` on the rule L fallback or when every team has 82 games,
  and `regular` otherwise.
- The adapter maps `vsdiv`, `vsconf` and `clincher`. An unknown clincher is
  null and logged.

## Consequences

- A standings request with a cold cache costs 1 or 2 standings reads plus 30
  team info reads, cached for an hour.
- A failed read with nothing stored answers 503.
- No scheduled standings job exists.
