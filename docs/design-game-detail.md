# Design: game detail page

The visual and interaction specification for the game detail page. It extends `docs/design.md`: every token, rule and shared component defined there applies here. Colors, type, spacing and motion are final: build pixel-close to this document.

## Overview

One page per game, at `/game/{id}`, with three layouts driven by the game's status:

| Status | Layout |
|---|---|
| scheduled, delayed, postponed, canceled | Pre-game |
| live | Live |
| final | Final |

The page receives all its data from the game's detail feed. It holds no business rules: every value it shows, including totals, percentages, standings ranks, the season series and the win probability, comes ready from the feed.

## Implementation rules

Everything under "Implementation rules" in `docs/design.md` applies, plus:

- **No URL and no data source or platform name is written in `/web`.** Images, video players, video links and the video platform name come from the feed or from build-time configuration.
- **A section with no data is hidden, together with its tab.** This is how the page handles data a source does not provide for a given game.
- **Every user-facing string is translatable**, in English and Spanish. The copy in this document is the English text.
- **Team and player names never break inside a word.** Long names wrap only at spaces. Text that still does not fit is reduced in size by its clamp, never split.
- **Every player photo falls back to the placeholder** used by `PlayerCutout` when it fails to load. Alternative text is never shown in place of an image.
- **Shared components are reused:** `BlueprintFrame`, `TeamMonogram`, `LiveBadge`, `StatusTag`, `Kicker`, `LineScore`, `TeamStats`, `Highlights` and the loading skeletons. A section extends a shared component instead of copying it.

### New components

| Component | What it is |
|---|---|
| `GameHeader` | Navigation, status line, scoreboard and the pre-game venue strip |
| `SectionTabs` | The sticky section tabs, with the mini score on live and final games |
| `PlayersToWatch` | The two star cards |
| `WinProbability` | The win probability chart |
| `BoxScore` | The full box score with its team toggle |
| `Injuries` | Injury lists for both teams |
| `LastGames` | Last five games of each team |
| `StandingsRows` | The two teams' standings rows |
| `SeasonSeries` | The season series summary and its games |
| `GameVideos` | The grid of video links |

## Entry point

In the home page's expanded game card, a link reads **"Game center"** and leads to `/game/{id}`:

- Live and final games: bottom right of the team stats column, under the last stat bar.
- Scheduled games: bottom right, under "Players to watch".

The link appears only on the cards that expand on the home page: scheduled, live and final. Delayed, postponed and canceled cards do not expand (`docs/design.md`), so they carry no link. Their pages stay reachable at `/game/{id}`.

Style: Barlow Condensed 600, 14px, letter-spacing .12em, uppercase, accent-light (hover ink), with a 10px gap to an 18px Lucide `arrow-right` at stroke 1.5.

## Page structure

Max content width 1320px, side padding `clamp(20px, 4vw, 48px)`. Sections stack with a gap of `clamp(64px, 8vw, 104px)`. Every section uses `scroll-margin-top: 72px`.

### Section header

The h2 is Barlow Condensed, `clamp(28px, 3.4vw, 40px)`, line-height 1, uppercase. An optional meta text sits on the right, 12px, muted.

### 1. Header

- Background: bg with the 88px grid of 1px lines in grid-line. The bottom border is a divider.
- **Nav row:** the brand mark and "COURTSIDE" on the left, as on the home. On the right, "All games" (15px, .1em, uppercase) with a Lucide `arrow-left`, linking to the home.
- **Status line,** centered, 13px, .08em, uppercase, muted:
  - Scheduled: `Wednesday, October 7 · Chase Center`.
  - Delayed, postponed, canceled: the `StatusTag` with "Delayed", "Postponed" or "Canceled", then the date and arena.
  - Live: the `LiveBadge`, then `Q3 · 4:12 · Chase Center`. Between periods it reads "Halftime" or "End of Q1". Overtime periods read "OT1", "OT2".
  - Final: `Final · Wednesday, October 7 · Chase Center`.
- **Desktop scoreboard,** from 680px: a grid `1fr auto 1fr`, gap `clamp(16px, 4vw, 64px)`.
  - Team block: a `TeamMonogram` box, `clamp(56px, 6vw, 80px)` square; then the city (13px, uppercase, muted), the team name as the h1 (`clamp(32px, 4.4vw, 64px)`, line-height .9, uppercase, never broken inside a word) and the record, such as `12–5` (14px, muted, tabular). The home team block is mirrored and right-aligned.
  - Center, live and final: the score in Barlow Condensed 600, `clamp(56px, 8vw, 120px)`, tabular. The dash between the scores is .4em, muted and vertically centered.
  - Center, pre-game: the tip-off time, `clamp(44px, 6vw, 88px)`, with its "PM ET" suffix at .4em, muted, and the broadcast under it. A delayed game shows "Scheduled" before the original time. Postponed and canceled games show no time.
  - Final: the losing team's block and score drop to opacity .45. The winner comes from the feed.
- **Mobile scoreboard,** under 680px: two rows, each with a 48px monogram, the name (26px), `city · record` (12px) and the score right-aligned (44px). Pre-game adds a time row (36px, plus the broadcast).
- **Pre-game venue strip:** a grid `repeat(auto-fit, minmax(min(100%, 340px), 1fr))`.
  - Arena photo: a 16:9 `BlueprintFrame` holding the photo in its original colors, with a bottom gradient to `rgba(12,14,16,.85)`. The arena name (22px, uppercase) and city sit over it. Without a city, the arena name sits alone, with no empty line. Without a photo, or when the photo fails to load, the frame shows the 44px grid with the arena name and city over it in the same type, and no gradient. The frame is never empty.
  - Info cells: Tip-off, Venue and Broadcast. Label 11px, .16em, uppercase, accent-light; value 22px Barlow Condensed; sub-line 13px, muted. The Venue cell shows the arena as its value and the city as its sub-line; without a city it has no sub-line.

### 2. Section tabs

Sticky at the top of the viewport. Background `rgba(12,14,16,.9)` with a 12px backdrop blur and a bottom divider. Anchor links in Barlow Condensed 600, 14px, .12em, uppercase, muted, hover ink, 16px vertical padding. On mobile the row scrolls horizontally. Live and final games add the mini score on the right, such as `OKC 78 – 74 GSW` (15px). The bar stacks above the page content at `z-index` 1, through the `--tabs-z-index` token; nothing else on the page sets a `z-index` at or above it, so the tabs stay clickable while scrolling.

| Layout | Tabs, in order |
|---|---|
| Pre-game | Players · Injuries · Last 5 · Standings · Season series |
| Live | Score · Win prob. · Box score · Injuries |
| Final | Highlights · Score · Win prob. · Box score · Injuries · Series · Videos |

A tab is shown only when its section has data. Tab links scroll smoothly, and instantly under reduced motion.

### 3. Highlights (final)

The `Highlights` component from the home, at a max width of 1040px, with a 72px play square. The section meta shows the video platform name from configuration. While highlight attempts remain, and after they run out, it behaves exactly as on the home.

### 4. Players to watch (pre-game)

Two cards in a grid `repeat(auto-fit, minmax(min(100%, 380px), 1fr))`. Each card is a `BlueprintFrame` split into two columns, with a min height of 240px:

- Left: the team tag (11px, 1px divider border), the first name (15px, uppercase, muted), the last name (`clamp(24px, 3vw, 38px)`, wrapping only at spaces or hyphens) and the full team name (13px, muted).
- Right: the player photo, as tall as the card's photo column with its width set by the photo's own proportions and never wider than the column, anchored to the bottom center so the head and shoulders show whole at every width, over a radial glow `rgba(116,157,196,.26)`, with a 1px divider on its left edge. It falls back to the placeholder.

The stars are the ones the feed carries for the game.

### 5. Line score and team stats (live, final)

Two columns, `repeat(auto-fit, minmax(min(100%, 440px), 1fr))`.

- **Line score:** the `LineScore` component, extended to a grid `1fr repeat(N, minmax(32px, 52px)) minmax(52px, 68px)`, with N at 4 or more. Overtime columns read "OT1", "OT2". The team cell shows the code (18px) and the team name (13px, muted, ellipsis). The total is 24px Barlow Condensed. Unplayed periods show "–".
- **Team stats:** the `TeamStats` component with eight rows: FG%, 3P%, FT%, Rebounds, Assists, Turnovers, Steals and Blocks. The leading side comes from the feed: for turnovers, lower leads. Bars animate their width over .6s with the default easing.

### 6. Win probability (live, final)

- A `BlueprintFrame` with a 40px y-axis column: the home team code at the top, "50%" in the middle and the away team code at the bottom.
- The chart is an SVG, `viewBox 0 0 1000 200`, height `clamp(180px, 24vw, 280px)`:
  - A dashed 50% line in `rgba(235,232,227,.22)`, and a gridline in row-rule at the start of every period after the first, with none at the left edge. The x axis runs from 0 to the game's end as the feed sends it, so a regulation game has its gridlines at 250, 500 and 750, and overtime periods narrow every period inside the same chart width.
  - The area between the line and 50% as one shape under the whole line, filled with `rgba(116,157,196,.12)`, and the line itself 2px in accent-light, with a non-scaling stroke.
  - A 9px square marks the latest point, with a 4px ring in `rgba(116,157,196,.25)`. While the game is live, the marker pulses: its opacity goes from 1 to .5 and back over 2s (`--win-prob-marker-pulse-duration`, with `--win-prob-marker-pulse-opacity` for the low point), ease-in-out, looping. Only the opacity changes: the marker keeps its size and position. On a final game the marker is still. Under reduced motion it does not pulse.
- Y is the home team's win probability (top is 100% home). X is elapsed game time.
- One label per period runs under the chart, centered under its period: Q1 to Q4, then OT1, OT2 when present. Without period boundaries in the feed, the chart draws no gridlines and no labels, and its x axis spans the points.
- The section meta, 26px, accent-light, shows the leading team and its percentage from the feed, such as `GSW 68%`. With no leader, on an exactly even latest point, it reads `Even` (Spanish `Parejo`). On a final game it reads `OKC win`.

### 7. Box score (live, final)

- A segmented toggle to pick the team: a 1px divider border, the active side filled with `rgba(116,157,196,.14)`. Team names on desktop, team codes on mobile. The away team is selected first.
- The table is a CSS grid, `minmax(150px, 2fr) repeat(14, minmax(52px, 1fr))`, with the shooting columns (FG, 3PT, FT) at `minmax(64px, 1fr)`. Its min width is 1040px and it scrolls horizontally. The player column is sticky, on a bg background.
- Columns: MIN, PTS, FG, 3PT, FT, OREB, DREB, REB, AST, TOV, STL, BLK, PF, +/-. No cell ever wraps.
- Groups: Starters, Bench, then Totals, with FG%, 3P% and FT% under the shooting columns.
- Type: player names 17px Barlow Condensed; PTS 18px Barlow Condensed; MIN, OREB and DREB muted. A positive +/- shows in ink with its "+"; zero and negative values show muted.
- Row hover: `rgba(116,157,196,.06)`.

### 8. Injuries (all layouts)

- Two team columns, `repeat(auto-fit, minmax(min(100%, 420px), 1fr))`. Each has a team header: a 36px monogram and the team name.
- Each row: the player name (18px) and a status tag (10.5px, .14em, uppercase, 1px border). The source's comment, when present, sits below in 13px muted and is shown as it comes, in English.
- Status tags, translated:

| Status | English | Spanish | Style |
|---|---|---|---|
| out | Out | Fuera | Accent border, accent-light text |
| doubtful | Doubtful | Dudoso | Divider border, ink text |
| questionable | Questionable | En duda | Divider border, ink text |
| probable | Probable | Probable | Divider border, muted text |
| day-to-day | Day-to-day | Día a día | Divider border, muted text |

- A team with no injuries shows "No injuries reported."
- The section meta reads "Injury report".

### 9. Last 5 games (pre-game)

- Two team columns. The team header has a strip of five 22px squares, oldest to newest: a win is filled accent with dark text, a loss is outlined.
- Rows, newest first, on a grid `24px 56px 1fr auto`: the result (W in accent-light, L muted), the date (`Oct 5`), the opponent (`vs DEN` at home, `@ DEN` away) and the score with the team's points first (`118–104`).

### 10. Standings (pre-game)

A grid `minmax(150px, 2fr) repeat(5, minmax(76px, 1fr))`, min width 560px, scrolling horizontally with a sticky team column. Columns: Team, Conference (rank plus conference, such as `3rd West`), Record, Home, Away, Last 10.

### 11. Season series (pre-game, final)

- Two columns. On the left, the summary in large type, `clamp(40px, 5vw, 64px)`: `OKC lead 2–1`, `Series tied 1–1` or `First meeting`. The meta reads `2 of 4 games played`.
- On the right, one row per game: the date, or "This game" in accent-light for the current game; then `AWAY pts – pts HOME` with the losing side at .45 opacity; and the arena under the score, wrapping on mobile.
- Before tip-off, the current game's row shows the team codes with no points.
- The feed also marks the current game on a live page, where this section is not shown.
- On a final game, the current game is part of the series the feed sends.

### 12. Videos (final)

- A grid `repeat(auto-fill, minmax(240px, 1fr))` on desktop, two columns on mobile.
- Each card is a `BlueprintFrame` link that opens in a new tab: a 16:9 thumbnail (the 44px grid when there is none), a 40px solid-accent play square, a duration chip at the bottom right, then the title (17px) and a Lucide `arrow-up-right`.
- Hover: the border turns accent.
- The section meta reads "Opens in a new tab". These videos are links, never embedded.

### Footer

The same footer as the home.

## States

| State | What shows |
|---|---|
| Loading | Skeletons shaped like the header and the first two sections, with the same shimmer as the home, which stops under reduced motion |
| Feed unavailable | The header's nav row, then the home's "Data isn't available right now. Check back later." row |
| Unknown game | The nav row, then a blueprint row reading "Game not found." with a link back to all games |
| Postponed or canceled | The pre-game layout with its status tag; sections with no data are hidden |

## Interactions and motion

| What | How |
|---|---|
| Polling | Same rules as the home: every 30 seconds while the game is live, every 60 seconds otherwise; paused while the tab is hidden and refreshed as soon as it is visible again |
| Section tabs | Smooth scroll to the section; instant under reduced motion |
| Highlights | As on the home: the thumbnail is replaced by the autoplaying player on click |
| Box score toggle | Switches the team shown; away first |
| New data while live | Values update in place. The win probability line extends without redrawing the whole chart |
| Win probability marker | While the game is live, the latest point marker pulses: opacity 1 to .5 and back over 2s, ease-in-out, looping. Still on a final game. Off under reduced motion |
| Spoiler-free mode | Does not apply on this page: it is reached from a card that is already expanded |
| Focus | `:focus-visible` as on the home |

## Responsive

- Under 680px: the mobile scoreboard, team codes in the box score toggle, and the tabs scrolling horizontally.
- Every other section reflows through its auto-fit grid.
- Hit targets are at least 44px.