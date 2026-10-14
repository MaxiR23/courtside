# 0037. Shared count-up

- Status: Accepted
- Date: 2026-10-14

## Context

The playoffs champion hero counts its stats up from zero. The All-Star hero
(issue 231) counts its stats the same way. The All-Star section may not import
from the playoffs section, or removing the playoffs would break it (ADR 0030,
ADR 0034).

## Decision

- `web/src/lib/count/` holds `count.ts` (the text counted by a progress) and
  `count-up.svelte.ts` (the `CountUp` controller), moved from
  `web/src/lib/playoffs/` with their tests, with no change of behavior.
- Neither section imports the other. Both import `#lib/count/`.
- The corner marks of the All-Star frames are a size variant of
  `BlueprintFrame` (`marks="allstar"`), as ADR 0030 allows. Without the prop
  the frame draws what it drew before.

## Consequences

- Removing one section leaves the module to the other. Removing both removes
  `web/src/lib/count/` too.
- A future hero that counts its numbers takes the controller from the same
  module.
