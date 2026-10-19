# 0066. Cut read amplification of on-demand builds

- Status: Accepted
- Date: 2026-10-19

## Context

Issue 299 and findings B1 to B6, B8 and G4 of the audit of commit 2927a09.
Several on-demand builds read more than they need: the current playoffs build
read every scoreboard day of both windows at 30 seconds of freshness, the
season playoffs build read five leaders per category and every award winner
under a budget that grew while it ran, the Cup build read 30 schedules at 1 hour,
team info was read every hour for a color that changes yearly, the team feed read
six Cup group tables at any date, a season player request for a player with no
season built and registered games, the day feed check and the past game detail
check read stored files on every request, and the standings and search builds
declared no budget.

This replaces decisions in force: the five leaders and the extendable budget of
ADR 0061, the team feed's Cup group table reads of ADR 0028, and the 1 hour
freshness of team info, team schedules and past scoreboard days of rule A
(ADR 0020).

## Decision

- **Current playoffs.** A scoreboard day before today is read through the source
  cache fresh for 7 days, or from the latest final time of a postseason game of
  that day when that is later (the final games of the games job with a
  postseason mark and every game of the stored feed). Today and later days keep
  the scoreboard's 30 seconds. The build runs in two budgeted phases, none of
  which extends a budget: `WINDOW_READS` (2) for the season types, then the day
  count plus `OTHER_READS` (60) for the rest, at most four reads in flight.
- **Season playoffs.** `READ_BUDGET` is one constant, 142: 63 reads, 27 leader
  identities (the top three of nine categories) and at most 52 award winner
  identities. 52 is the maximum of distinct winners the awards table can give: 12
  single-winner awards, the Cup All-Tournament team (5), All-NBA 3 x 5,
  All-Rookie 2 x 5 and All-Defensive 2 x 5. A further winner, as in a tie, is
  shown with a dash and no photo, is not read, and one warning is logged.
  `ReadBudget.extend` is removed. `BUILD_VERSION` is unchanged.
- **Cup.** A team schedule is fresh for 24 hours, except a team with a game
  today in the games job's shown games, which keeps 1 hour. Before the games
  job's first run every team keeps 1 hour. The build declares a budget of 44 that counts reads only: 6
  group teams, 6 group tables, 2 conference tables and 30 schedules.
- **Team info** is fresh for 24 hours. The standings build declares a budget of
  32 (2 division standings with the request of rule L and 30 team infos) and the
  search build 33 (the same plus 1 league injuries read).
- **Rate limits.** A budget has the option `stop_on_rate_limit`, true by default.
  The current playoffs, Cup, standings and search builds set it false: their budget
  enforces the read count only, and a rate-limited read fails as an ordinary
  one, so a team info, leaders or awards read still nulls only its part, as
  before, and a rate-limited Cup schedule read is still skipped under the
  existing rule. The past builds and the other budgeted builds keep the
  stop: a rate limit stops the build and nothing is stored.
- **Team feed.** The six Cup group tables are read only inside the Cup window,
  from the first Cup game (November 1 until the stored Cup feed knows it) to
  December 31 of the first calendar year of the season, and while the stored Cup
  feed is not complete. Otherwise the Cup mark comes from the stored Cup feed.
  The Cup section gives the team feed this through an injected provider
  (`CupTeamMarks`, wired in `main.py`), as it gives the titles.
- **Season player.** An id whose build finds no season game log, or no season
  row in either career stats read, is unknown: nothing is stored, no game is
  registered, the id is remembered in memory and answers 404 without another
  build. A stored feed with an empty game log is not kept and the cleanup deletes
  it. The issue's "the season calendar shows no game" is read as "the season game
  log the build already reads names no season", which adds no read.
- **Day feed.** `check` takes the shown days from the games job's memory
  (`GamesJob.shown_days`) and reads the stored games feed only before the job's
  first run.
- **Past game detail.** The index of final games by day feed is built once at
  startup and fed by a new optional `FeedKind.after_publish` hook whenever a day
  feed is published; a lookup reads no file.

## Consequences

- Stored past playoffs keep five leaders until rebuilt for another reason.
  Bumping the version would spend about 142 reads per stored season, the opposite
  of this change. The model allows up to five, so the web is unaffected.
- A color or arena change shows up to a day late on the standings, search,
  playoffs, team and All-Star feeds, and a Cup schedule of a team with no game
  today up to 24 hours late.
- The Cup section's mark reaches the team feed through an injected provider, a
  new qualification of principle 5: removing the Cup section removes
  `CupTeamMarks` and its line in `main.py`, and the team feed's `cup` is then
  null.
- `ReadBudget.extend` leaves the principle 5 list. The other budgeted builds are
  unchanged.
- No feed model changes: no schema or TypeScript regeneration.
