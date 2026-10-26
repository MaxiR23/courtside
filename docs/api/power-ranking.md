# Power ranking feed

The power ranking of the 30 teams for the current regular season, with every value ready
to draw.

## Schema

`api/schemas/power-ranking.schema.json`, generated from the models in
`api/app/feeds/power_ranking.py` by `scripts/contract.sh`. When this page and the models
disagree, the models win. The feed is decided in
[ADR 0075](../adr/0075-power-ranking-feed.md) and served at `/feeds/power-ranking.json`.

This page holds the planned contract; the implementing issue keeps it exact.

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
| `PowerRankingTeam` | `rank` (1 to 30), `tied`, `team`: `PowerRankingIdentity`, `record` (such as `3-1`), `rating` (signed text with the minus sign U+2212), `ratingNegative`, `offense`, `defense` (signed texts), `projected` (such as `54-28`), `playoffs`, `title` (display texts such as `>99.9%` or `<0.1%`), `playoffsLow` (under 10%), `titleShare` (0 to 1, the title chance over the top team's) |
| `PowerRankingIdentity` | `code`, `name`, `city`, `logo` (null), `accent` (resolved color, null) |

## Rules that live in the code

- `available` only when today (US Eastern) is between the regular season start and end
  and the regular-season run has 30 teams, each with a non-empty rating. Otherwise
  `unavailable`, with no teams and no index read.
- Only the regular-season run is kept. The provider `rank` is never used; a negative
  rating rank is a tie (absolute rank plus `tied`).
- The numeric team id maps to a team code through the teams module; no team read.
- `titleShare` of the top team is 1.

## Refresh

On demand. Rebuilt at the first US Eastern day change after the build.

## Read budget

2 reads (pages of 25). The URL is the Settings template `power_index_url`
(`{season}` and `{page}`).
