# 0085. The news archive and the news feeds

- Status: Accepted
- Date: 2026-11-03

## Context

Issue 454. The site gains a News section: the league's news, a team's, a
player's and the recap of a game, in English and Spanish. This decision covers
the API half; the pages are a separate issue. The All-Star and Playoffs pages
keep publishing no headline (`docs/design-all-star.md` and
`docs/design-playoffs.md` are not edited).

## Decision

- **What News is.** Notes written by the league's news source, shown as a
  headline, a short description, a photo and the time. Nothing leaves the site:
  no feed holds a link, a note opens on the site, and no source URL is stored or
  served. The only URLs in a news feed are photo URLs and the team logos added
  when served.
- **The switch.** `NEWS_ENABLED` (default false) turns News on, and `NEWS_URL`
  is the league news list. Off, every news feed answers 404 before any build or
  source read (rule I), and no news request is sent. Turning News off is a
  setting and a restart of the API: no code change and no web deploy. An empty
  `NEWS_ENABLED`, as `api/.env.example` lists it, reads as off.
- **The archive.** Every note a build reads is stored in the state database and
  kept forever. A note is one row per source id and language. A game keeps at
  most one recap per language: the first one stored wins, whether it came from a
  list or from the game summary, so the two never both show. A game whose
  summary has no recap in a language is marked, for good, and not read again for
  that language. No prune method touches these tables.
- **Summary recaps.** The game summary's article has no verified id, published
  time or tags. A recap read from it has the id `recap-{gameId}`, the game's
  start as its published time, the game's two league sides as its teams and no
  players, all from the site's own game. It is read only for a final game the
  site holds: a loaded game of the games job or a final game of a stored day
  feed.
- **Reads.** Every news feed is an on-demand kind of the feed cache (rule G).
  A list is read through the shared source cache and is fresh for 15 minutes, so
  every page, scope and concurrent build shares one read. A recap is read once
  per game and language, for a final game, and then stored or marked.
- **Degrade.** A failed read is logged and the feed is built from the archive; a
  failed read never fails the feed and leaves no recap mark.
- **The language rule.** English shows English notes. Spanish shows Spanish
  notes plus the English recaps of the games that have no Spanish recap, and
  never an English news note.
- **Paths and shapes.** Pages of 12 notes, newest first, in one schema,
  `NewsFeed`:
  `news/{lang}/pages/{page}.json`, `news/{lang}/teams/{code}/pages/{page}.json`
  and `news/{lang}/players/{id}/pages/{page}.json`. One note, or none, with the
  site's own game (sides and score) when it holds the game, in a second schema,
  `NewsArticleFeed`: `news/{lang}/games/{id}.json` and
  `news/{lang}/articles/{id}.json`. Three kinds of the feed cache hold them:
  `news`, `news-recaps` and `news-articles`. The feed files not served in 90
  days are deleted and built again on request; the archive stays.

Extends rules A, G and I of `docs/source-rules.md`, the storage bounds and the
read budgets.

## Consequences

- A recap requested in the minutes after a game ends, before the source has
  published it, marks the game for that language for good. An English recap that
  a list brings later still fills the game feed, because the archive is checked
  before the mark. A Spanish recap only ever comes from the summary, so for
  Spanish the mark is final.
- A game feed is kept for good only when its recap cannot change: a Spanish
  recap, or an English one once the Spanish recap of the game is archived or
  marked. A Spanish game feed holding the English fallback is rebuilt every 15
  minutes until then; the rebuild reads the archive and sends a Spanish read
  only for a final game the site holds and has not marked.
- Pages are numbered over a growing archive, so a page built after new notes
  arrive can repeat one note of the page before it. The pages should dedupe by
  note id.
- News builds count toward the cap of 16 builds started and 4 running (rule H).
- The state database gains four tables (migration 15) that only grow.
- The web half reads these paths and field names as its contract.
