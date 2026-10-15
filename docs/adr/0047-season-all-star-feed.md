# 0047. Season All-Star feed

- Status: Superseded by 0048 for what the season kind adds when served only
- Date: 2026-10-15

## Context

Issue 259. `docs/design-seasons.md` draws the All-Star page of a past season.
ADR 0036 serves the current season's All-Star feed only (`/feeds/all-star.json`),
from the edition its discovery job stores. ADR 0045 and ADR 0046 cover the Cup
and the playoffs of a past season.

## Decision

- **Path and kind.** `/feeds/seasons/{season}/all-star.json` (kind
  `season-all-star`, id `{season}`). The schema is the current `AllStarFeed`: no
  new model.
- **Range.** The end year from 1994 to the current season. The current season
  resolves before the cache to the current kind (`all-star`/`league`), so the
  current feed, its expiry and its route do not change. A season outside the
  range or ill-formed answers 404 with no source request, and 503 while the
  current season is not known.
- **Edition discovery.** The edition of a season is the stored
  `all_star_editions` row when there is one. Otherwise it is the first February
  day (US Eastern) that the season's calendar lists, read in order with the
  All-Star scoreboard view, that has All-Star games; it is then stored in
  `all_star_editions`. The calendar is read through the source read the calendar
  feed is built from (same URL, same cached response), not through the calendar
  feed, because a build needs two seasons' calendars and a build cannot wait on
  another build in its slot. A season with no edition found answers 404 and is
  remembered in memory, as the team of ADR 0043: it is not scanned again until a
  restart, unless an edition is stored for it meanwhile.
- **Previous edition.** Found the same way for the season before. The recap
  (`previous`) and `previousEdition` are null before 1994 or when it is not
  found.
- **Reads.** A game detail, sections, extras or season awards read that answers
  404 only nulls its part (the MVP is null when the source has none). Any other
  failed read, and any failed calendar or scoreboard day read, fails the build
  and stores nothing, because the feed is kept for good.
- **Must build as `after`.** Any other state fails the build with a logged reason
  and stores nothing.
- **League teams.** `leagueTeam` is null on every row: the rosters of the stars
  job are today's, and no roster or team info of that season is read.
- **No per-game highlight.** The season kind adds nothing when served, so
  `highlights` is null on every game. The current season's path serves the
  current feed byte for byte, with its per-game highlights.
- **Kept.** Built once on request under rule G and never refreshed or deleted.

## Consequences

- A restart forgets the seasons with no edition: one more scan each.
- The calendar is assumed to list the All-Star day as a day with games; if it
  does not, every past season answers 404. The season is logged at info.
- The season feed and the discovery job write the same table; the season feed
  writes only a season it found All-Star games for, on the first such day.
- The current season's path keeps the current feed's per-game highlights until
  the edition highlight is added.
- A cold build reads about 15 to 30 scoreboard days and 3 cached detail URLs per
  game, per season, once.
- No `/web` change.
