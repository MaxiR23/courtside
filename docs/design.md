# Design

The visual and interaction specification for the Courtside site. It is the reference for every front end change. Colors, type, spacing, motion and copy are final: build pixel-close to this document.

The game detail page is specified in [`design-game-detail.md`](design-game-detail.md).

## Overview

A dark-mode, single-page site with two parts:

1. **Hero.** A rotating hero that goes through the games of the day, leaving out postponed and canceled games. Each game shows the star player of each team as a transparent cutout, 7 seconds each, then the next game starts.
2. **Schedule.** A 7-day strip with today in the middle and the list of games for the selected day. Clicking a game expands its details: line score, top performers, team stats and, once the game is final, official highlights embedded inline.

## Implementation rules

- **Tokens live in one place.** Every color, font, size, spacing value, shadow and easing in this document is a design token, defined once as a CSS custom property in a single tokens file. Components use tokens and never repeat raw values.
- **Scoped styles.** Each component styles itself with its own scoped styles, built from tokens. No global styles beyond the tokens and the base page styles.
- **Components receive data through props**, with their own types. No component reads a feed directly. A separate layer turns feed data into props.
- **Reusable primitives first.** Shared pieces, such as the blueprint frame, are built once and reused everywhere they appear.
- **Every user-facing string is translatable**, in English and Spanish. The copy in this document is the English text.
- **Reduced motion.** When the system asks for reduced motion, entrance animations, the idle float, the parallax, the skeleton shimmer and the live win probability marker pulse are disabled, and transitions become instant or simple fades.

### Components

| Component | What it is |
|---|---|
| `BlueprintFrame` | The framed box with corner registration marks, used across the site |
| `Hero` | The top section, rotating through the games of the day |
| `PlayerCutout` | A player's transparent photo, framed and lit |
| `DayStrip` | The 7-day selector |
| `ScheduleSkeleton` | The schedule's placeholder while the first feed loads: the day strip and game cards |
| `GameCard` | One game, with its desktop and mobile rows and its expanded panel |
| `LineScore` | Points per quarter |
| `Leaders` | Top performer per team |
| `TeamStats` | Team stat comparison with bars |
| `Highlights` | The video cards of a final game |
| `MessageRow` | A single blueprint row holding one muted message |
| `NameLink` | A player or team name as a link, or as plain text when the href is null |

## Design tokens

### Color

Dark only. There is no light mode.

| Token | Value | Use |
|---|---|---|
| bg | `#0c0e10` | Page ground |
| surface | `#14171a` | Rarely used: skeleton blocks |
| frame-fill | `#11161b` | Inside image frames and video thumbnails |
| ink | `#ebe8e3` | Primary text, a warm off-white |
| muted | `#a19d96` | Secondary text |
| accent | `#749dc4` | Steel blue: primary button, live badge border, active borders, leading stat bars |
| accent-light | `#94bce3` | Accent text on dark: kickers, "Today", player team code, links. Name links (player and team names) are the exception: they keep the surrounding text color and change color only on hover |
| accent-hover | `#b5d9fd` | Link hover |
| bar-neutral | `#424244` | Trailing stat bar |
| divider | `color-mix(in srgb, #ebe8e3 13%, transparent)` | Every hairline border |
| row-rule | `rgba(235,232,227,.07)` | Line score row separators |
| grid-line | `rgba(235,232,227,.035)` | Hero background grid |
| open-tint | `rgba(116,157,196,.045)` | Background of an expanded game card |
| selected-day | `rgba(116,157,196,.12)` | Background of the selected day cell |

The only color besides the neutrals is the steel accent. No team colors, except on the team page, which draws the team's colors as `docs/design-profiles.md` requires.

### Type

- **Headings:** Barlow Condensed 600, with 400 and 600 loaded from Google Fonts. Usually uppercase.
- **Body:** Barlow 400 and 500.
- **Small labels and kickers:** 11px, `letter-spacing: .16em`, uppercase.
- Scores and stats use `font-variant-numeric: tabular-nums`.

| Element | Size | Notes |
|---|---|---|
| Hero h1 | `clamp(54px, 9.5vw, 148px)` | line-height .86, letter-spacing -.02em, uppercase. The second line starts with "at" in muted at .42em |
| Hero watermark | `clamp(180px, 26vw, 420px)` | Transparent fill, `-webkit-text-stroke: 1px rgba(235,232,227,.13)` |
| Section h2 | `clamp(40px, 5vw, 64px)` | line-height .95 |
| Team name, desktop row | `clamp(18px, 2.2vw, 26px)` | Uppercase |
| Team name, mobile row | 20px | |
| Score, desktop | `clamp(32px, 4vw, 46px)` | |
| Score, mobile | 30px | |
| Scheduled tip time | `clamp(28px, 3.4vw, 38px)` | The suffix "PM ET" at .45em, muted |
| Player name, panel | 19px | |
| Body and blurbs | 17px in the hero, 13 to 14px elsewhere | |

### Shape and elevation

- **Square corners everywhere** (radius 0).
- **Blueprint frame:** a 1px divider border plus four "+" registration marks, 11 by 11px, made of 1px lines in `color-mix(in srgb, ink 55%, transparent)`, centered on each corner (offset -6px). Used on game cards, the hero image frame, the player chip, highlight cards and the primary button.
- **Hero frame shadow:** `0 50px 100px -24px rgba(0,0,0,.9), 0 20px 40px -20px rgba(0,0,0,.7)`.
- **Floor shadow** under the hero frame: an ellipse, `radial-gradient(rgba(0,0,0,.9), transparent 70%)`, blur 10px, 56px below the frame.
- **Skeleton widths:** tag and indicator 72px, kicker and buttons 160px, short lines 40% and long lines 80% of the column.
- **Accent glow** behind the hero frame: `radial-gradient(circle at 50% 45%, rgba(116,157,196,.24), transparent 62%)`, extending 18% past the frame on every side.

### Spacing

- Max content width: 1320px.
- Side padding: `clamp(20px, 4vw, 48px)`.
- Game list gap: 14px. Day strip gap: `clamp(4px, 1vw, 8px)`. Expanded panel section gap: 36px.

### Motion

- Default easing: `cubic-bezier(.2,.7,.1,1)`, unless a section says otherwise.
- **Skeleton shimmer:** opacity from 1 to .5 and back over 1.6s, ease-in-out, looping. None under reduced motion.
- **Live marker pulse:** the win probability marker's opacity goes from 1 to .5 and back over 2s, ease-in-out, looping, while the game is live. None under reduced motion. See `docs/design-game-detail.md`, section 6.

### Icons

Lucide at `stroke-width: 1.5`: `chevron-down` (expand), `play` (filled, highlight play button), `external-link`.

## Screens

### 1. Hero

- **Nav row:** the brand mark (a 22px square outline in accent with an 8px solid accent square inside) and "COURTSIDE" in Barlow Condensed 20px with .12em letter-spacing. Then today's date in muted ("Sun, Oct 4, 2026") and a "GAMES" anchor to the schedule. The row wraps on narrow screens.
- **Layout:** a two-column grid, `repeat(auto-fit, minmax(min(100%, 440px), 1fr))`, that stacks on mobile. Gap `clamp(40px, 6vw, 96px)`, min-height `min(820px, 88vh)`.
- **Background:** an 88px square grid of faint lines. A huge outlined watermark of the current star's short name sits behind the content on the right.
- **Left column, top to bottom:**
  1. A status tag, "Tonight", "Live now", "Final", "Delayed", "Postponed" or "Canceled", 11px in a 1px divider box. Next to it the kicker with the tip time and arena, such as "10:30 PM ET · Chase Center". For a delayed game the kicker reads "Scheduled" and the original tip time and arena, such as "Scheduled 7:30 PM ET · Chase Center".
  2. The h1: the away team name, a line break, then "at" and the home team name.
  3. A blurb: "{Away star} and {Home star} meet at {Arena}."
  4. Buttons. **Match details** is the primary button (solid accent, dark text, blueprint marks): it selects today, expands the game on screen and smooth-scrolls to it. **All games** is a secondary outlined button linking to the schedule.
  5. A slide indicator with two items. Each has a 2px progress track whose fill (`#94bce3`) grows linearly over 7s on the active item, so it shows the progress of the current star. Under it, "01" or "02" and the player's short name: the active one in ink, the inactive in muted. Clicking an item jumps to that star. Next to the items, the current game's position among the games in the rotation, such as "03 / 10".

  The status tag, kicker, h1 and blurb always follow the game on screen.

  **Rotation.** The hero goes through the games of the day in feed order, leaving out postponed and canceled games, which stay in the schedule list. Delayed games stay in the rotation. Each game shows its two stars, 7 seconds each, then the next game starts. After the last game it returns to the first. With one game, the hero behaves as a single game: its two stars alternate and the position is not shown. With no games, or when every game of the day is postponed or canceled, the hero shows no game.
- **Right column:** the image frame, max-width 500px, aspect ratio 4:5. A blueprint frame filled with frame-fill, a 44px grid and the accent glow.
  - The star's cutout is a transparent player photo in full color, anchored to the bottom center at **172% of the frame width**, so the head pops out above the frame's top edge. The bottom is clipped with `clip-path: inset(-30% 0 0 0)`.
  - Image filter: `drop-shadow(0 0 1px rgba(148,188,227,.35)) drop-shadow(0 30px 30px rgba(0,0,0,.7)) contrast(1.05)`.
  - A bottom fade covers the lowest 30% of the frame, from `rgba(12,14,16,.85)` to transparent.
  - **Player chip:** it overlaps the frame's bottom-left corner (left `clamp(-28px, -2vw, -10px)`, bottom 36px). A blueprint frame in `rgba(12,14,16,.82)` with a 12px backdrop blur, holding the team code (34px, accent-light), the first name (11px uppercase, muted), the last name (22px Barlow Condensed) and the full team name (12px, muted).

### 2. Schedule

- **Header:** the kicker "SCHEDULE" in accent-light, with the selected day as the h2 ("Sunday, October 4"). On the right, the game count ("5 games") in ink, and below it a freshness label in muted: "Recently updated" when the feed is under a minute old, and "Updated 3 min ago" from 1 minute on.
- **Day strip:** 7 equal columns, from today minus 3 days to today plus 3 days. Today is the feed's middle day: the US Eastern date, which the backend changes at midnight once no game of the previous day is live. Each cell shows the weekday (or "Today" in accent-light), the date number in Barlow Condensed `clamp(22px, 3vw, 32px)`, and the game count ("5 games" on desktop, "5" on mobile). The selected cell has an accent border and the selected-day fill. Hover: accent border.
- **Day with no games:** the header still shows the selected day and "0 games". In place of the game list, a single blueprint row reads "No games scheduled for this day." in muted.
- **Data unavailable (temporary):** when the games feed cannot be loaded, a single blueprint row in place of the schedule, styled like the day with no games, reads "Data isn't available right now. Check back later.". It stays until the missing data design is decided (see "Open decisions" in `docs/architecture.md`). A day with no data in a loaded feed is still undecided.
- **Game card,** a blueprint frame:
  - **Desktop row, width 680px and up:** grid `minmax(0,1fr) auto minmax(0,1fr) 24px`.
    - Away team: a 46px monogram box with the team's three-letter code, the team name and the city in muted.
    - Center: a status line, then the score or the tip time. The status line is "FINAL", or the live badge plus the period and clock ("Q3 · 4:12"), or "DELAYED", "POSTPONED" or "CANCELED" for those games, with no score and no tip time (those cards do not expand), or the TV network. The TV network is omitted when it is unknown.
    - Home team: mirrored and right-aligned.
    - A chevron that rotates 180 degrees when the card is open.
  - **Mobile row, under 680px:**
    - A status line with the chevron on the right.
    - Two team rows, each with a 38px monogram, the name and city, and the score right-aligned.
    - Scheduled games show the tip time and network in the status line, such as "9:00 PM ET · Courtside TV".
  - **Final games:** the losing team's name and score drop to opacity .42.
  - **Live badge:** small and outlined, never a dot. It reads "LIVE" at 9.5px with .16em letter-spacing, a 1px accent border and accent-light text, padding 1px by 5px.
- **Expanded panel:** a 1px divider, then the content below it.
  - **Live and final games** get a three-column auto-fit grid, min 280px per column:
    - **Line score:** a grid `1fr repeat(4, 34px) 46px`. The header row reads "Team 1 2 3 4 T". Quarters in muted, the total in Barlow Condensed 17px. Unplayed quarters show "–". Overtime periods add columns.
    - **Top performers:** one per team. Each has a 72 by 56px frame holding the full-color player photo (bottom-anchored, 120% width, `drop-shadow(0 6px 8px rgba(0,0,0,.6))`), the team code, the name, and the line "34 PTS · 3 REB · 8 AST".
    - **Team stats:** FG%, 3P%, Rebounds, Assists and Turnovers. Each row shows the away value, the label and the home value, above two 3px bars that grow out from the center. The leading side is in accent and ink; the other side in bar-neutral and muted. For turnovers, lower is better.
  - **Final games without stats:** in place of top performers and team stats, one muted line in body-small reading "Stats will be available soon." while they are pending, or "Stats aren't available for this game." once they will not come. The line score and the highlights stay.
  - **Final games, highlights:** the kicker "HIGHLIGHTS" with the video platform's name on the right, and a grid of video cards, min 320px per column and at most two per row; a lone video keeps the width of one column.
    - Each card: a 16:9 thumbnail with a 56px solid-accent play square. Clicking it replaces the thumbnail in place with the embedded player, autoplaying. Below the thumbnail, the title in Barlow Condensed 18px and the channel in muted.
    - **No videos yet:** a single blueprint row reading "Highlights aren't in yet. They'll appear here automatically.", with a ghost link to search for the highlights.
  - **Live games** also show "Highlights will appear here after the final buzzer."
  - **Scheduled games:** three info cells (Tip-off, Venue, Broadcast), then "Players to watch", with each team's star as a photo frame and name.

### Before the first feed loads

Until the first feed loads, the hero and the schedule show skeletons shaped like their content: blocks in `surface`, square corners, with no text. The hero keeps its nav row and shows its two columns, in order: a tag block and a kicker block, two h1 lines (the second shorter), a blurb line, two button blocks, two indicator blocks, and, in the right column, a blueprint image frame at 4:5, max-width 500px. The schedule shows a 7-cell day strip (each cell with weekday, number and count blocks) and three blueprint game cards, each holding one block the height of a monogram (46px). The skeletons shimmer (see Motion). When the feed loads, the content replaces them. If the first load fails, the hero shows no game and the schedule shows the "Data isn't available right now. Check back later." row.

### 3. Footer

"COURTSIDE" on the left. "Personal project. Not affiliated with the NBA." on the right, 12px, muted.

## Interactions and motion

| What | How |
|---|---|
| Hero entrance | Each block fades in from opacity 0 and translateY(28px). Delays: tag .1s, h1 .2s, blurb .32s, buttons .44s, indicator .6s, each lasting .9 to 1s. The image frame comes in from translateY(60px) scale(.94) over 1.4s, starting at .25s |
| Hero slide change | Every 7s, and it can be turned off. The cutouts cross-fade over 1s; the incoming one rises from translateY(36px) scale(.95). The watermark cross-fades over 1.1s |
| Idle float | The image frame bobs translateY 0 to -16px and back over 6s, ease-in-out, looping. The floor shadow scales X from 1 to .82 and opacity from 1 to .6 in sync |
| Mouse parallax | With the pointer position x and y in [-1, 1] over the hero, the frame tilts `rotateY(x·7deg) rotateX(-y·6deg)` (perspective 1200px, .5s) and the watermark moves `translate(-x·30px, -y·18px)` (.6s). Resets on mouse leave. Skipped on touch devices |
| Expand and collapse | Grid rows 0fr to 1fr over .55s. The content fades in over .45s with a .12s delay and rises from -10px. The border turns accent and the open tint fades in over .35s. Stat bars grow from 0 to their value over .9s with a .2s delay. Only one card is open at a time |
| List entrance | When the list first scrolls into view, and on every day change, the cards stagger in: from opacity 0 and translateY(18px), 600ms each, 70ms apart |
| Highlight card | Hover drops opacity to .92. Clicking replaces the thumbnail with the autoplaying player. Closing the card stops playback |
| Spoiler-free mode | Optional setting. Final scores stay hidden and the card shows "Tap to reveal" until it is expanded |
| Skeleton shimmer | Opacity 1 to .5 and back over 1.6s, ease-in-out, looping, while the first feed loads. Off under reduced motion |
| Focus | `:focus-visible` gets a 2px accent outline with a 2px offset. Never the browser default |

## Page state

- The selected day: an index from 0 to 6, default 3 (today).
- The open game: one game or none.
- The playing video: one video of one game, or none.
- The hero game: an index into the games in the rotation, and the hero slide: 0 or 1 (the star on screen), plus the autoplay timer.

## Responsive

- Under 680px: the mobile game row, day counts as numbers only, and the hero stacked with the text above the image.
- Every text container wraps. No fixed heights on text.
- Hit targets are at least 44px.

## Assets

- **Player photos:** transparent PNG cutouts, one per player.
- **Video thumbnails:** provided with each highlight.
- **Fonts:** Barlow and Barlow Condensed from Google Fonts.
- No other images. Team logos are replaced by three-letter monograms on purpose.