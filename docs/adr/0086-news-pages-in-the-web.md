# 0086. News pages in the web

- Status: Accepted
- Date: 2026-11-03

## Context

Issue 456. The API serves the news feeds of ADR 0085. The web reads them in five
places: a carousel on the home, the News page at `/news`, a note page at
`/news/{id}`, a News section on the team and player pages and a Recap section on a
final game page. The pages are specified in `docs/design-news.md`, built under the
rules of ADR 0020 and ADR 0082.

## Decision

Settings and routes:

- Five build-time settings point at the feeds, as for every other feed:
  `NEWS_FEED_URL` (`{lang}`, `{page}`), `NEWS_TEAM_FEED_URL` (`{lang}`, `{code}`,
  `{page}`), `NEWS_PLAYER_FEED_URL` (`{lang}`, `{id}`, `{page}`), `NEWS_GAME_FEED_URL`
  (`{lang}`, `{id}`) and `NEWS_ARTICLE_FEED_URL` (`{lang}`, `{id}`). `scripts/deploy.sh`
  sets them and `deploy/vercel.json` serves the fallback page for `/news` and `/news/*`.
- `/news` has a prerendered shell and is rendered in the browser; `/news/{id}` is
  rendered in the browser from the fallback page, like `/game/{id}` (ADR 0019).

Reading the feeds:

- Every news feed is read once, in the active language, and never polled. A missing
  URL, a 404, a failed request or a page with no notes gives no block: no tab, no
  section, no link. The request starts in parallel with the page's own feed and never
  delays it.
- The team and player pages read news for the current season only: News is not
  scoped to a season, so a past season sends no request. The game page asks for the
  recap once the game is final.
- The News page pages over the archive and dedupes by note id (ADR 0085). The feeds
  have no kind path, so the type filter filters the notes already loaded; the team
  select switches to the team path. The 30 teams of the select come from the search
  feed.

Dates:

- A note is dated under 24 hours as hours ("16 h ago", at least 1) and otherwise by
  day and month in the viewer's zone, with the year when it is not the current one
  (ADR 0082).
- The note's game button names the game's own day, the US Eastern day of its tip-off
  (ADR 0082), read from the game detail feed the web already uses. The note's
  published time is not used: a late game's recap can be published the next day.
  Until that feed loads, or if it fails, the button shows the score without a date.
  The news feeds carry no game date, and adding one is not part of this decision.

## Consequences

- A build without the five URLs has no news anywhere and every page renders as before.
- The note page makes one extra request, to the game detail feed, only when the note
  has a game the site holds.
- The static host must serve the fallback page for `/news` and `/news/*`.
- A recap requested right after a game ends can be marked missing for Spanish for
  good (ADR 0085); the Recap tab then stays hidden.
