# 0061. Past playoffs player identities and Finals MVP averages

- Status: Superseded by 0066 for the past playoffs leader count and read budget only
- Date: 2026-10-18

## Context

Issue 289. A past playoffs feed of 2005 built (ADR 0060) but three blocks came
out empty. The leaders and award winners were named from the Finals box scores
and the stored past game players (ADR 0058), so a player who did not play the
Finals, or whose games were never stored, was left out and the block was null.
The champion's postseason record was null because the champion was picked from the
source's series object, which a 2005 schedule does not send. The past Finals
MVP's averages were null by rule (ADR 0058), though the source holds his
postseason career by season.

## Decision

- **One shared reader of player identities**, `PlayerIdentities`
  (`api/app/jobs/player_identities.py`). The identity of a player is the athlete
  object that `player_draft.fetch_player_athlete` already maps: the name, the
  position and the headshot. The reader keeps one row per player id in the state
  table `player_identities` (migration 9) with its read time. A row younger than
  30 days is used with no read. Any feed can use it; only the past playoffs build
  does today.
- **Misses are read at most eight at once.** The budget gets a second, wide lane
  (`ReadBudget(limit, wide_in_flight=8)` and `wide_reads()`); every other read of
  the build stays at four in flight (ADR 0058).
- **A read that fails gives "—".** Any `SourceError` that is not a rate limit
  gives no identity, and nothing is stored, so the next build reads it again. A
  rate limit (429, 503) is raised and the budget stops the build as before.
- **Leaders and winners are never left out.** The past playoffs build names the
  first five leaders of each of the nine categories and every award winner from
  their identity, or "—" with no photo when it could not be read. A block is null
  only when its source answers 404.
- **A leader's or winner's team is its own team reference.** The leaders adapter
  reads the team link of each leader (`LeaderEntry.team_code`, null when the link
  is absent or is not a league team); an award winner already carried it. A past
  build no longer takes a team from a roster or a box score.
  A leader whose team link is missing or is not a league team fails the past
  playoffs build as an invalid feed, and nothing is stored.
- **The champion's record is the counted Finals winner's.** The champion is the
  only team with four counted wins over the Finals games (ADR 0060), not the team
  of the series object.
- **The budget grows during the build.** The past playoffs budget is 63 reads
  plus 45 leader reads plus one read per award winner. `ReadBudget.extend` adds
  them once the awards are known; a stopped budget stays stopped. The Finals game
  players reads stay in the 63 as a warm-up of the cache the past Finals reads
  within the hour; their result is no longer used.
- **The past Finals reads the MVP's postseason career once.** The read has no
  season (the response lists every season), `averages` stays null, and the MVP's
  games, points, rebounds and assists are his row of the season label, else null.
  The budget becomes 12. A 404 nulls the part; any other failure fails the build.
- **These two kinds take their own build version.** The past playoffs and past
  Finals feeds carry `SEASON_BUILD_VERSION + 1`
  (`season_playoffs_feed.BUILD_VERSION`), through an optional `version` argument
  of `with_build_version` and `is_current_build`. Every other season kind keeps
  `SEASON_BUILD_VERSION`, which stays 3.
- **The current playoffs and Finals feeds do not change.** The shared builder
  takes the identities as an optional input that only the past build sets.

## Consequences

- The stored past playoffs and Finals feeds are rebuilt on their next request,
  with up to 45 plus one read per award winner on a cold identity cache. Other
  kinds are not rebuilt.
- The "—" rule for a name that cannot be read does not depend on the open
  decision on missing data.
- No feed model, JSON Schema or generated type changes.
- Seasonal-only additions to core: `ReadBudget.extend`, `wide_reads`, the
  `player_identities` table and the version argument of the two helpers.
- ADR 0058 is superseded for the names of past playoffs leaders and award
  winners, the past playoffs and Finals budgets, the past Finals MVP's averages
  and the build version of these two kinds only.
