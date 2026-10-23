# 0071. Playoffs bracket without a camera

- Status: Accepted
- Date: 2026-10-23

## Context

Issue 326. ADR 0034 gave the Cup and playoffs brackets one shared camera: a layer
moved with translate and scale. A scaled layer is rasterized at one size and drawn
at another, so text and borders blur at some browser zoom levels. The playoffs
redesign (`docs/design-playoffs.md`, "Bracket") replaces the zoom levels with a
seven-column map and a vertical tree that fit the screen. ADR 0034 is accepted and
is not edited.

## Decision

The playoffs bracket is a plain grid at 1:1, with no translate and no scale, so it
renders sharp at every browser zoom. The playoffs section stops importing
`web/src/lib/bracket/`. The Cup keeps the shared camera on desktop, and ADR 0034
stays accepted for the Cup.

## Consequences

- The playoffs bracket has no zoom levels, controls or keyboard camera; a series is
  selected by tap and its result shows in a panel below the bracket (1180px and
  wider) or in a bottom sheet (under 1180px).
- The camera module is used by the Cup alone; neither section imports the other.
- The playoffs camera tokens are removed from `docs/design-playoffs.md`.

It narrows ADR 0034 and supersedes nothing.
