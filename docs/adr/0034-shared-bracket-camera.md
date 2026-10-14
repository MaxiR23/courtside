# 0034. Shared bracket camera

- Status: Accepted
- Date: 2026-10-14

## Context

The playoffs bracket (issue 223) pans and zooms like the Cup bracket: the
same view math, the same geometry helpers and the same layer that writes
`style.transform`. The playoffs section may not import from the Cup section,
or removing the Cup would break it (ADR 0030).

## Decision

- `web/src/lib/bracket/` holds the camera view math, the geometry and
  `CameraLayer`, shared by the Cup and playoffs brackets.
- Neither section imports the other. Both import `#lib/bracket/`.
- `#lib/cup/camera.ts` re-exports the shared functions, so the Cup imports do
  not change.

## Consequences

- Removing one section leaves the module to the other. Removing both removes
  `web/src/lib/bracket/` too.
- A future bracket takes its camera from the same module.
