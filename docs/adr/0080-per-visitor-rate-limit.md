# 0080. Per-visitor rate limit in the API

- Status: Accepted
- Date: 2026-10-27

## Context
Since ADR 0079 the API is reached only through the front door, but one
visitor can still send unbounded feed requests. Raised in #388.

## Decision
- `RATE_LIMIT_PER_MINUTE` (default 120, 0 turns the limit off) limits every
  `/feeds/*` route. Request `limit + 1` inside a visitor's 60-second window,
  which starts at its first request, answers 429 with `Retry-After` in
  seconds. `/health` is never limited.
- The visitor is the first address of `x-real-ip`, else the connection's
  client address. Vercel forwards the visitor's address in `x-real-ip`
  (verified by the owner).
- The limiter is in the process, with no dependency and no external store
  (one process, ADR 0016). Expired windows are dropped, at most 10,000
  visitors are tracked, and the oldest window is evicted at the cap.
- Addresses are in memory only: never logged, stored or put in a feed.
- A refused request does nothing else: it does not record presence, so a
  flood cannot hold the games job at its "someone present" cadence.

## Consequences
- The key is trustworthy because Caddy refuses requests without the origin
  secret (ADR 0079), so only the front door can set `x-real-ip`.
- A restart clears the windows. An evicted visitor gets a fresh window.
- A request without `x-real-ip` is keyed on its connection address. Locally
  that is the caller. Behind Caddy it is the proxy's address, shared by every
  visitor, so if the front door does not deliver `x-real-ip` the limit acts
  as one global limit; `RATE_LIMIT_PER_MINUTE=0` turns it off.
- It extends rule H of `docs/source-rules.md`. ADRs 0016, 0062 and 0079 are
  not edited.
