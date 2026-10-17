# 0049. Competition season selectors

- Status: Superseded by 0054 for the Cup's season list only
- Date: 2026-10-15

## Context

Issue 263. ADR 0044 gives the standings, team and player pages a season
selector. ADRs 0045 to 0048 serve the season feeds of the Cup, the playoffs and
the All-Star game and the All-Star edition video, and left the pages to this
issue. `docs/design-seasons.md` draws them.

## Decision

- `/cup`, `/playoffs` and `/all-star` follow ADR 0044: the calendar is the
  source of the seasons, `?season=YYYY` picks a past season, a past season reads
  its feeds once with `FeedOnce`, and the selector is hidden when the calendar is
  unavailable.
- **Lists.** The Cup lists the calendar's seasons from `FIRST_CUP_SEASON`
  (2024), a constant in the Cup section that mirrors the api's, because no feed
  says when the Cup starts. The playoffs and the All-Star list every calendar
  season. A `?season` below 2024 on `/cup` requests
  its season Cup feed, which answers 404, so the page shows the unavailable
  state, as `docs/design-seasons.md` draws it; the selector never offers it.
- **Settings.** `SEASON_CUP_FEED_URL`, `SEASON_CUP_MATCHUP_FEED_URL`
  (`{season}`, `{slot}`), `SEASON_PLAYOFFS_FEED_URL`,
  `SEASON_PLAYOFFS_FINALS_FEED_URL` and `SEASON_ALL_STAR_FEED_URL`.
- A 404 on a season feed shows the unavailable state, because these pages have
  no not-found state.
- The past Cup matchup reads its feed once and shows the "current season only"
  line in place of the injuries and the roster.
- **Playoffs, past seasons only.** The head to head counts as present when at
  least one bar value is not null, and a null side seed draws no seed number.
  The current season renders exactly as before: the head to head is present
  whenever the finals feed is in, and a null seed draws "—". The `playin`
  stage is not drawn when `playIn` is null (the current feed never sends null,
  so the current season does not change).
- **All-Star.** The edition video (`editionHighlight`) replaces the selected
  game's media frame wherever it is present (the current after state, a past
  season, `/all-star/previous`), with the caption "Edition highlights". The
  "Last time" champion card links to the recap's `editionHighlight.embedUrl` in
  a new tab. The season tag takes its label from the calendar.

## Consequences

- The Cup's first season is written twice (api and web). A change on one side
  alone shows a 404 season (the unavailable state) or hides one.
- The current season draws no new behavior: a current Finals with all-null bars
  still draws the head to head, and a current null seed still draws "—". The two
  rules differ by season on purpose.
- One calendar request per view of the three pages when `CALENDAR_FEED_URL` is
  set.
- This ADR extends ADR 0044 to three more pages and does not supersede it.
