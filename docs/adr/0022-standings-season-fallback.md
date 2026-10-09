# 0022. Standings season fallback

- Status: Accepted
- Date: 2026-10-09

## Context

In the preseason the division standings response is not of the regular
season, and the standings adapter failed every team and player feed. Rule L
of `docs/source-rules.md` was written for this, but ADR 0020 adopts only
rules A to K and an accepted ADR is not edited.

## Decision

Rule L of `docs/source-rules.md` is adopted.

- The division standings adapter reads the season and the season type of
  each response. When it is not of the regular season, it makes one extra
  request: a preseason year Y reads `season=Y-1`, a postseason year Y reads
  `season=Y`. At most one extra request is made.
- Each URL, with its added query, is cached under its own key per rule A.
- A fallback response that is not of the regular season fails.
- The team feed labels its record with `record.season`. Its streak, games
  behind and seed may be null.

## Consequences

- In the preseason two URLs are cached per hour instead of one.
- A stored team feed without `record.season` is rebuilt.
- The configured `DIVISION_STANDINGS_URL` must select the regular season;
  otherwise a postseason fallback repeats the postseason and fails.
- ADR 0020 is unchanged: it keeps rules A to K.
