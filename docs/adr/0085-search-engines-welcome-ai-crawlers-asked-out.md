# 0085. Search engines are welcome, AI crawlers are asked to stay out

- Status: Accepted
- Date: 2026-11-04

## Context

Issue 464. The site had a `robots.txt` that allowed everything, no sitemap, no
description, no canonical address and no Open Graph or Twitter tags, and no
image for a link preview. The home is server-rendered at build time; every other
page turns server rendering off (ADR 0082), so its built file has an empty
component head. `/200.html` answers team, player, game and day addresses, and
also the standings, Cup, playoffs, series, All-Star and previous All-Star
addresses, which `deploy/vercel.json` rewrites to it (ADR 0081).
A link preview that runs no script therefore found no title on any page but the
home.

## Decision

- Search engines are welcome. `web/src/lib/meta/crawl.ts` holds the list of 16
  AI user agents; `robots.txt` disallows `/` for all of them in one group, and
  every other agent is allowed except on `/preview`, which is disallowed for
  everyone. No group names Googlebot or Bingbot. `robots.txt` is a request, not
  enforcement: the API's per-visitor rate limit (ADR 0080) stays the
  enforcement.
- `robots.txt` and `sitemap.xml` are prerendered `+server.ts` routes whose
  bodies come from pure functions in `web/src/lib/meta/crawl.ts`. The sitemap
  lists the prerendered pages that have an address of their own (the home,
  standings, Cup, playoffs, All-Star and the previous All-Star), never
  `/playoffs/series` (a not-found page without its `?id=`) and never `/preview`.
  The table of prerendered pages is `web/src/lib/meta/pages.ts`; removing a
  seasonal section removes its entry.
- Team, player, game and day pages stay rendered in the browser from the
  fallback page (ADR 0020, ADR 0021). Prerendering them would ask the source
  for every team and player at build time, ahead of any visitor (Principle 1).
- The head of every page is written by one builder, `web/src/lib/meta/head.ts`:
  title, description, canonical, Open Graph and Twitter card. `PageMeta` draws it
  in the browser and in the home's server-rendered file. The server hook writes
  the same tags into any built HTML that has no `<title>` (the files of the pages
  that turn off server rendering, and the fallback page); `PageMeta` removes
  those copies when it mounts, so a page never carries two of each. The fallback
  page gets the home's wording and no canonical, because it answers many
  addresses.
- Canonical and `og:url` are self-referential: the origin from the build-time
  setting `SITE_URL`, then the page's pathname and the query parameters the page
  reads: `season`, and `id` on the series page. Other parameters are dropped.
  Without `SITE_URL` there is neither, and
  `robots.txt` and `sitemap.xml` hold no URL.
- The Open Graph image is one file, `web/static/og-image.png`, 1200 by 630: the
  logo mark and the name on the page background.
- `/preview` (development only) sets `noindex` through `PageMeta` and no title.

## Consequences

- Every built HTML file has a title, a description and the social tags, with no
  change to what is drawn.
- A page added later must render `PageMeta`; a guard test fails otherwise.
- The three lists, the table of prerendered pages, the sitemap and the route
  folders, are tied by a test.
- A new AI user agent is one line in `crawl.ts`.
- Pages rendered only in the browser have per-page tags in the live document.
  In production every address but the home is answered by `200.html`, so a
  scraper that runs no script reads the home's generic tags, with no canonical,
  for all of them. The per-page files the hook writes (`standings.html` and the
  other five) carry their own tags but are not what Vercel serves today; serving
  them is left to a later change of the rewrites.
