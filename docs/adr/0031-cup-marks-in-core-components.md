# 0031. Cup marks in core components

- Status: Accepted
- Date: 2026-10-13

## Context

Issue 211 draws the nullable `cup` marks of the games, game detail and team
feeds (ADR 0028) on the home game card, the game header and the team header.
ADR 0030 allows a seasonal section only the nav link, shared component size
variants and shared feed module entries, and says removing the Cup touches no
other core component or route.

## Decision

- The marks are drawn by Cup components (`CupMarkTag`, `CupTeamLine`) that
  `GameCard`, `GameHeader` and `TeamHeader` render behind one condition each.
- The props layers of the three core feeds map `cup` through
  `web/src/lib/feed/cup-mark-props.ts` into one nullable view field each
  (`ScheduleGame.cupTag`, `GameHeaderView.cupTag`, `TeamHeaderView.cupLine`).
- `CupTeamLine` resolves `/cup` itself, as `NavRow` does, so no href is
  threaded through other components.
- This extends ADR 0030. It does not supersede it.

## Consequences

- Removing the Cup also removes those two components, that module, the three
  fields and their lines in the three props layers and the three components.
  Nothing else in the core changes.
- A future seasonal mark on a core feed follows the same shape.
