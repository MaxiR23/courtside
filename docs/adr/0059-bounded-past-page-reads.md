# 0059. Bounded reads of the past page builds

- Status: Accepted
- Date: 2026-10-18

## Context

Issue 283. ADR 0058 bounded the five past competition builds and left the past
team, player, day, game detail and standings builds with `SeasonRosters`, its
one-at-a-time pacing and `SOURCE_BUILD_PAUSE_MS` (ADR 0056). A cold past team
read one box score per final game and a cold past player read the box scores of
its team too; the day and standings builds read one season team object per side.
None of them declared a limit on what it reads.

## Decision

- **A declared budget per build.** Each of the five builds declares
  `READ_BUDGET`, counted and limited as in ADR 0058 (at most four requests in
  flight, no pause, a 429 or 503 stops the build and `FeedCache` retries after 10
  minutes).
  - Past team, 5: the season team object, the standings and the regular season
    and playoffs schedules, 4 reads sent. The team info is never read: the colors
    come from the cached team info.
  - Past player, 4: the athlete, the game log of the season and the career
    statistics of the regular season and of the playoffs.
  - Past day, 1: the scoreboard of the day.
  - Past game detail, 1: the game summary.
  - Past standings, 1: the division standings of the season.
- **Names from the payloads.** The league sides are named from the names their
  own payload gives the teams, as in ADR 0058: the past scoreboard day
  (`PastScoreboardDay.teams`), the past player game log (`PlayerGameLog.teams`),
  the team schedules (`SeasonSchedule.teams`) and the standings rows
  (`DivisionEntry`). The season code and the historical flag follow ADR 0054 and
  ADR 0055 with "today" taken from the open run of the stored franchise names. No
  build calls `TeamNamesFeeds.season_names`.
- **Colors** come from the cached team info, with no request; a missing one is
  null and the page draws no strip.
- **Nullable blocks.** `TeamFeed.colors`, `leaders` and `roster`, and
  `PlayerFeed.awards`, become nullable. The current feeds still always set them
  (their validators require it), so a stored current feed stays valid. A past
  team feed built from now on has a null roster and null leaders; a past player
  feed has a null number, a null draft and null awards. The page hides a null
  block and its tab without a gap, and shows no draft cell on a past season with a
  null draft.
- **Past player rows** (summary, averages, milestones) come from the two career
  statistics reads, which carry the season's row; no season statistics read, no
  standings, draft or awards read is sent.
- **The past player's team** is named from the stored franchise names run that
  holds the season, for the team of the newest game of the log; it is null with no
  stored list or run. When served, a null team is named from the season's career
  row and the stored runs, with no read.
- **The dates of the final games** of a team are registered from its schedules,
  with no box score read, so every game of the schedule still builds its past game
  detail (ADR 0053).
- **Known player ids** include the players a stored past playoffs feed names
  (leaders and award winners) and a stored past Finals feed names (the MVP and the
  averages), as `PastPlayerIds.known_in_season`, used by the past player kind
  only. An id known from stored past data never waits for the rosters; any other
  id answers 503 until the stars job has fetched the rosters, then 404 with no
  read.
- **Removed.** `SeasonRosters` and `SOURCE_BUILD_PAUSE_MS` (setting,
  `.env.example` and tests).
- **`SEASON_BUILD_VERSION` is unchanged**, as in ADR 0057 and ADR 0058: stored
  past team feeds keep their rosters and leaders, and those rosters still make
  player ids known; stored past player feeds keep their number, draft and awards.

## Consequences

- A first request of a past team, player, day, game detail or standings page
  builds in a few seconds, and a build can no longer grow past its budget without
  a failing test and a log line.
- The team and player schemas and the generated web types change: the fields
  become nullable. A past team page has no roster or leaders block, and a past
  player page has no draft cell, awards block or jersey number.
- Names are the payload's, which may be today's name when the provider sends it
  so; a relocated franchise would then show today's name with the standard code.
  The owner should check one relocated season after deploy.
- `api/.env` must not keep `SOURCE_BUILD_PAUSE_MS`: the settings reject an
  unknown variable, so the deployed file loses that line before the deploy.
- Past team colors are null until a current team page has cached the team info.
- The core `past_player_ids.py` imports no section: `main.py` gives it the
  (kind, reader) pairs of the stored season playoffs and Finals feeds, as in
  ADR 0035 and ADR 0048. Removing the playoffs section removes the readers and
  their line in `main.py`.
- `TeamNamesFeeds.season_names`, `season_identity` and `name_sides` have no caller
  left in the builds and stay for the franchise names kind.
