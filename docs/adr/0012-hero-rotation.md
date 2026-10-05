# 0012. Hero rotation

- Status: Accepted
- Date: 2026-10-05

## Context

ADR 0007's "Hero" says the hero rotates through every game of the day, so the
feed carries the stars of every game. The owner decided in #60 that games
that will not be played that day do not belong in the hero.

## Decision

- The hero rotates through the games of the day that are not postponed or
  canceled, in feed order.
- Postponed and canceled games stay in the schedule list.
- With none left, the hero shows no game, as with no games.
- Delayed games stay in the rotation.
- The rule lives in the front end's props layer (`toHomeView` in
  `web/src/lib/feed/props.ts`), never in the backend.

## Consequences

- The feed contract does not change, and the feed still carries the stars of
  every game.
- Refines the "Hero" of ADR 0007 without superseding it as a whole. ADR 0007
  is not edited.
