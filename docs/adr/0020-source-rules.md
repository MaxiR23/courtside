# 0020. Source rules

- Status: Accepted
- Date: 2026-10-08

## Context
ADR 0019 refreshes every game detail feed on a fixed schedule, whatever the
number of visitors, and ADR 0007 and ADR 0014 set refresh cadences per job.
Player and team feeds (ADR 0021) would multiply the source requests if built
the same way: hundreds of players and 30 teams, almost all of them unseen for
days. The source has to be asked as little as possible, and nobody should be
served older live data than before.

## Decision
- `docs/source-rules.md` is adopted. Its rules A to K apply to every job and
  feed build: games, game detail, player and team.
- The rules are: one shared source cache by URL (A), presence (B), live games
  (C), final games (D), fixed-time work (E), stars (F), on-demand builds (G),
  serving (H), unknown ids (I), restart and cleanup (J) and cache headers (K).
- The references behind the rules are:
  - RFC 5861: `stale-while-revalidate` and `stale-if-error`.
  - The Python 3.14 `asyncio` documentation: a strong reference to every
    created task, `asyncio.wait_for` cancelling the awaited task unless it is
    wrapped in `asyncio.shield`, `asyncio.Semaphore` with `async with`, and
    primitives that are not thread-safe.
  - Cloudflare's Origin Cache Control documentation: `s-maxage` disables
    `stale-while-revalidate`, and "Always Online" ignores it.
- This ADR supersedes ADR 0019. The route decision of ADR 0019 stays in
  force under this ADR: `/game/{id}` is rendered in the browser from the
  fallback page, and its detail feed is served at `/feeds/games/{id}.json`. It supersedes ADR 0007 and ADR 0014 for their
  refresh cadences only; everything else in them stays in force, including the
  star guarantees of ADR 0014.

## Consequences
- The source is asked at most once per URL per freshness window, whatever the
  number of visitors.
- Live data is refreshed every 30 seconds with someone present and every 2
  minutes with nobody present; everything else is built only when requested.
- Feed endpoints build on demand, so they need presence tracking, a shared
  source cache, in-flight build tracking and a build limit.
- The CDN in front of the API must honor the origin's Cache-Control, never add
  `s-maxage` and keep "Always Online" off (`docs/deploy.md`).
