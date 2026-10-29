# Design

The visual and interaction specification for the Courtside site. It is the reference for every front end change. Colors, type, spacing, motion and copy are final: build pixel-close to this document.

The game detail page is specified in [`design-game-detail.md`](design-game-detail.md).

## Overview

A dark-mode, single-page site with two parts:

1. **Hero.** A rotating hero that goes through the games of the day, leaving out postponed and canceled games. Each game shows the star player of each team as a transparent cutout, 5 seconds each, then the next game starts. Without an arena, the kicker shows the tip time alone and the blurb is left out.
2. **Schedule.** A 7-day strip with today in the middle and the list of games for the selected day. Clicking a game expands its details: line score, top performers, team stats and, once the game is final, official highlights embedded inline.

## Implementation rules

- **Tokens live in one place.** Every color, font, size, spacing value, shadow and easing in this document is a design token, defined once as a CSS custom property in a single tokens file. Components use tokens and never repeat raw values.
- **Scoped styles.** Each component styles itself with its own scoped styles, built from tokens. No global styles beyond the tokens and the base page styles.
- **Components receive data through props**, with their own types. No component reads a feed directly. A separate layer turns feed data into props.
- **Reusable primitives first.** Shared pieces, such as the blueprint frame, are built once and reused everywhere they appear.
- **Every user-facing string is translatable**, in English and Spanish. The copy in this document is the English text.
- **Reduced motion.** When the system asks for reduced motion, entrance animations, the idle float, the parallax, the skeleton shimmer and the live win probability marker pulse are disabled, and transitions become instant or simple fades.
- **Feed requests time out.** Every feed request that has no answer within 15 seconds counts as a failed request: the page keeps the last feed it showed and tries again at its next poll.

### Components

| Component | What it is |
|---|---|
| `BlueprintFrame` | The framed box with corner registration marks, used across the site |
| `Kicker` | The one small label: 11px, .16em, uppercase. Tones: `accent` (accent-light, the default), `muted`, and `inherit` (the surrounding color, for a label in a control or a state-colored cell). It renders as a span, or as a `dt`, an `h3` or a table's `thead` where one is needed; with `contents` it is a span or a div that draws no box and wraps an element that keeps its own layout. A wrapped element that sets its own font size must also set `letter-spacing: var(--label-letter-spacing)`, because otherwise it inherits the spacing computed at 11px. Tags and info cells keep their own label until their shared components exist |
| `PageContainer` | The one page container: the centered content width and the side padding of every page body and home section |
| `Hero` | The top section, rotating through the games of the day |
| `HeroPlayerCard` | The hero player card: the player's cutout over the logo, tricode and glow layers, with the player strip, specified in `docs/design-team-identity.md`, "Right column: player card" |
| `DayStrip` | The 7-day selector |
| `ScheduleSkeleton` | The schedule's placeholder while the first feed loads: the day strip and game cards |
| `SkeletonBone` | The one loading skeleton bone: a block in `surface` with square corners; each skeleton gives it its width, height or aspect ratio |
| `GameCard` | One game, with its desktop and mobile rows and its expanded panel |
| `LineScore` | Points per quarter |
| `Leaders` | Top performer per team |
| `TeamStats` | Team stat comparison with bars |
| `Highlights` | The video cards of a final game |
| `MessageRow` | A single blueprint row holding one muted message |
| `NoGamesHero` | The hero copy on a day with no games: scenario tag, date, title, paragraph and next tip-off |
| `ComingUp` | The dated events of the Coming up window, as a card on desktop and a section on mobile |
| `HomeLastGames` | The final games of the most recent game day on the home with no games: desktop rows and mobile cards |
| `HomeStandings` | The home's compact standings: East / West, the top 6 and the play-in footnote; in the Finals preview each finalist's path |
| `HomeLeaders` | The home's per-game leaders, one row per category the feed sends (one to four), with photo, category and team, name and value |
| `ScheduleEmptyDay` | The home's box for a selected day with no games: the next game day or the two-weeks message, and the Go to button |
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
- **Small labels and kickers:** 11px, `letter-spacing: .16em`, uppercase, always drawn by `Kicker`.
- Scores and stats use `font-variant-numeric: tabular-nums`.

| Element | Size | Notes |
|---|---|---|
| Hero h1 | `clamp(54px, 8.5vw, 132px)` | line-height .86, letter-spacing -.02em, uppercase. The second line starts with "at" in muted at .42em |
| Hero watermark | `clamp(180px, 26vw, 420px)` | Transparent fill, a 1px stroke in the side's accent at 28% alpha (see `docs/design-team-identity.md`, "Background word") |
| Section h2 | `clamp(40px, 5vw, 64px)` | line-height .95 |
| Team name, desktop row | `clamp(18px, 2.2vw, 26px)` | Uppercase |
| Team name, mobile row | 20px | |
| Score, desktop | `clamp(32px, 4vw, 46px)` | |
| Score, mobile | 30px | |
| Scheduled tip time | `clamp(28px, 3.4vw, 38px)` | The day period ("PM") at .45em, muted; absent in a 24-hour language |
| Player name, panel | 19px | |
| Body and blurbs | 17px in the hero, 13 to 14px elsewhere | |

### Shape and elevation

- **Square corners everywhere** (radius 0).
- **Blueprint frame:** a 1px divider border plus four "+" registration marks, 11 by 11px, made of 1px lines in `color-mix(in srgb, ink 55%, transparent)`, centered on each corner (offset -6px). Used on game cards, the hero image frame, highlight cards and the primary button.
- **Hero frame shadow:** `0 50px 100px -24px rgba(0,0,0,.9)`.
- **Floor shadow** under the hero frame: an ellipse, `radial-gradient(rgba(0,0,0,.9), transparent 70%)`, blur 10px, 56px below the frame.
- **Skeleton widths:** tag and indicator 72px, kicker and buttons 160px, short lines 40% and long lines 80% of the column.
- **Accent glow** behind the hero frame: the outer glow in the active side's accent, extending 18% past the frame on every side, and the inner glow of each slide; both are specified in `docs/design-team-identity.md`, "Right column: player card".

### Spacing

- Max content width: 1320px. `PageContainer` sets it, with the side padding, for every page body and home section.
- Side padding: `clamp(20px, 4vw, 48px)`.
- Game list gap: 14px. Day strip gap: `clamp(4px, 1vw, 8px)`. Expanded panel section gap: 36px.
- Header first line on mobile: `--header-first-line-offset-mobile` (0px). Under 680px every page header puts its first line (tag row, title row or status line, and its loading skeleton) this far below the nav row. It is the home hero's distance from the nav row to its status tag, measured at 390px. Rows below the first line keep their spacing. The home hero sets it by having no gap; the other headers apply the token.

### Motion

- Default easing: `cubic-bezier(.2,.7,.1,1)`, unless a section says otherwise.
- **Skeleton shimmer:** opacity from 1 to .5 and back over 1.6s, ease-in-out, looping. None under reduced motion.
- **Live marker pulse:** the win probability marker's opacity goes from 1 to .5 and back over 2s, ease-in-out, looping, while the game is live. None under reduced motion. See `docs/design-game-detail.md`, section 6.

### Icons

Lucide at `stroke-width: 1.5`: `chevron-down` (expand), `play` (filled, highlight play button), `external-link`.

## Screens

### 1. Hero

- **Nav row (every page):** the brand mark, the logo mark (`/logo-mark.svg`) at 22px (`--brand-mark-size`), decorative (empty alt, hidden from assistive technology) and "COURTSIDE" in Barlow Condensed at `--brand-size` (16px) with `--brand-letter-spacing` (.12em). Links at `--nav-link-size` (14px) and `--nav-link-letter-spacing` (.08em), uppercase; current: ink with a 1px accent underline; others muted, ink on hover. The row fits at 1024px without wrapping.
  - **Desktop (680px and wider):** brand, then "Games · Standings · Tournaments ▾" (a 12px chevron), then, on Home only, the date button and Spoiler-free, then the search field. "All games" replaces "Games" off Home.
  - **Tournaments dropdown:** a button with `aria-expanded` that opens a list under it in `surface` with a 1px divider border: Cup, All-Star, Playoffs, each a link with a 44px minimum height. It closes on Esc (focus back on the button), on a click outside and on selecting an item. On the Cup, All-Star and Playoffs pages the Tournaments button carries the current underline and the matching item `aria-current="page"`. The seasonal entries resolve their own routes in `NavRow` (ADR 0030).
  - **Mobile (below 680px):** one row: brand, the 40px search icon, a 44px menu button ("Open menu"). The menu opens a bottom sheet on the sheet pattern of the Cup and playoffs sheets (slide up over `--nav-sheet-duration` with the default easing, max height `--nav-sheet-max-height`, `--nav-sheet-scrim` scrim, body scroll locked, focus kept inside, focus on Close when it opens). Title "Menu", a Close button, then 48px rows (`--nav-sheet-row`) with a divider rule: Games (or All games), Standings, Cup, All-Star, Playoffs and, on Home only, the date and Spoiler-free. The current page row carries `aria-current="page"` and the accent underline. A link closes the sheet; Esc, the scrim and Close close it and return focus to the menu button; the date row closes the sheet and opens the calendar sheet; Spoiler-free toggles in place and keeps the sheet open, its pressed state in accent text. Nothing overlaps or wraps at 390px.
  - Strings: `nav_tournaments` Tournaments / Torneos, `nav_menu_open` Open menu / Abrir menú, `nav_menu_title` Menu / Menú, `nav_menu_close` Close / Cerrar.
- **Layout:** a two-column grid, `repeat(auto-fit, minmax(min(100%, 440px), 1fr))`, that stacks on mobile. Gap `clamp(40px, 6vw, 96px)`, min-height `min(780px, 84vh)`.
- **Background:** an 88px square grid of faint lines. A huge outlined watermark of the current star's short name sits behind the content on the right.
- **Left column, top to bottom:**
  1. A status tag, "Tonight", "Live now", "Final", "Delayed", "Postponed" or "Canceled", 11px in a 1px divider box. Next to it the kicker with the tip time and arena, such as "10:30 PM · Chase Center". For a delayed game the kicker reads "Scheduled" and the original tip time and arena, such as "Scheduled 7:30 PM · Chase Center". Times are in the viewer's time zone (ADR 0082).
  2. The h1: the away logo and name, a line break, then "at", the home logo and name, specified in `docs/design-team-identity.md`, "Home hero", "Left column", item 2. The logos are silent for assistive technology.
  3. A blurb: "{Away star} and {Home star} meet at {Arena}."
  4. Buttons. **Match details** is the primary button (solid accent, dark text, blueprint marks): it selects today, expands the game on screen and smooth-scrolls to it. **All games** is a secondary outlined button linking to the schedule.
  5. Two slide selectors (a 2px track filled in the side's accent over 5s on the active one, the team's `TeamMark` and the team name), specified in `docs/design-team-identity.md`, "Home hero", "Left column", item 4. Clicking an item jumps to that star. Next to the items, the current game's position among the games in the rotation, such as "03 / 10".

  The status tag, kicker, h1 and blurb always follow the game on screen.

  **Rotation.** The hero goes through the games of the day in feed order, leaving out postponed and canceled games, which stay in the schedule list. Delayed games stay in the rotation. Each game shows its two stars, 5 seconds each, then the next game starts. After the last game it returns to the first. With one game, the hero behaves as a single game: its two stars alternate and the position is not shown. With no games, or when every game of the day is postponed or canceled, the hero shows no game.
- **Right column:** the image frame, max-width 500px, aspect ratio 4:5. A blueprint frame filled with frame-fill and a 44px grid; the glows are specified in `docs/design-team-identity.md`, "Right column: player card".
  - The star's cutout is a transparent player photo in full color, anchored to the bottom center at **172% of the frame width**, so the head pops out above the frame's top edge. The bottom is clipped with `clip-path: inset(-30% 0 0 0)`.
  - Image filter: `drop-shadow(0 0 1px rgba(148,188,227,.35)) drop-shadow(0 30px 30px rgba(0,0,0,.7)) contrast(1.05)`.
  - The bottom scrim and the layers behind the cutout (the glows, the team logo, the tricode) are specified in `docs/design-team-identity.md`, "Right column: player card".
  - **Player strip:** the hero has no player chip; the strip with the team mark, the player and the team is specified in `docs/design-team-identity.md`, "Home hero", "Right column: player card".

### 2. Schedule

- **Header:** the kicker "SCHEDULE" in accent-light, with the selected day as the h2 ("Sunday, October 4"). On the right, the game count ("5 games") in ink, and below it a freshness label in muted: "Recently updated" when the feed is under a minute old, "Updated 3m ago" from 1 minute on, and "Updated 2h ago" from 60 minutes on, in whole hours rounded down. From 680px the game count and the freshness label sit on the right, right-aligned. Under 680px, when the header wraps they sit under the day, left-aligned; when it does not wrap they stay on the right, right-aligned.
- **Day strip:** 7 equal columns, from today minus 3 days to today plus 3 days. Today is the feed's middle day: the US Eastern date, which the backend changes at midnight once no game of the previous day is live. Each cell shows the weekday (or "Today" in accent-light), the date number in Barlow Condensed `clamp(22px, 3vw, 32px)`, and the game count ("5 games" on desktop, "5" on mobile). The selected cell has an accent border and the selected-day fill. Hover: accent border.
- **Day with no games:** the header still shows the selected day and "0 games". In place of the game list, a single blueprint row reads "No games scheduled for this day." in muted.
- **Data unavailable (temporary):** when the games feed cannot be loaded, a single blueprint row in place of the schedule, styled like the day with no games, reads "Data isn't available right now. Check back later.". It stays until the missing data design is decided (see "Open decisions" in `docs/architecture.md`). A day with no data in a loaded feed is still undecided.
- **Game card,** a blueprint frame:
  - **Desktop row, width 680px and up:** grid `minmax(0,1fr) auto minmax(0,1fr) 24px`.
    - Away team: a 46px box with the team logo, or the monogram with the team's code when it has none (a guest without a code shows the initials of its display name, the first and last word's initial, uppercased), the team name and the city in muted.
    - Center: a status line, then the score or the tip time. The status line is "FINAL", or the live badge plus the period and clock ("Q3 · 4:12"), or "DELAYED", "POSTPONED" or "CANCELED" for those games, with no score and no tip time (those cards do not expand), or the TV network. The TV network is omitted when it is unknown.
    - Home team: mirrored and right-aligned.
    - A chevron that rotates 180 degrees when the card is open.
  - **Mobile row, under 680px:**
    - A status line with the chevron on the right.
    - Two team rows, each with a 38px box (same content), the name and city, and the score right-aligned.
    - Scheduled games show the tip time and network in the status line, such as "9:00 PM · Courtside TV".
  - **Final games:** the losing team's name and score drop to opacity .42.
  - **Live badge:** small and outlined, never a dot. It reads "LIVE" at 9.5px with .16em letter-spacing, a 1px accent border and accent-light text, padding 1px by 5px.
- **Expanded panel:** a 1px divider, then the content below it.
  - **Live and final games** get a three-column auto-fit grid, min 280px per column:
    - **Line score:** a grid `1fr repeat(4, 34px) 46px`. The header row reads "Team 1 2 3 4 T". Each team's code has its 20px inline logo before it. Quarters in muted, the total in Barlow Condensed 17px. Unplayed quarters show "–". Overtime periods add columns.
    - **Top performers:** one per team. Each has a 72 by 56px frame holding the full-color player photo (bottom-anchored, 120% width, `drop-shadow(0 6px 8px rgba(0,0,0,.6))`), the team code with its 20px inline logo before it, the name, and the line "34 PTS · 3 REB · 8 AST".
    - **Team stats:** FG%, 3P%, Rebounds, Assists and Turnovers. Each row shows the away value, the label and the home value, above two 3px bars that grow out from the center. The leading side is in accent and ink; the other side in bar-neutral and muted. For turnovers, lower is better.
  - **Final games without stats:** in place of top performers and team stats, one muted line in body-small reading "Stats will be available soon." while they are pending, or "Stats aren't available for this game." once they will not come. The line score and the highlights stay. A final game on a past day whose stats are available but which has no leaders shows no line at all, only the link to the game center (ADR 0054).
  - **Final games, highlights:** the kicker "HIGHLIGHTS" with the video platform's name on the right, and a grid of video cards, min 320px per column and at most two per row; a lone video keeps the width of one column.
    - Each card: a 16:9 thumbnail with a 56px solid-accent play square. Clicking it replaces the thumbnail in place with the embedded player, autoplaying. Below the thumbnail, the title in Barlow Condensed 18px and the channel in muted.
    - **No videos yet:** a single blueprint row reading "Highlights aren't in yet. They'll appear here automatically.", with a ghost link to search for the highlights.
  - **Live games** also show "Highlights will appear here after the final buzzer."
  - **Scheduled games:** three info cells (Tip-off, Venue, Broadcast), then "Players to watch", with each team's star as a photo frame, the team's 20px inline logo and the name. The Venue cell is omitted when it is unknown, as the broadcast is.

### Before the first feed loads

Until the first feed loads, the hero and the schedule show skeletons shaped like their content: `SkeletonBone` blocks in `surface`, square corners, with no text. Every skeleton on the site draws its blocks with `SkeletonBone`. The hero keeps its nav row and shows its two columns, in order: a tag block and a kicker block, two h1 lines (the second shorter), a blurb line, two button blocks, two indicator blocks, and, in the right column, a blueprint image frame at 4:5, max-width 500px. The schedule shows a 7-cell day strip (each cell with weekday, number and count blocks) and three blueprint game cards, each holding one block the height of a monogram (46px). The skeletons shimmer (see Motion). When the feed loads, the content replaces them. If the first load fails, the hero shows no game and the schedule shows the "Data isn't available right now. Check back later." row.

### 3. Footer

"COURTSIDE" on the left. "Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners." on the right, 12px, muted.

## Home with no games

The home shows this layout when the games feed is in and today (US Eastern) has no game in it. A day with games keeps the home described above exactly as it is. If the home feed (ADR 0074, `docs/api/home.md`) fails, the hero still shows "No games today" and the sections that need the feed are hidden; the page never breaks. `/web` computes nothing: every text, date label, status and color comes ready in the feeds, except that a feed instant (a tip-off time, or the "Next tip-off" day) is formatted in the viewer's time zone (ADR 0082). Every new string is in `web/messages/en.json` and `es.json` with the same keys, and styles use the tokens in `web/src/lib/styles/tokens.css`.

**Order:** nav, hero, Coming up, Last games, our schedule, Standings and Leaders, footer. Desktop puts Coming up on the right of the hero and Standings and Leaders in two columns; mobile stacks every section.

### Scenarios

The backend decides one scenario from the schedule dates; the front end only draws it.

| Scenario | When | Tag chip |
|---|---|---|
| `offDay` | An ordinary day with no games | Off day |
| `allStarBreak` | Between the last regular-season game day before the All-Star date and the first after it | All-Star break |
| `finalsPreview` | The conference finals are complete and Finals Game 1 has not started | Finals preview |
| `offseason` | Between the end of the postseason and the start of the regular season | Offseason |

The paragraph of each scenario:

| Scenario | Paragraph |
|---|---|
| `offDay` | A rest day across the league. The schedule below shows the next games. |
| `allStarBreak` | The regular season pauses for the All-Star break. |
| `finalsPreview` | The conference finals are over. The Finals are next. |
| `offseason` | The season is over. The next one starts with the preseason and Opening Night. |

### Hero

Same grid background as the current hero. The tag chip with the scenario, the date, the title "No games today" (124px on desktop, 56px on mobile, `text-wrap: balance`), a paragraph for the scenario, and the next tip-off label from `nextGame` (hidden when it is null). The TV network comes from `nextGame.broadcast` and is shown next to the tip-off label only when it is not null. With no Coming up the hero takes the full width. Our nav (`NavRow`) stays as is.

The title uses `--home-no-games-title-size` (124px) and `--home-no-games-title-size-mobile` (56px), the hero h1 line height and letter spacing, uppercase. The tag row holds the scenario chip and the date of the games feed's today ("Sunday, October 4"). The next tip-off label reads "Next tip-off: {day} · {time}", with " · {network}" added only when `broadcast` is not null. The blocks enter with the hero's entrance delays. While the home feed loads, or when it fails or is not configured, the hero shows the date and "No games today" only: no chip, paragraph, next tip-off or Coming up. The home feed is loaded once, the first time today has no games, and is never polled. A day whose games are all postponed, canceled or guest games still has games and keeps the current home.

### Coming up

The next big event starting in 14 days or less, or an event in progress; null outside the window, and then the section is hidden. In the offseason it is always present, with the preseason start and Opening Night. Events: Opening Night, the Cup stages, All-Star, Play-In, Playoffs and the Finals (Finals Game 1, only when the bracket has it). An event with no date is left out, never invented. Each item shows its date, a title, a sub line and a status chip `Done`, `Now` or `Upcoming` computed by the backend, with a link to the related page (Cup, All-Star or Playoffs). Desktop: a blueprint card with corner marks on the right of the hero. Mobile: its own section below the hero.

Item layout: the date ("Nov 4", or "Nov 4 – Dec 3" for a range), the title, the sub line, the status chip (`Done`, `Now`, `Upcoming`; `Now` takes the accent border) and a call to action by key: "Cup →" for the three Cup stages, "All-Star →", and "Playoffs →" for Play-In, Playoffs and Finals; Opening Night and the preseason have none. The call to action is a text link with a 44px hit target. On desktop the card is in the hero's right column and wraps under the copy when two columns do not fit; on mobile the section sits between the hero and the schedule. The component resolves the three routes itself (ADR 0076).

| Key | Title | Sub line |
|---|---|---|
| `openingNight` | Opening Night | The regular season begins |
| `preseason` | Preseason | Exhibition games begin |
| `cupGroupStage` | Cup group play | In-season tournament · Group stage |
| `cupKnockout` | Cup knockout rounds | In-season tournament · Quarterfinals and semifinals |
| `cupFinal` | Cup championship | In-season tournament · Title game |
| `allStar` | All-Star | The midseason showcase |
| `playIn` | Play-In | Seeds 7 to 10 play for the last playoff spots |
| `playoffs` | Playoffs | The first round begins |
| `finals` | Finals | Game 1 |

### Last games

The most recent day with games before today. The title comes from a key: "Last night" (yesterday), "N days ago", "Before the break" (All-Star break), "Conference finals" (Finals preview) or "Last games played" (offseason). The game count is on the right. Desktop rows: label (Final or the playoff round and game), away side, score, home side mirrored. Mobile: cards. The losing side drops to 45% opacity (token). Each game links to its game page.

Built as `HomeLastGames`: the header is the kicker "Last games", the title as the h2 and the count "N games" on the right. The five titles read "Last night", "{N} days ago", "Before the break", "Conference finals" and "Last games played". The labels read "Final", "Final/OT", "Play-In", "First round", "Conference semifinals", "Conference finals" and "Finals", with " · Game {n}" added when the feed has a game number. Desktop row columns: the label (`--home-last-games-label-column`, 200px), the away side, the score and the home side mirrored. The mobile card holds the label and two team rows with the score right-aligned. Each side has an accent bar (`--home-last-games-accent-width`, 3px) in the feed's resolved color, or the neutral accent when it is null. The loser drops to `--home-last-games-loser-opacity` (.45). The whole row or card links to `/game/{id}`. With spoiler-free on, the scores and the dimming are hidden and "Tap to reveal" shows in their place. The section is hidden when `lastGames` is null or the home feed is loading, failed or not configured. It sits after Coming up (mobile) and before the schedule.

### Schedule

Our 7-day strip and list stay below (`Schedule.svelte`, `DayStrip.svelte`: 3 days back, today, 3 ahead). On the home only, a selected day with no games shows the empty-day box in place of "No games scheduled for this day.": the title, "Next games: {day} · N games", or "No games scheduled in the next two weeks." when `nextGame` is null. The button "Go to {day}" shows only when the next game day is inside the games feed window, and selects that day with `/?day=` as the calendar sheet does. Outside the window there is no button: no page exists for a future day (`/day/` is for past days only, `docs/design-past-dates.md`). `DayPage.svelte` keeps its message. In the offseason the schedule is hidden (seven empty days say nothing); Last games is shown and carries the `schedule` anchor, so the nav's Games link (`/#schedule`) and the calendar's `/?day=` links land on it.

Built as `ScheduleEmptyDay`: the title "No games on this day", the text "Next games: {day} · {N games}" with the day as "Tue, Oct 6", or "No games scheduled in the next two weeks.", and the secondary button "Go to {day} →". The box shows on any selected day with no games while the home feed is in. Without the home feed (loading, failed, not configured, or a day with games today) the row keeps "No games scheduled for this day.". The schedule is hidden once the home feed says `offseason`; while that feed loads the seven empty days show first.

### Standings (compact)

From the existing standings feed, no new feed. An East / West segmented control, the top 6 rows (rank, team with logo, W–L, GB), the play-in teams 7 to 10 as a footnote, and "Full standings →" to `/standings`. In the Finals preview the tabs become the two finalists and the table shows each one's path from `finalsPath`: for each finalist its three series (round, opponent with logo and resolved color, result as wins–losses, won).

Built as `HomeStandings`. The standings feed is loaded once, the first time today has no games, and is never polled: a day with no games does not move the table. The header is the h2 "Standings" with "Full standings →" on the right. The segmented control is the standings page's toggle (East / West). Columns: `#` (the seed, "—" when none), Team (logo and name), W–L and GB ("—" for the leader). The rows are 1 to 6 of the feed's seed order, and the footnote "Play-In · 7 XXX · 8 XXX · 9 XXX · 10 XXX" comes from rows 7 to 10, absent when the conference has no such rows. In the Finals preview the h2 is "Road to the Finals", there is no full standings link and the tabs are the two finalists (logo and name, East first). Columns: Round, Opponent (accent bar `--home-standings-accent-width`, 3px, in the opponent's resolved color, the neutral accent when null, with logo and name), Series (`4–2`) and Won / Lost. The section is hidden when the standings feed is loading, failed or not configured, and in the Finals preview when `finalsPath` is null (the regular-season table is not a stand-in). While the home feed loads in the Finals preview the compact standings may show first, then switch to the finalists. Spoiler-free does not apply: records and series results show as on `/standings`.

### Leaders

From the home feed: one row per category the feed sends, one to four, in the order points, rebounds, assists, blocks per game. A category with no leader is left out by the backend, never shown empty. Each row has a photo thumbnail anchored bottom-left so the head is never cut, the category and team, the name and the value. The title comes from a key: the season, the playoffs (Finals preview) or the previous season with its label (offseason). The section is hidden when `leaders` is null; a player with no photo shows our empty photo box. Percentage categories are excluded: early in the season there is no qualifying minimum.

Built as `HomeLeaders`: the header is the kicker "Leaders" and the title as the h2 ("This season", "Playoffs" or "{season} season"). The categories read "Points per game", "Rebounds per game", "Assists per game" and "Blocks per game". The row is `--home-leaders-row-height` (72px) high: the photo at `--team-leader-photo-width` through `PlayerAvatar` size `leader`, the meta line (category · team code), the name and the value. Rows stack in one column with no placeholder rows. The section is hidden when `leaders` is null or the home feed is loading, failed or not configured.

On the page, desktop puts the two sections side by side after the schedule; one present section takes the full width; mobile stacks Standings then Leaders.

### Deviations from the design handoff

The handoff ("Home — No games today") is a reference, not a spec. Where it differs from Courtside, Courtside wins.

| Handoff item | Decision | Reason |
|---|---|---|
| Nav | Ours (`NavRow`) | One nav for every page |
| Footer | Ours (`SiteFooter`) | One footer for every page |
| Logos and photos | From our feeds (team identity, player photos) | The handoff uses its own image URLs; we never hotlink them |
| 7-days-ahead strip | Not built; we keep our 7-day strip and list. Only the empty-day box is taken | One schedule component; avoids two |
| All-Star weekend events (Rising Stars, Skills, 3-Point, Dunk) | Removed | No verified data |
| Offseason events (Draft, free agency, Summer League, training camps) | Removed | No verified data |
| Countdown | Removed | No verified data to drive it |
| "Game of the night" | Removed | No verified data |
| Power ranking on the home | Moved to `/standings`, regular season only | See `docs/design-standings-search.md`, "Power ranking" |
| Percentage leader categories | Excluded | No qualifying minimum early in the season |
| TV network | Shown only when `nextGame.broadcast` is not null | An unknown network is omitted, as in the schedule |

## Interactions and motion

| What | How |
|---|---|
| Hero entrance | Each block fades in from opacity 0 and translateY(28px). Delays: tag .1s, h1 .2s, blurb .32s, buttons .44s, indicator .6s, each lasting .9 to 1s. The image frame comes in from translateY(60px) scale(.94) over 1.4s, starting at .25s |
| Hero slide change | Every 5s, and it can be turned off. The cutouts cross-fade over 1s; the incoming one rises from translateY(24px) scale(.97). The watermark cross-fades over 1.1s |
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

## Document titles

- Every page, except the development-only `/preview` page, which sets none, sets its title through `<svelte:head><title>`, in English and Spanish, ending with " · " and the site name. The home is exactly "Courtside".
- Standings, NBA Cup, Playoffs and All-Star: the section name, for example "Standings · Courtside".
- The full series page and the previous All-Star: their page's h1.
- Team: the team name ("Thunder · Courtside"). Player: the full name.
- Game: "{Away} at {Home} · Courtside", never the score, in any state (spoiler-free).
- Past day: "Games · {date} · Courtside", the date as the page's long date in the active language.
- Every value comes from the page's feed. While the feed is loading, unavailable or not found, the title is the section name, or "Courtside" on the team, player and game pages.
- The separator and the site name are joined in `pageTitle` (`web/src/lib/format/title.ts`).

## Responsive

- Under 680px: the mobile game row, day counts as numbers only, and the hero stacked with the text above the image.
- Under 680px the first line of every page header sits `--header-first-line-offset-mobile` below the nav row, as on the home.
- Under 680px the schedule header's game count and freshness label are left-aligned when the header wraps.
- Every text container wraps. No fixed heights on text.
- Hit targets are at least 44px.

## Assets

- **Player photos:** transparent PNG cutouts, one per player.
- **Video thumbnails:** provided with each highlight.
- **Fonts:** Barlow and Barlow Condensed from Google Fonts.
- **Logo mark and site icons:** the files in `web/static/` (`logo-mark.svg` drawn in the nav row, the favicons, the touch and app icons and `site.webmanifest`), shipped as they are.
- No other images. Team logos come from the feeds and are drawn by `TeamMark`, per `docs/design-team-identity.md`; a team without one shows its monogram (the team code, or the initials of a guest's name).
