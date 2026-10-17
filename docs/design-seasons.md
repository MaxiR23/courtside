# Design: Competitions by season

The visual, interaction and data specification of the Cup, playoffs and All-Star pages for past seasons, of the season selector on those three pages, of the All-Star edition video and of the past highlights backfill. It extends `docs/design.md`, `docs/design-cup.md`, `docs/design-playoffs.md` and `docs/design-past-dates.md`: every token, rule and shared component defined there applies here, and only new values are listed under "New tokens". The current feeds, their expiry and their live behavior do not change. This document is the specification the feature issues implement; it adds no behavior beyond the decisions recorded here.

## Overview

| Page | Route | Feeds (past season) | Feeds (current season) |
|---|---|---|---|
| Cup | `/cup?season=YYYY` | `/feeds/seasons/{season}/cup.json`, `/feeds/seasons/{season}/cup/matchups/{slot}.json` | The existing Cup feeds |
| Playoffs | `/playoffs?season=YYYY` | `/feeds/seasons/{season}/playoffs.json`, `/feeds/seasons/{season}/playoffs/finals.json` | The existing playoffs feeds |
| All-Star | `/all-star?season=YYYY` | `/feeds/seasons/{season}/all-star.json` | The existing All-Star feed |

- A season is identified by its end year. The label is "2023-24", written as `season_label` writes it.
- **Season ranges:** the Cup feeds exist for seasons 2024 to the current one; the playoffs and All-Star feeds exist for seasons 1994 to the current one. Any other season is a 404.
- Without `?season`, a page shows the current season as today and uses the existing feeds. With `?season` equal to the current season the page also uses the existing feeds. For a past season it uses the season feeds.
- A past season is complete: the Cup and the playoffs are in their final state and the All-Star is in its after state. The page has no live element.
- All routes are rendered in the browser from the fallback page (ADR 0020, ADR 0021).

## Implementation rules

Everything under "Implementation rules" in `docs/design.md`, `docs/design-cup.md`, `docs/design-playoffs.md` and `docs/design-past-dates.md` applies, plus:

- **`/web` computes nothing.** The rounds, the seeds, the champion, the paths, the edition video and every value shown come ready from a feed. The page writes the fixed words around them.
- **A value that is missing renders `—`. A block that is missing hides its section** and leaves no gap.
- **Nothing is hardcoded in `/web`:** no team, season list, date or series. No data source name, video platform or URL is written in `/web`.
- **Every user-facing string is translatable**, in English and Spanish. Long labels truncate with an ellipsis and never wrap in a table cell.
- **Today's colors and logos only**, as in `docs/design-past-dates.md`.
- **No live element on a past season:** no live dot, no countdown, no "today" strip, no live badge.
- **Web settings** (one per feed, with the placeholders in braces):

| Setting | Placeholders |
|---|---|
| `SEASON_CUP_FEED_URL` | `{season}` |
| `SEASON_CUP_MATCHUP_FEED_URL` | `{season}`, `{slot}` |
| `SEASON_PLAYOFFS_FEED_URL` | `{season}` |
| `SEASON_PLAYOFFS_FINALS_FEED_URL` | `{season}` |
| `SEASON_ALL_STAR_FEED_URL` | `{season}` |

- **No new source settings.** The only new api setting is `HIGHLIGHTS_BACKFILL_PAGES` (see "Past highlights backfill").
- **Shared components are reused:** `SeasonSelect` and `SeasonTag` from `docs/design-past-dates.md`, the Cup, playoffs and All-Star components and sheets, the highlights frame, the loading skeletons and the footer.

## Season selector and routes

- **Routes:** `/cup`, `/playoffs` and `/all-star` accept `?season=YYYY`. Without it, the current season as today. A season outside the range of the page, or a malformed value, is the current season, as without `?season`.
- **Selector:** the same select as `docs/design-past-dates.md` (`SeasonSelect`), at the right of the Cup, playoffs and All-Star headers. The Cup lists 2023-24 to the current season; the playoffs and the All-Star list 1993-94 to the current one, newest first. Changing it navigates to `?season=YYYY`; the current season has no parameter.
- **Season tag:** a past season shows the "Season YYYY-YY" tag (`SeasonTag`) in the header and no live element.
- **Mobile:** the selector is full width under the header with a 44px hit target, as on the other pages.

## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601. Every value is computed by the backend. Exact field names are set by `docs/api` in the issues that add the feeds. The season feeds have the same shapes as the current ones.

| Path | What it carries | Seasons |
|---|---|---|
| `/feeds/seasons/{season}/cup.json` | The Cup of that season in its complete state | 2024 to the current |
| `/feeds/seasons/{season}/cup/matchups/{slot}.json` | The matchup of that slot with the path of each team and no roster | 2024 to the current |
| `/feeds/seasons/{season}/playoffs.json` | The playoffs of that season, complete | 1994 to the current |
| `/feeds/seasons/{season}/playoffs/finals.json` | The Finals of that season, game by game | 1994 to the current |
| `/feeds/seasons/{season}/all-star.json` | The All-Star edition of that season in its after state | 1994 to the current |

- **Statuses:** a season outside the range of the feed is a 404. An All-Star season whose edition is not found is a 404.
- **Expiry:** a past season's feed is built once and kept, as the past-dates feeds. The current season keeps its existing feeds and routes; the page picks them when the season is the current one.
- **Cup:** a past season's Cup is in its complete state. Its matchup feed carries the path of each team and no roster: rosters, depth charts and injuries are current-season only.
- **Playoffs:** a past season is complete. The play-in block is `null` for seasons before 2021. The leaders, the team postseason record and statistics, the awards and the largest deficit are `null` when the source has none for that season, and the page hides them.
- **All-Star:** the edition of that season in its after state, discovered through the February days with games of the season calendar. No edition found is a 404. The previous-edition recap stays as it is in the current feed.
- **`editionHighlight`:** the All-Star feeds (current and season) carry `editionHighlight`, a Highlight of the same shape as the game highlight, or `null`.

### Rounds for seasons without round notes (1994 to 2007)

For the seasons whose game notes carry no round, the backend derives the rounds:

1. Group the postseason games into series by their two teams.
2. Order each team's series by the date of their first game.
3. A series is round k when it is the k-th series of both teams.
4. The Finals is the only series whose teams belong to different conferences. The conferences come from that season's standings feed.

- A postseason where this gives anything but eight, four, two and one series fails the build with a logged reason, never a wrong bracket.
- **Seeds** come from that season's standings feed (`playoffSeed`). A season without seeds shows the bracket without seed numbers.
- **Notes** are read case-insensitively when present.

## Past highlights backfill

A daily job step, after the highlights run.

- It pages the official channel's uploads back from the newest upload, matching every stored final game without a highlight with the existing matcher. The games are those of built past day feeds, past competition feeds and the current season's feeds.
- It reads at most `HIGHLIGHTS_BACKFILL_PAGES` pages per day (default 200) and remembers the oldest upload date reached, so the next day continues from there. A page already read is never read again for the same games.
- Matches are stored like the live ones and served by the existing serving path on every feed.
- **Re-upload of the same game:** the first match in channel order is taken.

### All-Star edition video

- For each edition (the current feed and the season feeds) the backfill looks, among the uploads published from the edition day to three days after it, for the first title in channel order that contains "All-Star", the edition year and the word "Highlight" or "Full".
- It is stored per edition and served as `editionHighlight` (same Highlight shape). None found, `null`.
- No per-game highlight is ever shown for an All-Star game.

## Cup of a past season

- The complete state as the page draws it today: the champion, the bracket with scores, the group tables with the clinchers.
- The header carries the selector and the "Season YYYY-YY" tag. No live dot, no countdown, no "today" strip.
- **Matchup sheet:** it shows each team's path and, in place of the roster, the line "Rosters are shown for the current season only". No depth chart and no injuries.

## Playoffs of a past season

The complete state, in this order, each block hidden without a gap when it has no data:

- The champion hero (trophy option).
- The Finals MVP, when the awards carry it.
- The series game by game.
- The road to the title.
- The head to head, when team statistics exist.
- The leaders, when they exist.
- The bracket. A season without seeds shows the slots without the seed number.
- The play-in strip, only from 2020-21.
- The awards.

## All-Star of a past season

- The after state of the page.
- **Edition video frame:** the edition video, when present, replaces the highlights frame of the selected game. The frame shows the edition video with the caption "Edition highlights", and the game cards do not show a per-game video state. Without it, the existing placeholder.
- The same frame appears in the current season's after state and in `/all-star/previous`.
- The "Last time" card links to the edition video when present.

## Past highlights in the pages

No new UI. A past game whose highlight has been found shows it in the game page and in the Finals series as today. The day page cards show the existing highlight mark when the stored game has one.

## Edge cases

| Case | What shows |
|---|---|
| Cup season before 2023-24 | The feed answers 404; the page shows the unavailable state. The Cup list keeps the season on show so the visitor can reach it (ADR 0054) |
| Playoffs season before 2020-21 | No play-in strip; the play-in block is `null` for seasons before 2021 |
| Postseason without leaders | The leaders section is hidden without a gap |
| Postseason without team statistics | The head to head section is hidden |
| Postseason without awards | The awards section and the Finals MVP are hidden |
| Season without seeds | The bracket shows the slots without the seed number |
| Round derivation that does not give 8-4-2-1 | The build fails with a logged reason and the feed is not served: the page shows the unavailable state, never a wrong bracket |
| All-Star edition not found for a season | The feed answers 404; the page shows the unavailable state |
| Edition video not found | `editionHighlight` is `null`; the frame shows the existing placeholder and the "Last time" card does not link |
| Backfill reaching its daily page cap | It stops for the day, remembers the oldest upload date reached and continues from there the next day |
| Re-uploaded highlight | The first match in channel order is taken |
| Season outside the range, or a malformed `?season` | The current season, as without `?season` |
| Missing values | `—` in that cell |
| Missing block | The section is hidden without a gap |
| Unavailable feed (503) | The nav row, then the home's 503 state: "Data isn't available right now. Check back later." Polling is not used for a past feed |
| Spanish strings | Every string has a Spanish text; long labels truncate, never wrap in a table cell |

## States

| State | What shows |
|---|---|
| Loading | Skeletons shaped like the page header and its first section, with the home's shimmer, stopped under reduced motion |
| Feed unavailable | See Edge cases |
| Past season | The "Season {label}" tag, no live element, hidden blocks without gap |

## Interactions and motion

| What | How |
|---|---|
| Season select | Navigates to `?season=YYYY`; the current season has no parameter |
| Matchup sheet, series sheet | As in `docs/design-cup.md` and `docs/design-playoffs.md` |
| Edition video frame | As the highlights frame today |
| Focus | `:focus-visible` as on the home |
| Reduced motion | As the pages today |

## Responsive

- Under 680px: the selectors are full width under the header, as the other pages, and every hit target is at least 44px.
- Desktop: the selector sits at the right of the header.

## New tokens

None. Every value maps to the tokens of `docs/design-past-dates.md` and the existing tokens.

## Strings

| Key (suggested) | English | Spanish |
|---|---|---|
| `seasons_cup_no_roster` | Rosters are shown for the current season only | Las plantillas solo se muestran de la temporada actual |
| `seasons_edition_highlights` | Edition highlights | Resumen de la edición |
| `seasons_season_tag` | The existing `past_season_tag`: Season {label} | Temporada {label} |
| `seasons_season_select` | The existing `past_season_select`: Season | Temporada |
| `seasons_unavailable` | The existing `feed_unavailable`: Data isn't available right now. Check back later. | Los datos no están disponibles ahora. Vuelve más tarde. |

The "Last time" card reuses its existing strings. The season label, the team names and the values come from the feeds. The missing value is "—" in both languages.
