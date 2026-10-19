# 0065. Background work limited to games, highlights and stars

- Status: Accepted
- Date: 2026-10-19

## Context

Issue 297 and the background-work findings of the audit of commit 2927a09. Five
scheduled tasks ran for a feed that is built on request: the games job, the
highlights job, the stars job, the All-Star discovery job and the highlights
backfill. The discovery and the backfill read the scoreboard and the channel
uploads daily whether or not anyone asked, a game past its start was checked
every minute with nobody present, the highlights job read SQLite several times
per game on every tick, a restarted stars job fetched every roster again, and
the franchise names were rebuilt in full every 7 days and started in the
background by a player feed.

This replaces four decisions in force: the discovery job of ADR 0036, the daily
backfill of ADR 0048, the 7-day franchise names of ADR 0055, and the final
builds, the stars cadence and the All-Star cadence of rule D, rule E and rule F
(ADR 0020).

## Decision

At startup only the games, highlights and stars jobs are scheduled.

- **Start check.** A game still scheduled past its start is checked every
  `START_CHECK_INTERVAL` (1 minute) when someone is present or a request asked,
  and every `NOBODY_INTERVAL` (2 minutes) when nobody is.
- **Highlights state in memory.** The highlights job reads each game's final
  time, first-seen flag and attempts once and keeps them in memory, updated on
  every write. A tick reads no SQLite for a game already seen. The entries of
  games that left the final games are dropped.
- **Stars.** The daily mark is the job's own last success, read at start; a
  failure does not count. A restart on a day already fetched calls no fetch
  function and sends no request: the rosters are read from the source cache
  (`team_players.cached_roster`), and a team with none cached is fetched as a
  pending team. At most 4 source reads are in flight (`READS_IN_FLIGHT`). A
  failed team is retried 5 minutes after it failed, one failed team per run.
- **All-Star edition.** The All-Star feed finds its edition itself. With no
  stored edition, the build reads the season calendar and tries the days of the
  calendar from February 1 to March 7 of the end year: the days next to the
  longest run of days without games first, Sundays first among equals, at most
  6 days, and stores the first with All-Star games. The previous edition is found
  the same way from its own calendar. A candidate day equal to today is read
  with the scoreboard freshness of 30 seconds, the others with 24 hours. A feed
  built before the edition is fresh for 24 hours.
- **On-demand highlights search.** A final game served with no highlight once
  its live attempts are over, a past game detail served with none and an
  All-Star edition served past its video window with none start one search of
  the channel by query, in the background, so the response is never delayed. The
  game query is the away team, the home team, "full game highlights" and the
  date; the edition query is "All-Star Game", the year and "full game
  highlights". The first result in the provider's order whose title matches and
  whose thumbnail the image host serves is stored. A search that finds none
  stores a mark and the target is never searched again; a failed request leaves
  no mark. At most `HIGHLIGHTS_SEARCH_DAILY_CAP` (default 80) searches are sent
  per US Eastern day, counted in the state database; a query the source cache
  still holds sends no request and is not counted. Past the cap nothing is
  searched or marked. One search per target is in flight at a time. Without
  `HIGHLIGHTS_SEARCH_API_URL`, the key or `VIDEO_EMBED_URL`, no search runs.
- **Edition video.** The All-Star section hands its edition video to the same
  search through a collaborator wired in `main.py`; the core search imports no
  section.
- **Final game details.** A final game's detail is built on its first request,
  reading the summary of the latest attempt time passed (ADR 0010), not after a
  games run. A stored live feed of a game now final is rebuilt on its next
  request, which waits. A failed build is retried on a request after the
  cache's retry window.
- **Franchise names.** A names list is built once per team over every season
  under a read budget of the number of seasons plus 2, and kept while its build
  version is the current one. A list records the past seasons whose read failed.
  A team page request reads the current season again when the list is 24 hours
  old (the retry window when it is incomplete), and that re-read also reads the
  recorded seasons, under a budget of their count plus 3, so a partial or failed
  first build heals; a season that fails again stays recorded, and a season with
  no team object is not recorded or retried. `career_runs` never starts a build: a
  player feed shows no career team codes for a franchise with no stored list.
- **Settings.** `HIGHLIGHTS_BACKFILL_PAGES` is retired. `.env` files that still
  set it start; the setting is ignored with a warning that does not show its
  value. `HIGHLIGHTS_SEARCH_API_URL` and `HIGHLIGHTS_SEARCH_DAILY_CAP` are new.

## Consequences

- Migration 12 drops the `highlights_backfill`, `highlights_backfill_swept` and
  `highlights_backfill_members` tables, deletes the `jobs` rows of
  `highlights-backfill` and `all-star-discovery`, and adds `highlight_searches`
  (the marks) and `highlight_search_counts` (the searches per day).
- The All-Star section now uses the core search through `main.py`
  (`docs/architecture.md`, ninth qualification).
- The highlights of games older than the live attempts are found only when
  someone opens them, and only while the daily cap lasts.
- A franchise rename in the current season closes the open run without
  recomputing the older runs' codes until the next `SEASON_BUILD_VERSION` bump.
- `docs/api/*` and `docs/design-seasons.md` still describe the backfill and the
  discovery; the docs issue of the hardening plan updates them.
