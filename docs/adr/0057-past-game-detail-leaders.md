# 0057. Past game detail leaders

- Status: Accepted
- Date: 2026-10-17

## Context

Issue 277. The day page card of a past game shows the leader of each team and
its team stats. ADR 0054 says the day feed sends them null and the page reads
them from the game detail of the game. The game detail feed had the team stats
and no leaders (finding 45). The web cannot choose a leader from the box score:
the front end only draws and holds no business rule about games (principle 2),
and ADR 0009 puts the leader rule in the API.

## Decision

- **A new field.** `GameDetailFeed` has `leaders: Leaders | null` (default
  null), the same `Leaders` and `Leader` models as the games feed: `away` and
  `home`, each with `playerId`, `displayName`, `teamCode`, `photoUrl`,
  `points`, `rebounds` and `assists`, the last three nullable (ADR 0055).
- **Filled only by the past build.** `fetch_past_game_detail_sections` sets it
  through the existing `_leader` (the rule of ADR 0009: points, then rebounds
  plus assists, then the first in the provider's order; a missing value counts
  as 0 for the order only), inside the block that builds the box score. The
  current path (the games job, the live refresh, the current game detail
  builder) never sets it, so the current game detail feed always serves
  `leaders: null` and the current season's live feeds are unchanged.
- **No new failure.** When a side has no row with a stat line, the leaders are
  null and the build still succeeds. The check is made before calling
  `_leader`. The leader reads the rows the box score kept, so a row with no
  player id is skipped and logged once (ADR 0055).
- **Past finals feeds.** The season playoffs Finals feed also reads
  `fetch_past_game_detail_sections`. It reads named fields of the sections and
  never `leaders`, so it is unchanged. The leaders are computed from rows
  already in memory, with no extra source request.
- **Stored past game details.** A stored past game detail whose JSON has no
  `leaders` key was built before the field and is stale: it is rebuilt on its
  next request (`"leaders" in feed.model_fields_set` is false). That request
  waits for the rebuild, as a missing feed does, so the day card's first read
  already carries the leaders; when the rebuild fails or runs past the wait, the
  stored body is served as it is.
  One with `"leaders": null` and the current build version is fresh. The
  builder always writes the key.
- **A league leader has a photo.** The rule the games feed already has: a league
  side's leader has a photo (a league player's photo comes from the template; a
  guest player only has the box score headshot, if any). A guest side's leader
  keeps the provider's team code, as in the games feed.
- **The game page draws no leaders block.** `docs/design-past-dates.md` names
  none for the past game page. The field serves the day cards, which read it on
  their first expand.

## Consequences

- The game detail schema and the generated web types change (one nullable
  field, with a default, so every stored current and past feed stays valid).
- A stored past game detail is rebuilt once on its next request: one summary
  read through the source cache. `SEASON_BUILD_VERSION` stays 3: raising it
  would rebuild every kept past feed and read again every stored past game
  players body (about 1,300 summaries for one cold past playoffs build, ADR
  0054), the source load ADR 0056 was written to limit, for one field of one
  kind.
- This ADR supersedes ADR 0041 for the list of past game detail blocks only
  (`leaders` joins the blocks the past build fills) and ADR 0053 for the
  staleness of a stored past game detail only (a second condition besides its
  `buildVersion`). ADR 0054 is not contradicted: its rule that the day card's
  leaders are read from the game detail is true with this field.
- The current game detail feed and the game page have no leaders.
