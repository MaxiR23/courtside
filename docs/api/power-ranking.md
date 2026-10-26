# Power ranking feed

The power ranking of the 30 teams for the current regular season, with every value ready
to draw.

## Schema

`api/schemas/power-ranking.schema.json`, generated from the models in
`api/app/feeds/power_ranking.py` by `scripts/contract.sh`. When this page and the models
disagree, the models win. The feed is decided in
[ADR 0075](../adr/0075-power-ranking-feed.md) and served at `/feeds/power-ranking.json`.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

| Field | Type | Meaning | Present |
| --- | --- | --- | --- |
| `season` | season label | Such as `2026-27` | always |
| `state` | `PowerRankingState` | `available` or `unavailable` | always |
| `teams` | `PowerRankingTeam[]` | Ordered by rank; empty when unavailable | always |

## Nested objects

| Object | Fields |
| --- | --- |
| `PowerRankingTeam` | `rank` (1 to 30), `tied`, `team`: `PowerRankingIdentity`, `record` (wins-losses, such as `3-1`), `rating` (signed one-decimal text with the minus sign U+2212, zero unsigned), `ratingNegative` (true only for a negative rating), `offense`, `defense` (signed texts like `rating`), `projected` (the rounded projected wins-losses, such as `54-28`), `playoffs`, `title` (the provider's display texts as sent, such as `>99.9%` or `<0.1%`), `playoffsLow` (the playoffs chance is under 10%, read from its display text), `titleShare` (0 to 1: the title chance over the highest title chance of the 30, the rank 1 team's in the normal case; 0 for every team when that is 0) |
| `PowerRankingIdentity` | `code`, `name` (null: from the cached team info, null when the cache has none), `city` (null: same source), `logo` (null: added when served, [ADR 0068](../adr/0068-shared-team-identity-and-hero-accents.md)), `colors` (null: added when served), `accent` (null: the resolved color, added when served, [ADR 0072](../adr/0072-resolved-team-colors-in-the-playoffs-and-cup-feeds.md)) |

## Rules that live in the code

- `available` only when today (US Eastern) is between the regular season start and end,
  both inclusive, and the regular-season run has exactly 30 distinct teams, each with a
  rank from 1 to 30, a rating, an offense, a defense, a record, a projected record and
  both chances, and every playoffs chance text parses. Anything else is `unavailable`,
  with no teams. Outside the regular season the index is not read.
- Only the regular-season run is kept. The provider `rank` is never used; a negative
  rating rank is a tie (absolute rank plus `tied`). Teams are ordered by rank and a tie
  keeps the provider's order.
- The numeric team id maps to a team code through the teams module; no team read. The
  name and city come from the team info already in the source cache, with no request.
- A failed season type or index read fails the build: the stored feed is kept and served,
  and with none stored the request answers 503. The failure is not retried for 10 minutes.

## Refresh

On demand. Rebuilt at the first US Eastern day change after the build.

## Read budget

1 season type read (the regular season, cached 1 hour and shared with the home and
playoffs builds), then at most 2 index pages: the second only when the first holds 25
items, and no index read outside the regular season. The URL is the Settings template
`power_index_url` (`{season}` and `{page}`); its own query is kept. The payload is a list
of items, each with a season type, a team link carrying the numeric team id and named
stats with a value and a display value; only the items of the regular season are kept.
