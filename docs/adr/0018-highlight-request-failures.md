# 0018. Highlight request failures

- Status: Accepted
- Date: 2026-10-06

## Context

A failed request used up a highlight attempt, and one outage of the video
source spent an attempt on every due game at once, leaving them without
highlights for good. Raised in #97.

## Decision

A highlight attempt is used up when the lookup ends in any way other than a
failed request. A failed request is a timeout, a transport failure or an
error status, on the uploads listing or on a thumbnail check. It uses up no
attempt, is logged with its reason and recorded as the job's failure, and the
same attempt is retried no sooner than 10 minutes after the failure, and not
before its slot.

Every other failure uses up the attempt as before: a body that is not JSON,
an invalid payload, a missing setting, and a matched video without a served
thumbnail. An error status from the image host means "not served" and is not
a failed request.

## Consequences

- Refines the highlight attempts of ADR 0010 without superseding it.
- The schedule (1, 2, 3 hours; 0, 1, 2 for a game first seen final) and the
  stats attempts do not change.
- The wait lives only in memory, so the first run after a restart may retry
  sooner.
- During a long outage a game is retried every 10 minutes while it is due,
  one request per page read, against the API quota of ADR 0015.
