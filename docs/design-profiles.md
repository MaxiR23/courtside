# Design: player and team pages

The visual, interaction and data specification for the player page and the team page. It extends `docs/design.md` and `docs/design-game-detail.md`: every token, rule and shared component defined there applies here. Colors, type, spacing and motion are final: build pixel-close to this document.

## Overview

| Page | Route | Feed |
|---|---|---|
| Player | `/player/{id}` | `/feeds/players/{id}.json` |
| Team | `/team/{code}` | `/feeds/teams/{code}.json` |

- `{id}` is the player id the feeds already use (box score, stars). `{code}` is the standard team code in lowercase, such as `gsw`.
- A player page exists for every player on the current roster of the 30 teams. A team page exists for the 30 teams.
- Both pages are rendered in the browser from a fallback page, as the game detail page is (ADR 0021).

## Implementation rules

Everything under "Implementation rules" in `docs/design.md` and `docs/design-game-detail.md` applies, plus:

- **The front end only draws.** Every value comes ready from the feed: percentages, per-game values, totals, career rows, ranks, ages, metric conversions, record splits, differentials, streaks, playoff position, the next game, the month groups of the schedule and the default month. `/web` computes none of them.
- **No URL and no data source name is written in `/web`.** Player photos and the arena photo come from the feed.
- **A section with no data is hidden, together with its tab.** A cell with no data is hidden; the cells around it keep their order.
- **Every user-facing string is translatable**, in English and Spanish. Award names, arena names, colleges and injury comments are shown as the feed sends them.
- **Names never break inside a word.** They wrap only at spaces or hyphens.
- **Every player photo falls back** to initials when the feed has none or it fails to load. Alternative text is never shown in place of an image.
- **Game links:** a game row or card links to `/game/{id}` only when the feed marks `detailAvailable: true`. Otherwise it is plain text, with no hover state.
- **Shared components are reused:** the nav row, `SectionTabs`, `BlueprintFrame`, `TeamMonogram`, `StatusTag`, `Kicker`, the next game card pattern of the game detail page, the loading skeletons and the footer.

### New components

| Component | What it is |
|---|---|
| `PlayerHeader` | Name block, status, injury card, photo with its fade and the four hero stats |
| `ProfileCells` | The player profile cells |
| `NextGameCard` | The next game card, shared by both pages |
| `RecentGames` | The player's last 5 games |
| `AveragesTable` | Per-game averages: regular season, playoffs and career |
| `SeasonsTable` | Season by season, with its two segmented controls |
| `Milestones` | The eight milestone cells |
| `GameLog` | The full game log with filter chips and "Show all" |
| `Awards` | The awards grid |
| `TeamHeader` | Team identity, record and the four header cells |
| `TeamOverview` | Arena, head coach and team colors |
| `TeamRecord` | The large record row and the detail row |
| `TeamLeaders` | The three leader cards |
| `RosterTable` | The roster table |
| `TeamInjuries` | The injury list |
| `TeamSchedule` | The schedule with month chips |

## Shared patterns

- Ground `#0c0e10`, ink `#ebe8e3`, muted `#a19d96`, accent `#749dc4`, accent text `#94bce3`, hover link `#b5d9fd`. Divider `color-mix(in srgb, #ebe8e3 13%, transparent)`; table row rules `rgba(235,232,227,.07)`. All through the existing tokens.
- Headings Barlow Condensed 600, body Barlow. Numbers use `font-variant-numeric: tabular-nums`.
- Content max width 1320px, side padding `clamp(20px, 4vw, 48px)`, section gap `clamp(64px, 8vw, 104px)`, `scroll-margin-top: 72px`.
- Section header: h2 `clamp(28px, 3.4vw, 40px)`, line-height 1, uppercase; optional meta on the right, 12px, muted.
- **Stat cell:** 1px divider top border; label 11px, .16em, uppercase, accent text; value in Barlow Condensed; sub-line 13px, muted. Cells sit in `repeat(auto-fit, minmax(min(100%, Npx), 1fr))`.
- **Tables:** the first column is `position: sticky; left: 0` with the ground background. A table scrolls horizontally inside `overflow-x: auto` once the viewport is narrower than its min width. No cell wraps.
- The nav row and the sticky section tabs are the game detail page's.

## Player page

### 1. Header

- Background and nav as on the game detail page.
- Two blocks in a wrapping flex row, `align-items: flex-end`:
  - **Text,** `flex: 1 1 380px`: the team tag and a status tag (`Active`, or the injury status in accent); the first name, `clamp(18px, 2vw, 26px)`, uppercase, muted; the last name as the h1, `clamp(46px, 6.6vw, 100px)`, line-height .88; then `#2 · Guard · Oklahoma City Thunder`. When the player is injured, a blueprint card below shows the status, the comment and the update time.
  - **Photo,** `flex: 1.5 1 460px`, aspect ratio 1040 / 760, from the feed. No frame and no background behind the player. It bleeds to the page edge (negative right margin equal to the side padding) and overlaps the hero stats below by `clamp(48px, 7vw, 110px)`. Bottom fade: `mask-image: linear-gradient(to bottom, #000 58%, transparent 96%)`. Drop shadow `0 24px 28px rgba(0,0,0,.6)`. Without a photo, the block is not rendered and the text takes the full width.
- **Scroll behavior:** as the photo scrolls under the top of the viewport it fades out and drifts down. `p = clamp((90 − photoTop) / (photoHeight × 1.1), 0, 1)`; `opacity: 1 − p`; `transform: translateY(p × 60px)`, updated on scroll with `requestAnimationFrame`. No blur, no scale, nothing appears in its place. Not applied under reduced motion.
- **Hero stats:** four cells, min 140px: Points, Rebounds, Assists and FG%. Value `clamp(44px, 5vw, 68px)`; sub-line the rank, such as `41st in NBA` / `41.º en la NBA`. The section label above names the season, such as `2025-26 · per game`.
- On mobile the photo stacks under the name, with the same fade and scroll behavior.

### 2. Tabs

Profile · Averages · Seasons · Milestones · Game log · Awards. Mini name on the right, such as `#4 S. Barnes`.

### 3. Profile, next game and last 5

Two columns, `repeat(auto-fit, minmax(min(100%, 440px), 1fr))`.

- **Profile** cells, min 180px: Height (sub: centimeters), Weight (sub: kilograms), Born (date; sub: `Age 25`), Birthplace (sub: country), College, Draft (`2021 · Round 1 · Pick 4`; sub: team name; `Undrafted` when the feed says so), Seasons (count; sub: `Debut 2021-22`).
- **Next game:** the next game card (tag, date, opponent, `arena · city`, `time · TV`, and "Game center →" when the game has a detail page). When the feed has no next game, a muted line: "Season over." / "Temporada terminada."
- **Last 5 games:** rows on `22px 52px 1fr auto`: the result (W in accent text, L muted), the date, `vs` / `@` plus the opponent code, the score with the tag under it, and the points (20px) with `REB · AST` under them. Each row links to its game per the game link rule.

### 4. Per-game averages

Meta: "Regular season, playoffs and career". Rows: Regular season and Playoffs of the latest season in the feed (each labeled with its season, such as `2025-26`), and Career (label in accent text). A row with no games shows `—` in every cell. Columns: GP, MIN, FG%, 3P%, FT%, REB, AST, BLK, STL, PF, TOV, PTS. PTS in Barlow Condensed 18px. GP, MIN, PF and TOV muted.

### 5. Season by season

- Two segmented controls: **Per game / Totals** and **Regular / Playoffs**. The Playoffs option is hidden when the player has no playoff seasons.
- Rows newest first, with the team code under the season. A season played for more than one team shows its combined row with all the codes, such as `DAL · LAL`. The last row is Career.
- Columns: GP, GS, MIN, FG (made–attempted), FG%, 3PT, 3P%, FT, FT%, OREB, DREB, REB, AST, BLK, STL, PF, TOV, PTS. In Totals the MIN column is not shown.

### 6. Milestones

Eight cells, min 128px: Double-doubles, Triple-doubles, Disqualifications, Ejections, Technical fouls, Flagrant fouls, AST/TO, STL/TO. The value is the latest regular season; the sub-line `Career N`. Two columns on mobile.

### 7. Game log

- The section meta names the season.
- Filter chips: All · Regular season · NBA Cup · Playoffs. "Regular season" shows regular and NBA Cup games. A chip with no games is hidden.
- Newest first. The first column shows `Apr 29 · @ MEM` with a tag line under it (`West R1 · G4`, `NBA Cup`, `All-Star`). Columns: Result (`W 118–104`, W in accent text), MIN, FG, FG%, 3PT, 3P%, FT, FT%, REB, AST, BLK, STL, PF, TOV, PTS.
- Shows 20 rows with a "Show all N games" toggle. Rows link per the game link rule.

### 8. Awards

Two columns, min 420px. The count `3×` (36px, accent text), the award name (21px, uppercase) and the seasons joined with ` · `, such as `2023-24 · 2024-25`.

## Team page

### 1. Header

Two columns, min 440px:

- **Left:** the code box, `clamp(64px, 7vw, 88px)`, with a 5px strip under it split into the primary and secondary team colors from the feed; the city (uppercase, muted); the team name as the h1, `clamp(52px, 8vw, 120px)`; then `Western Conference · Northwest Division`.
- **Right:** the record `57–25`, `clamp(64px, 8vw, 112px)`; the win percentage, 24px, accent text; and four cells: Conference (`1st West`), Streak (`W3`), Last 10, Playoffs (`1st seed`, `Play-in` or `Out`). The Playoffs cell is hidden when the feed has no playoff position.

### 2. Tabs

Overview · Record · Leaders · Roster · Injuries · Schedule. Mini `OKC 57–25` on the right.

### 3. Overview

- **Arena:** a 16:10 blueprint frame with the arena photo **in its original colors** and a bottom gradient, the label "Home arena", the arena name and the city over it. **Without a photo the frame is not shown:** the label, the arena name and the city are shown as a stat cell, in the same position and order.
- **Head coach:** the name and `N seasons as NBA head coach`.
- **Team colors:** two 26px swatches with their hex values.
- **Next game:** the next game card, as on the player page.

### 4. Record

- **Large row:** Overall, Home, Away and Last 10, each as `W–L` with the win percentage.
- **Detail row:** Streak, Games behind, Playoff position, Conference, Division, Points for (per game; sub: total), Points against (per game; sub: total), Differential (`+8.4`; sub: total `+689`).

### 5. Team leaders

Three blueprint cards, min 280px: Points, Rebounds and Assists per game. Value 56px, the player name, `#2 · Guard`, and the photo on the right in a 96px column (initials without one). The meta names the season the values belong to. Each card links to the player page.

### 6. Roster

A table in the order the feed sends (by number). Columns: Player (40px photo or initials, then the name, linking to the player page), No., Pos, Ht, Wt, Age, Born, Birthplace, College, Exp (`R` for a rookie), Status (`Active`; `Out` in accent; `Doubtful` and `Questionable` in ink; other statuses muted). The first column is 220px on desktop and 170px under 680px.

### 7. Injuries

Meta: "Official injury report". Two columns, min 420px. The name with `#num · Position`, the status tag on the right and the comment under it, 13px, muted. "No injuries reported." when the list is empty.

### 8. Schedule

- Month chips in the order the feed sends (Oct → Apr, then Playoffs). The selected chip on load is the one the feed marks as default.
- Rows on `84px 1fr auto` (`52px 1fr auto` under 680px): the date with the weekday above; `vs` / `@` and the opponent code with a tag (`NBA Cup`, `West R1 · G3`, `Next`); on the right, a played game shows `W 118–104` (W in accent text) and Home / Away, an upcoming game shows the time and the broadcaster.
- The next game row is tinted `rgba(116,157,196,.08)` and tagged `Next`. Rows link per the game link rule.

## Links into these pages

- Player names in the game detail page's box score, players to watch and injuries link to `/player/{id}`.
- Team names and codes on the home page and the game detail page link to `/team/{code}`.
- A link is never nested inside a button or another link. Where a name sits inside one (such as the collapsed schedule row, which is the expand control), it stays plain text.

## States

| State | What shows |
|---|---|
| Loading | Skeletons shaped like the header and the first section, with the home's shimmer, stopped under reduced motion |
| Feed unavailable | The nav row, then the home's "Data isn't available right now. Check back later." row (a 503 or a failed request; polling continues, and the page fills in when a later request succeeds) |
| Unknown player or team | The nav row, then a blueprint row reading "Player not found." or "Team not found." with a link back to all games (the feed answers 404: an unknown id, or a team code that is not lowercase) |
| Partial data | A null field hides its cell, and a section without data hides with its tab |
| Start of a season | Sections whose season has no data yet are hidden, together with their tabs |

## Interactions and motion

| What | How |
|---|---|
| Polling | Every 60 seconds; paused while the tab is hidden and refreshed when it is visible again |
| Section tabs | Smooth scroll; instant under reduced motion |
| Segmented controls and chips | Switch the rows shown; the selection is not kept between visits |
| Player photo | The scroll fade described in the header; none under reduced motion |
| Focus | `:focus-visible` as on the home |

## Responsive

- Under 680px: the photo stacks under the name, the milestones use two columns, tables scroll horizontally with their sticky first column, and the schedule's date column narrows to 52px.
- Every other section reflows through its auto-fit grid.

## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601. Every value below is computed by the backend.

### Shared objects

| Object | Fields |
|---|---|
| `GameTag` | `kind`: `cup`, `playoffs` or `allstar`; `conference`: `east`, `west` or null; `round`: 1 to 4 or null (4 is the Finals); `game`: number or null |
| `NextGame` | `gameId`, `startTime`, `opponent` (code), `isHome`, `tag` (`GameTag` or null), `arena`, `city` (or null), `broadcast` (or null), `detailAvailable` |
| `Injury status` | the game detail feed's `InjuryStatus` values |

### Player feed

| Field | Content |
|---|---|
| `id`, `firstName`, `lastName` | Identity |
| `number`, `position` | Jersey number (or null) and position name |
| `team` | `code`, `name`, `city` |
| `photoUrl` | Or null |
| `injury` | `status`, `comment` (or null), `updatedAt`; null when healthy |
| `profile` | `height` (`display`, `cm`), `weight` (`lb`, `kg`), `birthDate`, `age`, `birthplace` (`place`, `country`), `college`, `draft` (`year`, `round`, `pick`, `teamName`; null when undrafted), `seasons` (count), `debutSeason`; each field null when unknown |
| `summary` | `season` and four stats, `points`, `rebounds`, `assists`, `fieldGoalPct`, each `value` and `rank` (or null) |
| `nextGame` | `NextGame` or null; null shows "Season over." |
| `live` | The live game of the player's team, taken from its live game detail at serve time: `gameId`, `opponent` (code), `isHome`, `period`, `clock`, `teamScore`, `opponentScore`, `line` (the game detail feed's `BoxScorePlayer` for the player, or null before the player enters the box score); null when the team has no live game |
| `lastGames` | Up to five game log entries, newest first, All-Star excluded |
| `averages` | `regular`, `playoffs` (each with its `season`) and `career`: GP, MIN, FG%, 3P%, FT%, REB, AST, BLK, STL, PF, TOV, PTS; a row with no games is null |
| `seasons` | `regular` and `playoffs`, each with `perGame` and `totals` row lists, newest first, plus a `career` row. A row: `season`, `teams` (codes), GP, GS, MIN (null in totals), FGM, FGA, FG%, 3PM, 3PA, 3P%, FTM, FTA, FT%, OREB, DREB, REB, AST, BLK, STL, PF, TOV, PTS |
| `milestones` | `season`, `current` and `career`: double-doubles, triple-doubles, disqualifications, ejections, technicals, flagrants, AST/TO, STL/TO |
| `gameLog` | `season` and `entries`, newest first. An entry: `gameId`, `date`, `opponent` (code, or null for All-Star), `isHome`, `kind` (`regular`, `cup`, `playoffs`, `allstar`), `tag` (`GameTag` or null), `result` (`win`, `loss`), `teamScore`, `opponentScore`, MIN, FGM, FGA, FG%, 3PM, 3PA, 3P%, FTM, FTA, FT%, REB, AST, BLK, STL, PF, TOV, PTS, `detailAvailable` |
| `awards` | `name`, `count`, `seasons` (labels such as `2025-26`) |

### Team feed

| Field | Content |
|---|---|
| `code`, `city`, `name` | Identity |
| `conference`, `division` | `east` / `west`, and the division name |
| `colors` | `primary`, `secondary`: hex values |
| `arena` | `name`, `city` (or null), `photoUrl` (or null) |
| `coach` | `name`, `seasons`; or null |
| `season` | Label, such as `2026-27` |
| `record` | `wins`, `losses`, `winPct`; `home`, `away`, `lastTen` (each `wins`, `losses`, `winPct`); `streak` (`kind` win / loss, `count`; or null); `gamesBehind`; `conferenceRank`; `divisionRank`; `playoff` (`status` seed / playin / out, `seed`; or null before the first game); `pointsFor`, `pointsAgainst`, `differential` (each `perGame`, `total`) |
| `leaders` | `season` and `points`, `rebounds`, `assists`: `playerId`, `name`, `number`, `position`, `photoUrl`, `value`; each or null |
| `roster` | Ordered by number: `id`, `name`, `number`, `position` (abbreviation), `height`, `weight` (lb), `age`, `birthDate`, `birthplace`, `college`, `experience` (0 is a rookie), `photoUrl`, `status` (`active` or an injury status); each detail null when unknown |
| `injuries` | `playerId`, `name`, `number`, `position`, `status`, `comment`, `updatedAt` |
| `nextGame` | `NextGame` or null |
| `schedule` | `groups` in display order, each `key` (such as `2025-10` or `playoffs`) and `games`; `defaultGroup`. A game: `gameId`, `startTime`, `opponent`, `isHome`, `kind`, `tag`, `result` (or null), `teamScore`, `opponentScore` (or null), `broadcast` (or null), `isNext`, `detailAvailable` |