# 0076. Coming up links to the seasonal pages

- Status: Accepted
- Date: 2026-10-26

## Context

The home with no games (ADR 0074) lists Opening Night, the Cup stages, All-Star,
Play-In, Playoffs, Finals and the preseason in its Coming up card. Each Cup, All-Star
and playoffs item links to its page. ADR 0030 lets a seasonal section link only from
`NavRow`, which resolves its own route so no href is passed through any other
component or route. A link from the home is a new qualification of that decision.

## Decision

The home's `ComingUp` component may link to the Cup, All-Star and Playoffs pages. It
resolves those three routes itself, in one record in `ComingUp.svelte`, as `NavRow` and
`CupTeamLine` do, so no href goes through any other component or route. The mapping
from a `comingUp` key to its title, sub line and link target lives in
`web/src/lib/feed/home-props.ts`.

## Consequences

Removing a section also removes its entry in that record and the link targets of its
keys in `home-props.ts`. Its items, if the feed still sent them, show with no link. No
other core component or route is touched. This extends ADR 0030 and replaces nothing
in it.
