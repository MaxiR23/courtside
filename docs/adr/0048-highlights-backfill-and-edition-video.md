# 0048. Highlights backfill and the All-Star edition video

- Status: Superseded by 0065 for the backfill only
- Date: 2026-10-15

## Context

Issue 261. `docs/design-seasons.md` draws the highlight of past games and one
video for each All-Star edition. The highlights job (ADR 0015, ADR 0018) looks
for a game's full game highlights 3 times after the final time and then gives
up, so a game older than the games feed window, or one the job missed, never gets
one. ADR 0040, 0041 and 0046 serve no highlight on the day feed, the past game
and the past Finals. ADR 0036 sets per-game highlights on the All-Star games of
the current feed, and ADR 0047 left them until the edition video exists.

Corrections to the issue that this decision records:

- The highlights job has no daily run and shares the task of the live refresh, so
  a 200-page step cannot run in it.
- The day feed, the past game detail and the season Finals serve no highlight
  today, so "every feed that serves highlights" is read as every feed whose
  contract has a `highlights` field.
- The adapter dropped the publish time of an upload, which the sweep and the
  All-Star window need.
- The title matcher reads a team name that can be null on the stored Cup and
  playoffs feeds.
- Cup, playoffs and All-Star are seasonal sections, so the core cannot import
  them.
- The daily pattern of the other jobs runs on startup, so a restart would reset a
  per-day cap.

## Decision

- **Own task, once a day.** `HighlightsBackfill` (job `highlights-backfill`) runs
  in a third scheduler task, so its pages never delay the live refresh or the
  stars (ADR 0014). It runs once a day at `DAILY_FETCH_TIME`, and seeds its last
  run from its own `jobs` row, so the daily cap holds across restarts. A step
  with no target makes no request and records nothing.
- **Targets.** The final games of the games job window, of every stored day feed,
  of the stored Cup feeds and of the stored playoffs feeds, and every stored
  All-Star edition. Left out: a game with an `all_star` mark, a game with a
  highlight, a game whose live attempts are not over (3 used, or no final time
  stored) and a target already swept. A game with a side without a name is
  skipped.
- **Sweep.** One sweep pages the channel uploads newest first, 50 per page, with
  the adapter's page read (same request, source cache and key header). The state
  holds the page token to continue from, the oldest upload time reached and the
  members: the targets the sweep reads for. A new sweep takes every pending
  target; a target that becomes pending during a sweep is not a member and waits
  for the next sweep. A page holding an upload published before a member's start
  passes it: the target is swept and never targeted again. A sweep ends when no
  member is ahead or the uploads run out; the next sweep starts from the newest
  upload. No page is read twice for the same games, and every page able to hold
  a target's video is read after the target appeared.
- **Cap.** `HIGHLIGHTS_BACKFILL_PAGES` (default 200, a positive integer) pages per
  step. The sweep is saved at the next page when the cap is reached.
- **Matching.** The title rule of the highlights job (`title_matches`: both
  teams, the label and the Eastern date). The first match in channel order wins
  and a match is never replaced. A matched upload that does not give a valid
  highlight records the failure and the target is swept.
- **Failure.** A failed page read records the failure under the job name, keeps
  the sweep row and every match stored, and stops the step; the next day reads
  the same token. A failed thumbnail request stops the step before the page's
  sweep advance is saved, so the page is read again.
- **Edition rule.** The window of an edition is the game day (US Eastern,
  midnight) and the 3 days after it. An upload is the edition video when it is
  published in the window and its title has "All-Star", the year of the game day
  and "highlight" or "full", in any letter case. An edition becomes a target when
  its window has ended and it has no video. An edition not found is swept.
- **Storage.** One migration with 4 tables: `all_star_edition_highlights` (season
  to highlight), `highlights_backfill` (the running sweep, one row at most),
  `highlights_backfill_members` (kind and target id of the running sweep) and
  `highlights_backfill_swept` (kind and target id). A game match is stored in
  `highlights` through the highlights job, so the games feed and the game detail
  see it at once.
- **Serve-time overlays.** The stored highlight of a game is added when served,
  never stored, on the day feed (a list, empty when none), the past game detail
  (a list of one, null when none) and the season Finals. The stored edition video
  is added as `editionHighlight` on the edition, the previous edition and the
  recap of both All-Star kinds. A game with an `all_star` mark is served no
  per-game highlight on any feed, including the games feed and the game detail.
- **Feed model.** `editionHighlight: Highlight | null` on `AllStarEdition` (so on
  `AllStarPreviousEdition`) and on `AllStarRecap`, default null so stored feeds
  stay valid. The schema and the TypeScript types are regenerated.
- **Section providers.** The Cup, playoffs and All-Star sections give the core
  their games and editions through injected providers wired in `main.py`, the
  shape of ADR 0035. The core backfill imports no section.

Supersedes only: ADR 0036's serve-time per-game highlights, ADR 0040's empty
highlights on the day feed, ADR 0041's null highlights on a past game, ADR 0046's
"no highlights" on the past Finals and ADR 0047's "adds nothing when served".

## Consequences

- Swept rows and edition highlights are never deleted.
- A game whose upload appears after its sweep passed is not found.
- A target that becomes pending during a sweep waits for that sweep to end.
- A stored page token the source stops accepting fails the step each day until
  the sweep row is cleared.
- The backfill reads every stored day feed once a day.
- Up to 200 more page requests a day on the video API quota; the pages go through
  the source cache.
- A step that found no target records nothing, so it runs again after a restart
  that day, with no reads.
- No `/web` change other than the regenerated types.
