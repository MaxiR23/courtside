# 0078. Power ranking names from the stored standings feed

- Status: Accepted
- Date: 2026-10-26

## Context

The name and city of a power ranking team came only from the cached team info. A feed
built before that cache held a team kept null names for the whole US Eastern day, and
the page showed the code.

## Decision

- Name and city come as a pair from the stored standings feed of the current season
  (read from disk, no request), else from the cached team info, else null. There is no
  new source read.
- The build warms the standings feed (ADR 0062: starts a build when missing or not
  fresh, and never waits) only when it has teams to name and no standings feed of the
  season is stored. It never builds or awaits it. The warm happens only inside a
  requested build (rule G), as in ADR 0077.
- A feed with any null name is fresh for 1 hour after its build, then served at once
  and rebuilt in the background. A feed with every name stays fresh until the first US
  Eastern day change.
- This ADR replaces ADR 0075 for its freshness only.

## Consequences

- Once the standings feed is stored, names fill in on the first rebuild after the
  power ranking feed is 1 hour old. The hour runs from the power ranking build, not
  from the standings store. The request that starts that rebuild is still served the
  feed with null names, and later requests get the names.
- While names are null, each rebuild reads 1 season type and up to 2 index pages, both
  cached 1 hour by their adapters, so the budget per build does not change. A standings
  build warmed from here keeps its own budget (32).
