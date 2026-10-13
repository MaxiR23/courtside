# 0029. Cup matchup feed

- Status: Accepted
- Date: 2026-10-13

## Context

Issue 205. The matchup panel and the player card of the `/cup` page
(`docs/design-cup.md`) need, for each bracket slot, the slot's game and, for each
team, its path in the Cup, its injuries and its roster with per game averages,
the starting five and the stat leaders. The Cup feed (ADR 0028) has the bracket
but none of this data, and the six on-demand kinds before it each serve one
shape; one more kind keeps the Cup feed small and the Cup section removable.

## Decision

- **Route and kind**: `/feeds/cup/matchups/{id}.json` has one feed per bracket
  slot, built on demand under rule G and served under rule H, stored as
  `cup-matchups/{id}` (a kind name matches `[A-Za-z0-9-]+`, so it cannot hold a
  slash). The ids are the 7 slot ids of the Cup feed. Any other id answers 404
  with no read, and the endpoint answers 503 before the season is known when
  nothing is stored.
- **Dependency on the Cup feed**: the kind declares the Cup feed as its
  dependency, so the cache builds it first when it is missing or stale. The build
  reads the slot from the stored Cup feed, whose season must be the current one;
  otherwise it fails.
- **Sides**: a side's team is the team of the Cup feed's side, else its projected
  team, else none. A scheduled slot already carries the game's teams on its
  sides. A side with no team has only its label, its rule and `known`; nothing is
  read for it. `projected` is true when the team is the projected one.
- **Header**: the slot's `game` is the Cup game as the Cup feed stored it, so the
  panel and the bracket node never disagree.
- **Reads per team**: the league injuries once, then the roster, the season
  schedule, the season averages and the depth chart of each team, all through the
  source cache. A cold build with two teams costs 9 reads, after the Cup feed.
- **Path**: every Cup game of the team's season schedule by start time, with the
  Cup round and the status; the result and both scores only when final.
- **Roster**: ordered as the team feed orders it, with the team feed's card
  fields (the hometown is `birthplace`) and status, plus the per game points,
  rebounds and assists rounded to one decimal, null for a player without
  averages. Injuries are drawn as the team feed draws them.
- **Starters**: the rank 1 athlete of each of the five positions of the depth
  chart who is on the roster; an athlete at two positions counts once, and a
  missing position marks no one.
- **Leaders**: per stat, every player at the highest rounded average of the
  roster leads; a player without averages never leads.
- **Setting**: `DEPTH_CHART_URL`, a template with `{season}` and `{team_id}`,
  where the team id is the provider's, from the fixed team id table. The chart is
  kept 24 hours under rule A, like a roster.
- **Expiry**: 1 hour after a final game of either team or of its path that
  follows the build, when the Cup feed it read is rebuilt after the build, and 7
  days after the build.
- **Failures**: a failed Cup feed, roster, schedule or injuries read fails the
  build and the stored feed is kept. A failed averages read builds with null
  averages and no leader, and a failed depth chart read builds with no starter.
  `detailAvailable` is set when served and is false in the stored file.

## Consequences

- The Cup section also owns this kind, its module, the depth chart adapter and
  its setting. Removing the section removes them with nothing in the core
  changed except three helpers of the team feed and one of the Cup feed made
  public, which stay.
- The payload shape of `DEPTH_CHART_URL` is part of the contract of the setting
  and is documented in `docs/api/cup-matchup.md`.
- A Cup rebuild expires all 7 matchups.
- A cold matchup costs the Cup build plus up to 9 reads, shared through the
  source cache with the team feeds.
