# 0030. Cup nav link

- Status: Accepted
- Date: 2026-10-13

## Context

Issue 207, Decision 2, puts the Cup link on the nav of every page. Principle 5
of `docs/architecture.md` lets a seasonal section touch the core only through
the nullable marks on core feeds (ADR 0028). The nav is a core component, so
the link needs a recorded exception, and threading its href through every page
component would spread the Cup across the core.

## Decision

- **Nav link**: a seasonal section may add one link to the core `NavRow`. The
  link resolves its own route inside `NavRow`, so no href is passed through any
  other component or route.
- **Shared component variants**: a seasonal section may add its own size
  variants to a shared component (`TeamMonogram` gets `cup-draw` and
  `cup-champion`).
- **Feed modules**: the section's setting, loader and poll interval live in the
  shared feed modules (`env.ts`, `feed/config.ts`, `feed/load.ts`,
  `feed/poller.svelte.ts`), as every page's do.

## Consequences

- Removing the Cup also removes the `NavRow` link and the `'cup'` page value,
  the two monogram sizes and those feed module entries. It touches no other
  core component or route.
- A future seasonal section's nav link follows the same rule.
