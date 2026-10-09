# Design: nav, standings page and search

The visual, interaction and data specification for the nav, the `/standings` page and the search overlay. It extends `docs/design.md`, `docs/design-game-detail.md` and `docs/design-profiles.md`: every token, rule and shared component defined there applies here. Colors, type, spacing and motion are final: build pixel-close to this document.

## Overview

| Surface | Where | Feed |
|---|---|---|
| Nav | Every page | None |
| Standings | `/standings` | `/feeds/standings.json` |
| Search overlay | Opens over any page | `/feeds/search.json` |

- Season: unchanged (ADR 0022). The page shows the last regular season, with its label, until the regular season starts.
- Both new feeds are on demand (rule G), never on a fixed time.
- The standings page is rendered in the browser from a fallback page, as the game detail page is (ADR 0021).

## Implementation rules

Everything under "Implementation rules" in `docs/design.md`, `docs/design-game-detail.md` and `docs/design-profiles.md` applies, plus:

- **The front end only draws.** Every value comes ready from the feed: percentage, short name, ordinal inputs (the page formats the ordinal), both games behind, signs. `/web` computes nothing except search matching and ranking, locally, with zero requests per keystroke.
- **A missing value is `null` in the feed and renders `—`** (seed, streak, games behind). A missing clinch renders no tag.
- **No URL and no data source name is written in `/web`.** Photos come from the feed.
- **Every user-facing string is translatable**, in English and Spanish (Paraglide). The full list is in "Strings".
- **Styles use tokens.** Every raw color or size in this document is mapped to an existing token or listed under "New tokens" for the implementing issue. Styles never repeat the raw value.
- **Names never break inside a word.** They wrap only at spaces or hyphens.
- **Every player photo falls back** to initials when the feed has none or it fails to load.
- **Shared components are reused:** `TeamMonogram`, `StatusTag`, `Kicker`, `BlueprintFrame`, the loading skeletons and the footer.

### New components

| Component | What it is |
|---|---|
| `NavSearchTrigger` | The search trigger in the nav (field on desktop, icon on mobile) |
| `StandingsHeader` | Season tag, state line, h1, note and the Conference / Division toggle |
| `StandingsTable` | One group block: header, sticky columns, rows, playoff and play-in lines |
| `ClinchTag` | The one-letter clinch tag |
| `StandingsKey` | The key section under the tables |
| `SearchOverlay` | Backdrop, panel or sheet, input row and results |
| `SearchResultRow` | The team row and the player row |

## Shared patterns

- Ground, ink, muted, accent, accent text, divider and row rule through the existing tokens (`--color-bg`, `--color-ink`, `--color-muted`, `--color-accent`, `--color-accent-light`, `--color-divider`, `--color-row-rule`).
- Headings Barlow Condensed 600, body Barlow. Numbers use `font-variant-numeric: tabular-nums`.
- Content max width `--content-max-width`, side padding `--side-padding`.
- Labels: `--label-size`, `--label-letter-spacing`, uppercase, `--color-accent-light`.
- Mobile breakpoint: 680px (`--game-row-breakpoint`).
- Focus: `:focus-visible` with `--focus-ring-width` and `--focus-ring-offset`.

## Nav (every page)

- Order: logo, page links ("Games" or "All games", "Standings", the date on Home), search trigger.
- "Games" is shown on Home; "All games" on every other page (it links to Home).
- Current page link: ink with a 1px accent underline. Other links: muted, ink on hover. Link text uses `--nav-link-size` and `--nav-link-letter-spacing`.
- **Desktop trigger,** 240x40: the search icon (`--nav-icon-size`) and the placeholder "Search player or team", nothing else. Radius 10px.
- **Below 680px:** two rows. Row 1: the logo on the left and a 40x40 icon-only trigger on the right. Row 2: the links, as a full-width break (`flex-basis: 100%` and `order`).
- The trigger is a button with an accessible name "Search".

## Standings page

### 1. Header

- Grid background as the other pages.
- **Season tag** (accent outline) and a **state line**: "Final · regular season" when the regular season is over, or "Regular season · N games played" while it runs.
- **h1** "Standings", `clamp(56px, 9vw, 128px)`.
- A one-line note under the h1.
- **Toggle** on the right: Conference / Division. The active option has the `--toggle-active-fill` background and an accent border. The selection is not kept between visits; Conference is the default.

### 2. Group blocks

One block per group. In the Conference view: Eastern Conference, Western Conference. In the Division view: Atlantic, Central, Southeast, Northeast, Northwest, Pacific, Southwest, in the order the feed sends.

- h2 with the group name (`--detail-section-h2-size`, uppercase) and a meta on the right, 12px (`--caption-size`), muted:
  - Conference view: "15 teams · GB vs conference leader"
  - Division view: "Eastern Conference · GB vs division leader"
- The count is the number of teams in the group.

### 3. Table

- Columns: Seed + Team (sticky) · W · L · Pct · GB · Strk · Home · Away · L10 · Div · Conf · PPG · Opp · Diff · Tot.
- **Seed is always the conference seed,** also in the Division view.
- **GB is against the group leader** (the conference leader or the division leader, per the view).
- Order: the Conference view is sorted by seed; the Division view follows the division order the feed sends.
- **Team cell:** the seed, a 34px monogram tile with a 3px strip (primary | secondary team color), the city (muted; hidden below 680px) and the name, then the clinch tag.
- **Pct** is shown without the leading zero: `.659`.
- **GB** is `—` for the leader and one decimal otherwise.
- **Strk** is in accent text when it is a win streak.
- **Diff** and **Tot** carry a sign (`+4.4`, `−312`) and are in accent text when the value is zero or above.
- **Div** and **Conf** are the record within the division and the conference.
- **Diff** is per game; **Tot** is the season total.
- An eliminated team (`e`) has its whole row muted.
- Every row links to `/team/{code}`. Hover: `--box-row-hover`.
- Row rules: `--color-row-rule`. The first column is `position: sticky; left: 0` with the ground background.
- No cell wraps.

### 4. Clinch tags

One tag per team, the highest status. Tags use `--injury-tag-size` and `--tag-padding`.

| Code | Meaning | Look |
|---|---|---|
| `*` | Clinched best record in league | Accent border, accent text |
| `z` | Clinched best record in conference | Accent border, accent text |
| `y` | Clinched division | Accent border, accent text |
| `x` | Clinched playoffs | Accent border, accent text |
| `xp` | Clinched play-in | Divider border, ink |
| `pb` | In play-in position | Divider border, ink |
| `e` | Eliminated | Divider border, muted |

"Accent text" is `--color-accent-light`; "accent border" is `--color-accent`; "divider border" is `--color-divider`.

### 5. Playoff and play-in lines

Conference view only. A dashed accent line under seed 6 ("Playoff line") and under seed 10 ("Play-in line"). The lines are decorative: they carry no text in the table and are explained in the key. Dash pattern: `--standings-line-dash`.

### 6. Key

A section under the tables, with the label "Key":

- The seven codes with their meaning (see "Clinch tags").
- A note: "GB, Div and Conf are within the group shown. Diff is per game, Tot is the season total. The dashed lines mark seed 6 and seed 10."

## Search overlay

### 1. Opening and closing

- **Open:** click the trigger, press `/` when the focus is not in a text field, or press Cmd+K / Ctrl+K. The input takes focus. Body scroll is locked while the overlay is open.
- **Desktop:** a centered panel, max width 720px, 10vh from the top. Close with Esc, the Esc button or a click on the backdrop.
- **Below 680px:** a full-screen sheet. The close button reads "Cancel".
- On close, the focus returns to the trigger and the scroll lock is released.

### 2. Input row

- 64px high: the search icon, the input (Barlow Condensed 500, 24px), a clear button shown only when the input has text, and the Esc button (desktop) or Cancel button (mobile).
- With an empty input, only the input row shows.

### 3. Matching

- Both the query and the index text are lowercased and normalized to NFD with diacritics removed.
- The query is split on whitespace. **Every token must prefix-match a word.**
- **Team words:** city, name, code.
- **Player words:** the full name and its parts split on space, hyphen, period and apostrophe. A player also matches his team's words, at a lower score.

### 4. Ranking

- Teams first, then players.
- Player score per token: exact word 4, prefix of an own-name word 3, team word 1. The score of a player is the sum over the tokens.
- Ties: players with a photo first (the roster entry has a headshot), then name A to Z.
- Players are capped at 8 on desktop and 6 on mobile, followed by a "Show all N players" row that lifts the cap.

### 5. Results

- Section labels "Teams · N" and "Players · N": `--label-size`, `--label-letter-spacing`, uppercase, `--color-accent-light`.
- **Team row:** a 42px monogram tile with a 4px strip; the city (muted) and the name at 19px (`--player-name-size`); under them "OKC · 1st in Northwest"; the record on the right (19px, tabular). Links to `/team/{code}`.
- **Player row:** a 42px photo tile (initials fallback); the name at 19px; under it "#2 · Guard (G)"; the injury tag when present; on the right a 3px bar in the team's primary color and the team code. Links to `/player/{id}`.
  - Below 680px: the short name and "#2 · G".
- **Injury tag:** Out = accent border and accent text. Questionable and Doubtful = divider border and ink. Any other status = divider border and muted.
- **Active row:** the `--search-active-row` background, radius 10px, inset 8px. Hover sets it; Up / Down move it, wrapping at both ends; Enter opens it.
- **No results:** `No players or teams match "{q}".`

### 6. Surface

- Radii, only in this overlay: trigger and rows 10px, panel 14px, tiles 8px, Esc button 6px.
- Backdrop: `--search-backdrop` with a `--search-backdrop-blur` blur.
- Panel: `--search-panel-bg`, a 1px `--color-divider` border, shadow `--search-panel-shadow`.

### 7. Data

- The index is fetched on the first open, kept in memory and revalidated with its ETag.
- After that, matching runs locally: zero requests per keystroke.

## Edge cases

| Case | What shows |
|---|---|
| No results | The "No players or teams match" line; the input stays focused |
| Empty input | Only the input row; no results, no hint |
| Null seed, streak or games behind | `—` in that cell |
| No clinch | No tag; the team name sits where the tag would start |
| 0-0 teams (start of a season) | Streak and games behind are null (`—`); seeds can repeat; Pct shows `—` |
| Repeated seeds | Both rows show the same seed; the order is the feed's |
| A seed above a team with more wins | Seeding follows the final seeding, not the record: sort by seed, never by wins |
| Missing photo | Initials in the photo tile |
| Missing colors | A plain tile (`--color-surface`) with no strip |
| Unavailable feed | The standings page shows the home's "Data isn't available right now. Check back later." row under the nav; the overlay shows the same line under the input row (a 503 or a failed request) |
| Rosters not fetched yet | The search feed answers 503; the overlay shows the unavailable line, and the next open fetches again |
| Spanish | Every string in "Strings" has a Spanish text; long Spanish labels truncate with an ellipsis in the trigger and never wrap in a table cell |

## States

| State | What shows |
|---|---|
| Loading (standings) | Skeletons shaped like the header and the first table, with the home's shimmer, stopped under reduced motion |
| Loading (search) | The input row is usable at once; results appear when the index arrives |
| Feed unavailable | See "Edge cases" |
| Start of a season | The last regular season with its label until the regular season starts; then the 0-0 rules of "Edge cases" |

## Interactions and motion

| What | How |
|---|---|
| Conference / Division toggle | Switches the blocks shown; no scroll jump |
| Row hover | `--box-row-hover` on the standings row |
| Open overlay | Backdrop fades in and the panel rises `--list-entrance-offset` with `--ease`; instant under reduced motion |
| Close overlay | The reverse; instant under reduced motion |
| Keyboard | `/`, Cmd+K / Ctrl+K open; Esc closes; Up / Down move the active row (wrapping); Enter opens it |
| Focus | Trapped in the overlay while open; `:focus-visible` as on the home |

## Responsive

- Under 680px:
  - The nav is two rows (logo and icon trigger, then the links).
  - The standings table scrolls horizontally inside `overflow-x: auto`; Seed and Team stay pinned; the team column has a 178px minimum; the city is hidden.
  - The search overlay is a full-screen sheet with a "Cancel" button; player rows use the short name and "#2 · G"; players are capped at 6.
- Every other part reflows without a breakpoint.

## New tokens

To add to `web/src/lib/styles/tokens.css` in the implementing issue. Values below are the design values; every other value in this document maps to an existing token.

| Token | Value | Use |
|---|---|---|
| `--nav-search-width` | 240px | Desktop trigger width |
| `--nav-search-height` | 40px | Trigger height |
| `--nav-search-icon-trigger` | 40px | Mobile icon trigger |
| `--search-radius` | 10px | Trigger and rows |
| `--search-panel-radius` | 14px | Panel |
| `--search-tile-radius` | 8px | Tiles |
| `--search-esc-radius` | 6px | Esc button |
| `--search-panel-max-width` | 720px | Panel |
| `--search-panel-top` | 10vh | Panel offset |
| `--search-input-row-height` | 64px | Input row |
| `--search-input-size` | 24px | Input text |
| `--search-tile-size` | 42px | Team and player tile |
| `--search-strip-height` | 4px | Team tile strip |
| `--search-team-bar-width` | 3px | Player row team bar |
| `--search-row-inset` | 8px | Active row inset |
| `--search-active-row` | rgba(116, 157, 196, 0.10) | Active row |
| `--search-backdrop` | rgba(6, 7, 8, 0.74) | Backdrop |
| `--search-backdrop-blur` | 6px | Backdrop blur |
| `--search-panel-bg` | #101316 | Panel |
| `--search-panel-shadow` | 0 40px 90px -20px rgba(0, 0, 0, 0.85) | Panel |
| `--search-players-cap` | 8 | Desktop player cap (mobile 6) |
| `--standings-h1-size` | clamp(56px, 9vw, 128px) | h1 |
| `--standings-monogram-size` | 34px | Table tile |
| `--standings-strip-height` | 3px | Table tile strip |
| `--standings-team-column-page-min` | 178px | Team column minimum (the existing `--standings-team-column-min` belongs to the game detail table) |
| `--standings-line-dash` | 4 4 | Playoff and play-in lines |

Mapped to existing tokens: active toggle `rgba(116, 157, 196, 0.14)` is `--toggle-active-fill`; row hover `rgba(116, 157, 196, 0.06)` is `--box-row-hover`; label color `#94bce3` is `--color-accent-light`; label size and spacing are `--label-size` and `--label-letter-spacing`; the 19px name is `--player-name-size`; the 680px break is `--game-row-breakpoint`; the divider is `--color-divider`.

## Strings

| Key (suggested) | English | Spanish |
|---|---|---|
| `nav_games` | Games | Partidos |
| `nav_all_games` | All games | Todos los partidos |
| `nav_standings` | Standings | Clasificación |
| `search_trigger_label` | Search | Buscar |
| `search_placeholder` | Search player or team | Buscar jugador o equipo |
| `search_clear` | Clear | Borrar |
| `search_esc` | Esc | Esc |
| `search_cancel` | Cancel | Cancelar |
| `search_teams` | Teams · {n} | Equipos · {n} |
| `search_players` | Players · {n} | Jugadores · {n} |
| `search_show_all` | Show all {n} players | Ver los {n} jugadores |
| `search_no_results` | No players or teams match "{q}". | Ningún jugador ni equipo coincide con "{q}". |
| `search_team_meta` | {code} · {rank} in {division} | {code} · {rank} en {division} |
| `search_unavailable` | Data isn't available right now. Check back later. | Los datos no están disponibles ahora. Vuelve más tarde. |
| `standings_title` | Standings | Clasificación |
| `standings_note` | Seeds follow the official seeding. | Los puestos siguen la clasificación oficial. |
| `standings_state_final` | Final · regular season | Final · temporada regular |
| `standings_state_live` | Regular season · {count} game played / {count} games played (one / other) | Temporada regular · {count} partido jugado / {count} partidos jugados (one / other) |
| `standings_conference` | Conference | Conferencia |
| `standings_division` | Division | División |
| `standings_view_toggle` | Standings view | Vista de la clasificación |
| `standings_meta_conference` | {count} team / {count} teams · GB vs conference leader (one / other) | {count} equipo / {count} equipos · DP vs líder de conferencia (one / other) |
| `standings_meta_division` | {conference} · GB vs division leader | {conference} · DP vs líder de división |
| `standings_col_seed` | Seed | Puesto |
| `standings_col_team` | Team | Equipo |
| `standings_col_w` | W | G |
| `standings_col_l` | L | P |
| `standings_col_pct` | Pct | Pct |
| `standings_col_gb` | GB | DP |
| `standings_col_strk` | Strk | Racha |
| `standings_col_home` | Home | Casa |
| `standings_col_away` | Away | Fuera |
| `standings_col_l10` | L10 | U10 |
| `standings_col_div` | Div | Div |
| `standings_col_conf` | Conf | Conf |
| `standings_col_ppg` | PPG | PPP |
| `standings_col_opp` | Opp | Rival |
| `standings_col_diff` | Diff | Dif |
| `standings_col_tot` | Tot | Tot |
| `standings_key` | Key | Leyenda |
| `clinch_star` | Clinched best record in league | Mejor récord de la liga asegurado |
| `clinch_z` | Clinched best record in conference | Mejor récord de la conferencia asegurado |
| `clinch_y` | Clinched division | División asegurada |
| `clinch_x` | Clinched playoffs | Playoffs asegurados |
| `clinch_xp` | Clinched play-in | Play-in asegurado |
| `clinch_pb` | In play-in position | En posición de play-in |
| `clinch_e` | Eliminated | Eliminado |
| `standings_key_note` | GB, Div and Conf are within the group shown. Diff is per game, Tot is the season total. The dashed lines mark seed 6 and seed 10. | DP, Div y Conf son dentro del grupo mostrado. Dif es por partido, Tot es el total de la temporada. Las líneas discontinuas marcan el puesto 6 y el 10. |

Notes:

- Conference names reuse `team_conference_east` and `team_conference_west`, and the unavailable row reuses `feed_unavailable`. The playoff and play-in lines carry no text.
- Division names, team names, cities, positions and injury statuses are shown as the feed sends them or through the existing translations of the injury statuses.
- Ordinals (`1st`, `2nd`) are formatted by the page from the feed's integer position, in the active language's form (`1.º`).

## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601. Every value below is computed by the backend, except the ordinal text, which the page formats from an integer position. Both feeds are on demand (rule G).

### Standings feed

Where this table and `docs/api/standings.md` or `web/src/lib/contract/standings.ts` differ, those two are the authority.

| Field | Content |
|---|---|
| `season` | Label, such as `2025-26` |
| `state` | `final` or `regular`, and `gamesPlayed` for the state line |
| `conferences` | In display order; each `key` (`east` / `west`), `name`, `teamCount` and `teams` sorted by seed |
| `divisions` | In display order; each `name`, `conference` (the key, `east` / `west`) and `teams` in division order |
| Team row | `code`, `city`, `name`, `colors` (`primary`, `secondary`; each or null), `seed` (or null), `clinch` (`*`, `z`, `y`, `x`, `xp`, `pb`, `e`; or null), `wins`, `losses`, `pct` (ready string, such as `.659`), `gamesBehind` (ready string, or null; against the group), `streak` (an object with `kind` win / loss and `count`, or null), `home`, `away`, `lastTen`, `division`, `conference` (each a ready `W-L` with a hyphen, such as `34-7`), `pointsFor`, `pointsAgainst` (per game), `differential` (ready signed string, per game, and `nonNegative`), `total` (ready signed string, and `nonNegative`) |

### Search feed

Where this table and `docs/api/search.md` or `web/src/lib/contract/search.ts` differ, those two are the authority.

| Field | Content |
|---|---|
| `teams` | `code`, `city`, `name`, `colors`, `record` (ready string), `divisionRank` (integer 1 to 5, or null; the page formats the ordinal) and `division` (name) |
| `players` | `id`, `name`, `shortName`, `number`, `position` (name), `positionAbbr`, `photoUrl` (or null), `injury` (`status`, or null), `team` (`code`, `primary` color or null) |

- Answers 503 until the rosters are fetched. The client sends the ETag back and handles 304.
