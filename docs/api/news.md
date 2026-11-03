# News feeds

The league's news, a team's and a player's in pages, the recap of a game and one
archived note, in English and Spanish. No feed holds a link: a note opens on the site.

## Schema

`api/schemas/news.schema.json` (pages) and `api/schemas/news-article.schema.json` (game
recap and article), generated from the models in `api/app/feeds/news.py` and
`api/app/feeds/news_article.py` by `scripts/contract.sh`. When this page and the models
disagree, the models win. The feeds are decided in
[ADR 0085](../adr/0085-news-archive-and-feeds.md).

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## URLs

`{lang}` is `en` or `es`. `{page}` is a positive integer without a leading zero. `{code}`
is a lower-case team code of the 30.

| URL | Schema | Meaning |
| --- | --- | --- |
| `/feeds/news/{lang}/pages/{page}.json` | `NewsFeed` | A page of the league's notes |
| `/feeds/news/{lang}/teams/{code}/pages/{page}.json` | `NewsFeed` | A page of the notes tagged with a team |
| `/feeds/news/{lang}/players/{id}/pages/{page}.json` | `NewsFeed` | A page of the notes naming a player |
| `/feeds/news/{lang}/games/{id}.json` | `NewsArticleFeed` | The recap of a game, or none |
| `/feeds/news/{lang}/articles/{id}.json` | `NewsArticleFeed` | One archived note |

## Page feed (`NewsFeed`)

| Field | Type | Meaning | Present |
| --- | --- | --- | --- |
| `page` | integer | The page, from 1 | always |
| `hasMore` | boolean | The archive holds notes past this page | always |
| `notes` | `NewsNote[]` | At most 12, newest first | always |

Pages are numbered over a growing archive: a page built after new notes arrive can repeat
one note of the page before it. Dedupe by note `id`.

## Article feed (`NewsArticleFeed`)

| Field | Type | Meaning | Present |
| --- | --- | --- | --- |
| `note` | `NewsNote` or null | The note; null when the game has no recap | always |
| `game` | `NewsGame` or null | The site's own game the note is about; null when the site does not hold it or there is no note | always |

## Nested objects

| Object | Fields |
| --- | --- |
| `NewsNote` | `id` (letters, digits and hyphens: safe in a path), `language` (`en` or `es`), `kind` (`news` or `recap`), `headline`, `description` (null), `published` (UTC), `photo` (null): `NewsPhoto`, `teams` (distinct standard team codes), `players`: `NewsPlayer[]` (distinct), `gameId` (null: the source's game id) |
| `NewsPhoto` | `url`, `width`, `height` (positive integers), `credit` (null) |
| `NewsPlayer` | `playerId`, `name` |
| `NewsGame` | `id`, `away` and `home` (the game's sides as in the games feed, with their logo and colors added when served, [ADR 0068](../adr/0068-shared-team-identity-and-hero-accents.md)), `score` (null: the game's score) |

## Rules that live in the code

- With `NEWS_ENABLED` off every news feed answers 404 and no news request is sent.
- A note is stored once per id and language and kept forever. A game keeps one recap per
  language, the first stored. A recap read from a game summary has the id `recap-{gameId}`,
  the game's start as its time, the game's two league sides as its teams and no players.
- The language rule: `en` shows English notes; `es` shows Spanish notes plus the English
  recaps of the games with no Spanish recap, never an English news note. The article path
  follows the same rule.
- A note that is not news-worthy for the site is dropped on read: previews, media and
  premium notes. The source's links are never read.
- The description has a leading em dash ("—") and the spaces around it removed. The photo is the first
  header image with a size, else the first image with a size.
- A team page is known for the 30 codes. A player page is known when a roster lists him or
  a stored note names him (503 before the rosters are fetched). A page past the first is
  known only when the archive holds more notes than the pages before it.
- The game feed reads the game summary only for a final game the site holds (a game of the
  games job or a final game of a stored day feed), once per language. A summary with no
  recap marks the game for that language, for good. Spanish tries the Spanish summary and
  then the English one. A game is known when the games job holds it, a stored day feed
  has it as a final game or the archive holds a recap of it; 503 before the days are
  loaded.
- A failed read is logged and the feed is built from the archive, so it never fails the
  feed and marks nothing.

## Refresh

On demand. A page feed and an article feed are rebuilt 15 minutes after the build; a game
feed is kept once its recap cannot change (a Spanish recap, or an English one when the
Spanish recap of the game is archived or marked missing); any other game feed, empty or
holding the English fallback, is rebuilt 15 minutes after the build, which reads Spanish
again when it is still open. A stale feed
is served at once and rebuilt in the background. Files not served in 90 days are deleted
and built again on request; the archive stays.

## Read budget

A list build reads at most 1 list; a game build reads at most 2 summaries; an article
build reads nothing. A list is fresh for 15 minutes in the shared source cache, and so is
a summary read for a recap.
