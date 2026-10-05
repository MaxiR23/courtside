# 0009. Game leader selection

- Status: Accepted
- Date: 2026-10-05

## Context

The games feed carries one leader per team in a live or final game. The
adapter took the top scorer and broke every tie by the provider's order, a
rule no decision recorded. It was raised in #46 and decided by the owner in
#60.

## Decision

- The leader is the team's player with the most points.
- A tie on points goes to the tied player with the most rebounds plus
  assists.
- A tie on both goes to the first of them in the provider's order.
- Only players with a stat line count.

## Consequences

- The rule lives in `_leader` in `api/app/sources/game_detail.py`.
- The feed contract does not change.
- It is separate from the star player selection of ADR 0007, which is not
  affected.
