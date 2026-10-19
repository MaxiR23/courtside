# 0062. Bounded upstream reads and on-demand builds

- Status: Accepted
- Date: 2026-10-19

## Context

Issue 291 and findings C1, C2, C3 and G2 of the audit of commit 2927a09.
Reads that run under no budget had no client-wide limit. A rate limit stopped
only the build that met it, so every other caller kept sending requests. The
feed cache had no bound on started builds and none on the time of a build.

## Decision

- **At most eight requests of the shared client are in flight at once**, budgeted
  or not. A budgeted read takes its build's budget slot first and the client slot
  inside it.
- **A 429 or 503 answer pauses every request of the client.** The pause lasts the
  `Retry-After` of the answer (seconds or an HTTP date), 60 seconds when it is
  missing or unreadable, and at most 15 minutes. A paused read raises "source
  paused" and sends no request; a fresh cache entry is still served. The start of
  a pause is logged once, without the URL. A later 429 or 503 only extends it.
- **At most 16 builds are started at once** (running, waiting for a slot or for a
  dependency). A missing feed requested at the cap answers 503 and starts nothing.
  A stale feed is served from storage with no build. A refresh, a warm-up and a
  dependency start nothing; a dependency is used as stored.
- **A build runs at most 60 seconds.** A build past it is cancelled and recorded as
  a failure with the reason "build timed out".
- **A paused read is a rate limit for `is_rate_limited`**, so a budgeted build
  stops as "rate limited" (rule O), and it is a failed request (`request_failed`),
  so a highlight attempt is not spent (ADR 0018).

It supersedes no ADR.

## Consequences

- While the client is paused the games job, the stars job and the live refresh
  fail their reads and keep the last valid feed. Scores can be up to 15 minutes
  old after a long `Retry-After`.
- A missing feed requested at the cap answers 503 and the front end keeps polling
  (rule H).
- A `warm` call past the cap is skipped until a later call.
- A build past 60 seconds is retried after the 10-minute window of rule H.
- A 429 or 503 on a thumbnail HEAD also pauses the client.
- The wide lane of ADR 0061 still allows eight reads, but shares the eight client
  slots with every other read.
- ADR 0058's "no pause" still holds between budgeted reads: the new pause starts
  only after a rate-limit answer.
