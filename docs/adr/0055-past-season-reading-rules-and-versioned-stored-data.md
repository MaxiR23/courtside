# 0055. Past season reading rules and versioned stored data

- Status: Superseded by 0059 for the stored past game detail used in place of a past game players body only
- Date: 2026-10-17

## Context

Issue 273. The audit of the past season pages found reading rules that failed a
whole feed for one value the source does not send, season codes that were wrong
for a relocated franchise, and stored data that was never rebuilt when the rules
changed.

- The 2023-24 Cup group stage carries the note "NBA In-Season Tournament - Group
  Play", which the Cup note table did not know, so its group games were not
  counted.
- A tie for the 2nd All-Defensive team gives six winners, and the playoffs feed
  bounded an award at five, so the season playoffs feed and the Finals feed
  built on it failed.
- A box score row with no player id failed the whole summary payload in every
  reader. A box score of a 2004-05 game has no `totalRebounds`, no shooting
  percentage and no minutes or plus-minus column, and ADR 0052 made a missing
  count stat a failure of the build.
- The season code of the 2004-05 Hornets came out as "NOP": the source's "NO"
  was mapped to today's standard code even for an identity whose name differs
  from today's. The player's career rows and the plain-code fields of the past
  playoffs and Finals (leaders, award winners, Finals MVP, finalist records,
  roster averages) had no season code at all.
- The franchise names, the past calendars and the stored past game players
  carried no build version, so a change to the rules did not reach them, and a
  team feed ignored an outdated names list.

## Decision

- The Cup note table has "NBA In-Season Tournament - Group Play" as the group
  round.
- An award has as many winners as the source sends, at least one, ties included.
- A box score row with no player id is skipped and logged once per game read
  ("game detail: game <id> has a box score row with no player id, skipped"), by
  the leaders reader, the sections reader (current and past) and the past
  players reader. A row with an id and no name still fails.
- A team or player stat the source does not send is null in every adapter, never
  a failure: a counted or rated value of a team's or a player's performance (box
  score columns, team statistics, leader values). The fields that identify a
  record (ids, codes, a standings row's wins, losses and seed, the Cup table's
  wins and losses) are not stats and keep failing. A value that is sent and is not
  a number still fails. A leader with a missing points, rebounds or assists column
  keeps ADR 0009's order with the missing value read as 0 for the order only; the
  leader's value is null; with every value missing the first player in the
  provider's order leads. Sums over values with a null are null, orderings read
  null as 0, a "better" or leading side is none when a value is null, and the
  All-Star `teamStats` block is null when any value is null. This supersedes ADR
  0052's "a missing count stat still fails the build".
- The season code of a historical identity (that season's name or city differs
  from today's) is the season team object's abbreviation as the source sends it,
  never mapped to a standard code; an identity whose name and city equal today's
  keeps the standard code. The same rule gives the code of the franchise names
  runs. This supersedes ADR 0054's "the provider code mapped to the standard code
  as in the names runs" for a historical identity.
- Every plain-code field a past feed draws carries `seasonCode`: the playoff
  leader, the award winner, the Finals MVP, the finalist record, the roster
  averages and the past player's team. The core names helper sets it from the
  field's team code, as it sets the sides' codes.
- Every career row of both player feeds carries `seasonCodes` (one entry per team
  of the row, null when no names run holds the season). The codes come from the
  stored franchise names runs, never from a season team read per row, and are set
  when the feed is served, so a rebuilt names list reaches the next served feed
  with no player rebuild. A list that is missing or outdated for a franchise of the
  career is built in the background, with the 10-minute retry window and one build
  in flight (`FeedCache.warm`); the response does not wait.
- The postseason mark of a game carries `awayWins`, `homeWins` and, once the
  series object says it is complete, `seriesWinner`. A complete series of the
  playoffs feed has the wins of both sides. A player's award carries its
  `AwardCode` and team number, from the same name table as the season awards. The
  English `summary` strings stay in the contract.
- The franchise names, the past calendars and the stored past game players carry
  `buildVersion` as the eight season kinds do (ADR 0053). A names list or a past
  calendar of another or no version is rebuilt on its next request; a stored past
  game players body, and a stored past game detail used in its place, of another
  or no version is read again; a team feed, current or past, is stale while its
  stored names list is of another version, which rebuilds the names first.
  `SEASON_BUILD_VERSION` is 3. This supersedes ADR 0043's names "kept 7 days"
  (now also until the version changes), ADR 0053's "a game is read once and kept"
  and "a stored past game detail is reused with no read" (now only for the current
  version) and ADR 0040's kept past calendar (now only for the current version).
- Not versioned, because they hold source facts and no reading rule's product and
  every build re-reads what it draws from them: the stored All-Star editions, the
  game dates of `past_games`, the highlights, the backfill tables, the final
  times and the source cache.

## Consequences

- The schemas of the games, days, game detail, player, all-star, playoffs,
  playoffs finals and calendar feeds change, and so do the generated types. Every
  new field has a default, so a stored current feed stays valid.
- The first request after the deploy rebuilds every kept past feed, every names
  list and every `past_games` body it needs. Source pacing is not part of this
  decision.
- On the first request for a career franchise with no stored names list, the
  career rows show null season codes until its build ends; the web falls back to
  the row's `teams`.
- The web shows "—" for a null stat. Hiding it and using the structured fields
  are a later change.
