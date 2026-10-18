# 0058. Bounded reads of the past competition builds

- Status: Accepted
- Date: 2026-10-18

## Context

Issue 281. The cold build of a past playoffs feed read about 1,300 game
summaries (ADR 0053), and ADR 0056 paced them to one at a time. The pacing
stopped the rate limit but made a first request wait for minutes, and the five
past competition builds (playoffs, Finals, Cup, Cup matchup and All-Star) still
had no declared limit on what they read. The reads are mostly not needed: the
postseason schedules of the teams already carry the games, the series and the
competition types; the Finals box scores name the players of the two finalists;
a past feed needs no team info, roster or per-player statistics read.

## Decision

- **A declared budget per build.** Each of the five builds declares
  `READ_BUDGET`, the most source reads it sends: playoffs 63, Finals 11, Cup 44,
  Cup matchup 2 and All-Star 60. A read is one request that reaches the network
  through `SourceClient`; a cache hit, and a caller that joins an in-flight
  request, are not reads.
  - Playoffs, 63: 1 standings, 20 postseason team schedules, 1 play-in window,
    5 play-in days (the window's Eastern dates, its end included), 1 leaders, 26 awards (the index and up to 25 documents),
    2 finalist records, 7 Finals game details.
  - Finals, 11: 4 (2 records and 2 team statistics) and 7 Finals game details.
  - Cup, 44: 6 group team reads, 6 group tables, 2 conference tables and 30 team
    schedules. No calendar, scoreboard day or game detail.
  - Cup matchup, 2: the schedules of the two teams.
  - All-Star, 60: 1 calendar, 29 February days, 4 game details and 26 awards.
- **Counting is in one place.** `_fetch` of `app/sources/http.py` is the only
  function that sends a JSON request after a cache miss. A `ReadBudget` lives in
  a context variable that `within_budget` sets around a build; the task of each
  read copies the context, so every adapter is counted with no change to its
  signature. A read past the limit raises `SourceError("read budget of N
  reached")` before it is sent, and so does every later read of that build.
- **At most four reads in flight, no pause.** The budget holds a semaphore of 4.
  `SOURCE_BUILD_PAUSE_MS` and the one-at-a-time lock of `SeasonRosters` do not
  apply to these builds (they stay for the past team and player feeds).
- **A 429 or 503 stops the build.** The budget records the stop with the reason
  "rate limited" (ADR 0056), and `within_budget` raises it after the build even
  when the build swallowed it, as the Cup's schedule gather does. The build logs
  `<label> not built: <reason>` and stores nothing; `FeedCache` records the
  reason and retries after 10 minutes (rule H).
- **Playoffs reads.** The postseason schedule of each team that can have played
  a series (per conference the seeded teams in seed order, then the unseeded by
  best record, the first 8 and from 2021 the first 10), which gives every game
  with its competition type and series object, replaces the postseason window,
  the bracket scoreboard days and the 30 rosters. The play-in window and its days
  are still read from 2021. The two finalists' records and the Finals game
  details are read. The Finals pair is the only pair of teams from different
  conferences.
- **Names of leaders and award winners** come from the Finals box scores and from
  the stored past game players of the games the build read. A leader or winner no
  read names is left out; a block left with no one is null, and the page hides a
  null block. An award winner who played no postseason game and is in no Finals
  box score is left out.
- **Team colors** come from the team info the source cache already holds, with no
  request; a team without one has null colors.
- **Past Finals averages.** No read of a past Finals build carries a postseason
  average: `averages` is null (the field becomes nullable; the current feed always
  sets it), and the Finals MVP's `games`, `points`, `rebounds` and `assists` are
  null. `bestGame` still comes from the Finals box scores. The Finals build reads
  no roster and no per-player statistics.
- **Names from the payloads.** The league sides of the past playoffs and Cup are
  named from the names their own payloads give the teams (the standings; the 30
  schedules): the name and city are the payload's, the code and the historical
  flag follow ADR 0054 and ADR 0055 with "today" taken from the open run of the
  stored franchise-names list (the standard code, not historical, without one).
  The past Finals takes the names, codes and flags of the sides of the stored
  season playoffs feed. `TeamNamesFeeds.name_sides` is not called by these builds.
- **The previous All-Star edition** is taken from the stored feed of the season
  before when that one is stored and finished, as the recap and the whole edition
  with its MVP; otherwise it is null. The build reads nothing for it, and stops
  reading February days at the first with All-Star games. The recap depends on
  the previous season's feed already being stored when this build runs. A
  finished past All-Star feed is kept and `SEASON_BUILD_VERSION` is unchanged, so
  a previous edition that is null because of the visit order stays null until the
  version changes.
- **`SEASON_BUILD_VERSION` is unchanged**, as in ADR 0057: raising it would
  rebuild every kept past feed, the past team, player, day and game detail feeds
  included, and read again every stored past game players body. Stored feeds of
  these five kinds stay served as they are.

## Consequences

- The seasonal-only additions to core adapters are additive and the core does not
  use them: `SeasonSchedule.teams` and `season_schedule_url`,
  `DivisionEntry.abbreviation`, `cached_team_info`, `SeasonTeamName`, and
  `ReadBudget` and `cached_json`.
- A first request of a past season builds in a few seconds, and a build can no
  longer grow past its budget without a failing test and a log line.
- The finals schema and the generated web types change: `averages` becomes
  nullable, so every stored feed stays valid. The page hides the averages table
  when it is null.
- Past Finals pages show no postseason averages table and the Finals MVP's
  average figures as dashes. A stored past Finals feed built before this change
  keeps its averages until it is rebuilt.
- A past playoffs build that the provider's team schedule does not give the
  series object or competition type for fails as not complete and stores nothing;
  the owner should confirm one real past season after deploy.
- Colors are null when no team info was ever cached; award winners who played no
  postseason game may be missing.
- `SeasonRosters`, its wiring for the team and player feeds and
  `SOURCE_BUILD_PAUSE_MS` stay until a later issue.
- ADR 0033 is not superseded: the current Finals feed keeps sending `averages`.
