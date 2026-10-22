# Design: All-Star

The visual, interaction and data specification of the All-Star page (`/all-star`), the All-Star link in the nav, the hero per state, the Last time recap, the MVP, the games and the detail of the selected game, the box score, the teams, and the All-Star marks on the player page, the home game card and the game page header. It extends `docs/design.md`, `docs/design-cup.md` and `docs/design-playoffs.md`: every token, rule and shared component defined there applies here, and only new values are listed under "New tokens". The nav, header, monograms, box score and highlights embed are reused from the Cup and playoffs pages; the marks extend ADR 0030, 0031 and 0035; the All-Star teams follow the guest team rule (ADR 0025, 0026). Nothing in the Cup or playoffs behavior changes.

## Overview

| Page | Route | Feeds |
|---|---|---|
| All-Star | `/all-star` | `/feeds/all-star.json` |

- Current season's edition, plus a recap of the previous edition. The page exists all season long.
- An edition is a list of games on one day. Each game has a round label and N teams (two to four): the format changes every year (two teams, four teams with semifinals, three teams with a round robin). The page is a list of games with a round label, never a fixed bracket.
- All-Star games are regular season games of a special competition type. They appear in no team schedule; the backend finds them by reading the scoreboard days (see Feed contract).
- The page is rendered in the browser from a fallback page, as the other pages are.
- Three states, derived from the feed data and never chosen by `/web`:
  - `before`: the current season's edition has no games yet. Date, venue and format may or may not be known.
  - `live`: a game is in progress, or the day is not finished (some games final, others scheduled).
  - `after`: every game of the edition is final.
- Which state the page is in comes from the feed.
- The previous edition has its own `after` view, opened from the Last time link in the `before` state.

## Implementation rules

Everything under "Implementation rules" in `docs/design.md`, `docs/design-cup.md` and `docs/design-playoffs.md` applies, plus:

- **`/web` computes nothing.** The state, the champion, the runner-up, the placements, the wins and losses per team, the format (as parts; the page words the format line), the Top 5 of each game, the leaders, the team statistics and their bar values and better sides, the MVP's game lines and day totals, the attendance, the broadcast names, the round labels, the "To be determined" slots and every count all come ready from the feed. `/web` formats and lays out.
- **Nothing is hardcoded in `/web`:** no team, venue, broadcast, date, round name or award winner. No data source name, video platform or URL is written in `/web`.
- **Every user-facing string is translatable**, in English and Spanish. Long labels truncate with an ellipsis and never wrap in a table cell.
- **A value that is missing renders `—`. A block that is missing hides its section.**
- **A live game shows its status text, clock and period exactly as the feed sends them**, with the same scoreboard fields and refresh rule as a regular live game. Nothing is built from the format: the format object feeds only the format line.
- **All-Star teams are guest teams** (ADR 0025, 0026): no colors, no team link, the code in an outlined box. No explanatory text about it is written anywhere.
- **Players are league players:** a photo, a link to the player page, and a monogram of their league team linking to the team page. A player the feed cannot place in a league roster has no league monogram and no team link.
- **No headline, no story and no records ticker** from any source is published. The page shows scores, leaders and numbers only. The MVP label is the award's name.
- **Shared components are reused:** nav row, `TeamMonogram`, `StatusTag`, `Kicker`, `BlueprintFrame`, the highlights embed and placeholder, the box score table, `PlayerCard`, the loading skeletons and the footer. A "Game page →" link goes to `/game/{id}` only when the game exists.
- **Counting animation:** the hero stats count up and a timeout forces the final values; under reduced motion the final values show at once.

### New components

| Component | What it is |
|---|---|
| `AllStarHeader` | Tag, meta line, kicker, h1, score, hero stats and buttons per state |
| `AllStarPlate` | The right panel of the hero: MVP (after), live scoreboard (live), outlined year (before) |
| `AllStarLastTime` | The two recap cards of the previous edition and the link to it |
| `AllStarMvp` | The MVP card and the Championship scoreline card |
| `AllStarGames` | The games header, the game cards strip and the selected game detail |
| `AllStarGameCard` | One game card: round tag, status, label, team rows |
| `AllStarSigla` | The outlined code box of an All-Star team |
| `AllStarTop5` | The Top 5 rows of a game |
| `AllStarTeamStats` | The team statistics comparison with split bars |
| `AllStarTeams` | One card per All-Star team with placement, results and roster tiles |
| `AllStarTag` | The stage tag "All-Star" with its round, and the player tag "All-Star {year}" |

## Shared patterns

- Ground, ink, muted, accent, accent text, divider and row rules are the existing tokens. Headings Barlow Condensed 600, body Barlow, numbers `font-variant-numeric: tabular-nums`.
- Content max width `--content-max-width`, side padding `--side-padding`, section gap `clamp(64px, 8vw, 104px)`, `scroll-margin-top: 72px`. Section header: h2 `clamp(28px, 3.4vw, 40px)`, uppercase, optional meta right.
- Tags: accent outline, 11px, .16em, uppercase, accent text (`StatusTag`).
- Corner marks: 14px accent-light ticks at the four corners, as on the blueprint frames.
- An All-Star team is drawn as its code in an outlined box (the sigla). It has no colors and no link. The box is 56px in heroes and team cards, 34x24px in game cards, and `--team-code-box-size` where the standard scoreboard is reused.
- A league player is drawn with a photo (or initials), a link to the player page and, next to the name, a 38px monogram of the player's league team (code and a 3px two-color bar) linking to the team page.
- Photos are a background image over an initials layer, so a missing or slow photo shows the initials. A photo never links by itself; the row or tile that holds it does.
- The winner of a game is shown in ink, the loser muted.
- The 680px break is `--game-row-breakpoint`.

## Nav

- Links: the desktop row reads Games · Standings · Tournaments ▾, with Cup, All-Star and Playoffs inside the dropdown, in that order, then the search trigger. Same rules as the other pages (`docs/design.md`, "Nav row (every page)"). All-Star is active on `/all-star`.
- Mobile: sticky 56px header with blur (`rgba(12, 14, 16, .92)`, `backdrop-filter: blur(12px)`). Below 680px the links live in the menu sheet, as `docs/design.md`, "Nav row (every page)", describes.

## Header

The hero. Ground `--color-bg` with a 56px grid of 1px lines in `--color-grid-line` (`--playoffs-hero-grid-size`), a 1px divider below. Two columns `repeat(auto-fit, minmax(min(100%, 440px), 1fr))`, gap `clamp(32px, 5vw, 72px)`.

### Hero, after

- Left column:
  - An outline tag "All-Star {year}" (Barlow Condensed 600, 14px, .1em, accent border, accent-light text) and a meta line (12px, uppercase, muted): date · venue.
  - Kicker "Champions of the day" (12px, .18em, accent light).
  - H1: the champion's name, `--allstar-hero-title-size`, line-height `--allstar-hero-title-leading` (.82), uppercase.
  - The Championship score, 600, `clamp(34px, 4.4vw, 56px)`, accent light.
  - Hero stats: four cells between dividers, value 600 `clamp(26px, 3.4vw, 44px)`, tabular. Cells: Games · Teams · Championship (accent) · Attendance. The values count up over 1400ms ease-out cubic (`--playoffs-count-duration`); a timeout forces the final values after 1600ms (`--playoffs-count-timeout`). The Championship cell shows the score and does not count.
  - Buttons: primary "Every game" (44px, accent fill, ground text), secondary "All-Star MVP" (1px `rgba(235, 232, 227, .25)` border). "Every game" scrolls to `#games`; "All-Star MVP" scrolls to `#mvp`.
- Right column: the plate, max 520px, aspect `--playoffs-plate-ratio` (26 / 30), 1px divider, 14px accent-light corner marks.
  - The MVP headshot anchored at the bottom center at 92% of the height, over `radial-gradient(ellipse at 50% 100%, rgba(116, 157, 196, .3), transparent 70%)`. Behind it the jersey number as a watermark in `rgba(235, 232, 227, .06)`; the initials as the fallback when there is no photo.
  - Top labels: "All-Star MVP" and "{pts} PTS · {n} games".
  - Bottom: the MVP's name, 600 `clamp(28px, 3.4vw, 40px)`, and a solid "MVP" tag.

### Hero, live

- Left column: as `after`, with the tag "All-Star {year}", the kicker "Live now" and the h1 "All-Star". The score and the champion are not shown.
- Hero stats: Games today · Final · Live now (accent) · Teams. Values come from the feed. Primary button "Follow the games" scrolls to `#games`.
- Right column: the live plate, with a 32px grid:
  - Header: "● Live · {round}" and the format line.
  - Two team rows: the 56px sigla box, the name, the score (600 `clamp(64px, 8vw, 104px)`); the leader in ink, the trailing team muted. A third team in a round robin plays another game and is not shown here.
  - Footer: the clock at 44px, accent light, with the status as the games feed sends it, and "Next: {label}" for the next game when there is one.
- The live game is the one in progress. When no game is in progress but the day is not finished, the plate shows the next game in the scheduled card form: "Tip-off · {time}".

### Hero, before

- Left column: tag "All-Star {year}" when the year is known, the kicker "Next edition", the h1 "All-Star", and three rows: Date, Venue, Format. Each row reads "To be confirmed" unless the feed has the value. Primary button "Last edition" scrolls to the Last time section.
- Right column: the year as an outlined numeral (`-webkit-text-stroke: 1.5px` in accent light, transparent fill) at `--allstar-year-size` over dashed crosshair circles. When the year is unknown the plate shows the dashed circles and "—".
- No hero stats in this state.

## Last time

Before state only, and only when the previous edition is in the feed.

- Two framed cards, `repeat(auto-fit, minmax(min(100%, 420px), 1fr))`:
  - The champion card: kicker "Champions of the day", the champion's name 600 `clamp(44px, 5.6vw, 72px)`, "date · venue", the Championship score at 56px in accent.
  - The MVP card: a photo column (initials fallback), the name, the league team, and "{pts} PTS · across {n} games".
- Link below: "Every game, box score and highlight from {prev} →". It opens that edition's `after` view.
- When the previous edition has no MVP, the MVP card is not drawn and the champion card takes the row.

## MVP

After state only. `#mvp`.

- Left card with corner marks, min-height `--allstar-mvp-min-height` (380px), columns `1fr 1.15fr`:
  - The photo column: the photo or the initials fallback, with the jersey number as a watermark.
  - The info column: kicker "All-Star MVP"; the name `clamp(36px, 4.4vw, 56px)`; the league team link with a 3px color bar; one row per game he played: the round label (accent for the Championship), the result ("W 47–21 vs Team Stripes"), and "PTS · REB · AST" at 22px; the day total at 40px in accent; the link "Player profile →".
- Right card: the Championship scoreline. The winner in ink with its score in accent, the loser muted, scores `clamp(72px, 9vw, 124px)`. The link "Box score and highlights →" selects the Championship in the games section and scrolls to `#games`.
- When the MVP is missing from the feed, the left card is not drawn and the scoreline card takes the row.

## Games

Live and after states. `#games`.

- Header: a kicker, the h2 `clamp(28px, 3.4vw, 40px)`, and the format line on the right (13px, muted).
- Game cards, in one 1px frame, grid `repeat(auto-fit, minmax(min(100%, 230px), 1fr))` with left dividers. A card shows:
  - The round tag: "Championship" solid accent with ground text, the other rounds outlined muted.
  - The status: "Final", "Final · OT", "● Live · {status text and clock as the games feed sends them}", or the tip-off time ("6:20 PM ET").
  - The label.
  - Two team rows: a 34x24 sigla box (accent border on the winner), the name at 18px, the score at 26px; the loser muted.
- Selected card: background `rgba(116, 157, 196, .1)` and a 2px inset accent-light bottom bar. Hover: `rgba(116, 157, 196, .08)`.
- Default selection: the Championship in the `after` state, the live game in the `live` state. If neither exists (live state between games), the first game not final, then the first game.

### Selected game detail

Two columns `repeat(auto-fit, minmax(min(100%, 440px), 1fr))`.

- Left column:
  - A 16:9 highlights embed, or the placeholder (a 32px grid, a 68px outlined play button). In a live or scheduled game the button is muted and the text reads "Highlights post after the final buzzer". With a final game and no stored highlights the placeholder reads "Highlights not available".
  - The venue strip: Venue (name, city) · Attendance · Broadcast (the TV name, then the streaming name when there is one) · Tip-off.
  - The Top 5 of the game: rank at 32px (#1 in accent); a 52px photo with a 3px league-team color bar; the name; "{All-Star team} · {league team}"; the points at 30px with "PTS · x REB · y AST". Each row links to the player. The order and the five rows come from the feed.
- Right column:
  - The scoreboard: names, score `clamp(40px, 5vw, 64px)`, status.
  - Two leader cards: the top scorer of each team, from the feed.
  - Team statistics comparison: FG%, 3PM, Rebounds, Assists, Steals, Blocks. Each stat has the two values and a split 3px bar; the higher side is ink and accent, the lower `rgba(235, 232, 227, .25)`. The better side comes from the feed.
- A scheduled game replaces both columns with one centered card: "Tip-off · {time}" and "Box score, leaders and highlights appear once the game starts."

### Box score

Full width, below the detail, for the selected game.

- Tabs per All-Star team; a 2px accent bar marks the active one. The legend reads "■ Starter" and "Monogram · player's league team".
- Columns `44px minmax(220px, 1fr) 52px repeat(6, 52px) 70px 60px 56px`: # · Player · Pos · Min · Pts · Reb · Ast · Stl · Blk · FG · 3P · +/−. Minimum width 860px with horizontal scroll.
- The player cell: a 36px photo, a 6px accent square if he started, the name as a link, and the 38px league-team monogram (code and a 3px two-color bar) linking to the team page.
- The top PTS value of the team in accent; a negative +/− muted. The totals row on `rgba(116, 157, 196, .06)`.
- The full stat line has more values than the table shows (offensive and defensive rebounds, free throws, turnovers, fouls); the table shows the columns above and the rest are not drawn.

## Teams

Live and after states.

- Grid `repeat(auto-fit, minmax(min(100%, 340px), 1fr))`, one card per All-Star team.
- Card header: the 56px sigla box, the name at 28px, the placement, the record at 32px.
  - Placement: "Champion" (accent), "Runner-up", "Eliminated in the {round}" (the round label comes from the feed), "So far today" (live, games played), "Yet to play".
- Result rows: a 22px W/L square (W solid accent), "{label} · vs {opp}{ · OT}", the score.
- Roster tiles: `repeat(auto-fill, minmax(48px, 1fr))`, square photos with a 3px league-team bar, each linking to the player with the title "Name · league team".
- The champion card has an accent border and a `rgba(116, 157, 196, .06)` fill.
- Placements come from final scores only (see Feed contract): wins and losses per team; the champion is the winner of the Championship game and the runner-up its loser; every other team is "Eliminated in the {round}". Who advances is never inferred before the games exist: an unscheduled or team-less Championship shows "To be determined".

## Tags

Marks on pages that already exist, extending the Cup marks (ADR 0031) and the playoffs marks (ADR 0035). `/web` computes nothing for them: the stage, the round and the year come from the feeds, and a mark whose field is absent is not drawn.

### Stage tag

| Game | Tag | Style |
|---|---|---|
| All-Star game | `All-Star` | accent outline, accent-light text |

Same size, letter spacing and truncation as the other stage tags: 11px, .16em, uppercase, ellipsis, no wrap. The tag is plain text: it does not link and has no hover state. The Championship uses the solid accent style, as in the games section.

### Context line

- Muted caps after the tag: the round. The four known rounds are translated strings (`allstar_round_championship`, `allstar_round_semifinals`, `allstar_round_robin`, `allstar_round_game`), as on the `/all-star` page; any other round is shown as the feed sends it. The format suffix is not shown here.

### Home game card

- The stage tag first in the card's center column, above the status line (first in the status line on the mobile row), then the context line.
- An All-Star team side is drawn as a sigla box with no colors and no link.

### Game page header

- The stage tag as the first item of the kicker line, before the date and the venue; then the context line. Same truncation as on the home card.

### Player tag

- The player page shows the tag "All-Star {year}" (accent outline) in the header when the feed marks the current season with an All-Star game in the player's game log. A player without one shows none and the cells around keep their order. The tag does not link.

## Edge cases

| Case | What shows |
|---|---|
| Before, nothing scheduled | The hero shows the three rows "To be confirmed", the outlined year or the dashed circles with "—", the Last time section when the previous edition exists. No games section, no teams section |
| Before, date and venue but no games | The Date and Venue rows show their values, Format stays "To be confirmed", no games section |
| A day with 2, 3 or 4 teams | The Teams grid has one card per team; the game cards list the games the feed sends; no fixed slot count |
| Championship without teams | The card shows "To be determined" in each team row; the placements of the other teams do not mention the Championship |
| Championship not yet played | No champion, no runner-up; teams show "So far today" or "Yet to play" |
| Live game | The status text, the clock and the period as the games feed sends them; the one-period format changes only the format line |
| Overtime | "Final · OT" in the card status and "OT" after the score in the result row |
| No highlights | The 16:9 placeholder "Highlights not available" for a final game; the rest of the detail shows |
| Player without photo | Initials in the photo tile |
| Player not found in the rosters | No league monogram and no team link; the name still links to the player when a player id exists |
| Missing values | `—` in that cell, bar or stat |
| Missing block | The section is hidden; the section order does not change |
| MVP missing | The MVP section shows only the scoreline card; the hero plate shows the Championship score instead of the photo |
| Unavailable feed | The nav row, then the home's 503 state: "Data isn't available right now. Check back later." |
| Previous edition missing | The Last time section is hidden |
| Spanish strings | Every string has a Spanish text; long labels truncate, never wrap in a table cell |

## States

| State | What shows |
|---|---|
| Loading | Skeletons shaped like the hero and the games strip, with the home's shimmer, stopped under reduced motion |
| Feed unavailable | See Edge cases; polling continues and the page fills in when a request succeeds (the previous edition page is not polled: it stays unavailable until reloaded) |
| Before / live / after | Per the state rules in Overview and Header |

## Interactions and motion

| What | How |
|---|---|
| Polling | Current edition every 30 seconds while the state is `live`, every 60 seconds otherwise; the previous edition page loads its feed once and never polls; paused while the tab is hidden and refreshed when it is visible again |
| Hero stats | Count up over 1.4s ease-out cubic; a 1.6s timeout forces the final values; none under reduced motion |
| Game card click | Selects the game; the detail updates and the box score tab resets to the first team |
| Live clock | Re-rendered every second from the feed clock |
| Live dots | 7px, 1.4s pulse (opacity 1 to .35, scale 1 to .7); static under reduced motion |
| "Every game", "Follow the games", "Box score and highlights →" | Smooth scroll to `#games` with a 24px offset (64px on mobile) |
| "All-Star MVP" and the mobile MVP thumb | Scroll to `#mvp` |
| Box tabs | Switch the team; the active tab has a 2px accent bottom bar |
| Photos | Background image over an initials layer |
| Focus | `:focus-visible` 2px accent outline (`--focus-ring-width`, `--focus-ring-offset`) |

## Responsive

Under 680px (the 390px design):

- Side padding 18px, section gap 56px. The sticky 56px header with blur and the one-row nav with the menu button.
- Hero after: the h1 `clamp(58px, 17vw, 84px)`, a 116x156 MVP thumb with corner marks and a solid "MVP" tag linking to `#mvp`, the score at 44px, the stats 2x2, the buttons 48px in two columns.
- Hero live: the framed live scoreboard (score 56px, clock 22px); tapping it selects the live game and scrolls to `#games`.
- Hero before: the h1, the outlined year `clamp(96px, 30vw, 140px)`, the three "To be confirmed" rows, the button.
- MVP: the photo 250px tall on top, the info below; the Championship card is one tappable block.
- Game cards: a horizontal strip of 224px cards with `scroll-snap-type: x mandatory`; the selected card has a 1px accent-light border.
- The detail stacks: scoreboard, video, venue 2x2, Top 5 (44px photos), team statistics. The two leader cards are dropped on mobile.
- Box score: horizontal scroll, minimum width 660px, a sticky player column (184px, opaque, right divider) with the short name and "#5 · G · MIN". Columns: Pts · Reb · Ast · Min · Stl · Blk · FG · 3P · +/−. The hint "Swipe for more columns" shows above.
- Teams: stacked cards, the roster photos as a horizontal row of 44px tiles.
- Hit targets at least 44px (`--hit-target-size`).

## New tokens

To add to `web/src/lib/styles/tokens.css` in the implementing issue. Values not listed map to existing tokens.

| Token (suggested) | Value | Use |
|---|---|---|
| `--allstar-hero-title-size` | `clamp(72px, 11vw, 176px)` | Hero h1 |
| `--allstar-hero-title-size-mobile` | `clamp(58px, 17vw, 84px)` | Mobile hero h1 |
| `--allstar-hero-title-leading` | .82 | Hero h1 line height |
| `--allstar-score-size` | `clamp(34px, 4.4vw, 56px)` | Championship score in the hero |
| `--allstar-hero-stat-size` | `clamp(26px, 3.4vw, 44px)` | Hero stat value |
| `--allstar-plate-max-width` | 520px | Hero plate |
| `--allstar-plate-photo-height` | 92% | MVP headshot in the plate |
| `--allstar-plate-glow` | `rgba(116, 157, 196, .3)` | Plate radial glow |
| `--allstar-watermark-ink` | `rgba(235, 232, 227, .06)` | Jersey number watermark |
| `--allstar-plate-grid-size` | 32px | Live and placeholder grid |
| `--allstar-sigla-size` | 56px | Sigla box in heroes and team cards |
| `--allstar-sigla-width-small` | 34px | Sigla box in game cards |
| `--allstar-sigla-height-small` | 24px | Sigla box in game cards |
| `--allstar-live-score-size` | `clamp(64px, 8vw, 104px)` | Live plate score |
| `--allstar-live-clock-size` | 44px | Live plate clock |
| `--allstar-year-size` | `clamp(120px, 19vw, 220px)` | Outlined year |
| `--allstar-year-size-mobile` | `clamp(96px, 30vw, 140px)` | Outlined year on mobile |
| `--allstar-year-stroke` | 1.5px | Outlined year stroke |
| `--allstar-button-border` | `rgba(235, 232, 227, .25)` | Secondary button border |
| `--allstar-recap-name-size` | `clamp(44px, 5.6vw, 72px)` | Last time champion name |
| `--allstar-mvp-min-height` | 380px | MVP card |
| `--allstar-mvp-name-size` | `clamp(36px, 4.4vw, 56px)` | MVP name |
| `--allstar-mvp-total-size` | 40px | MVP day total |
| `--allstar-mvp-line-size` | 22px | MVP game line |
| `--allstar-mvp-photo-height-mobile` | 250px | Mobile MVP photo |
| `--allstar-championship-score-size` | `clamp(72px, 9vw, 124px)` | Championship scoreline |
| `--allstar-card-min` | 230px | Game card |
| `--allstar-card-mobile` | 224px | Mobile game card |
| `--allstar-card-selected` | `rgba(116, 157, 196, .1)` | Selected card |
| `--allstar-card-hover` | `rgba(116, 157, 196, .08)` | Card hover |
| `--allstar-card-bar` | 2px | Selected card bottom bar |
| `--allstar-card-score-size` | 26px | Score in a game card |
| `--allstar-card-name-size` | 18px | Name in a game card |
| `--allstar-top5-rank-size` | 32px | Top 5 rank |
| `--allstar-top5-photo-size` | 52px | Top 5 photo |
| `--allstar-top5-photo-size-mobile` | 44px | Mobile Top 5 photo |
| `--allstar-top5-points-size` | 30px | Top 5 points |
| `--allstar-detail-score-size` | `clamp(40px, 5vw, 64px)` | Detail scoreboard |
| `--allstar-stat-bar-height` | 3px | Team statistics split bar |
| `--allstar-stat-bar-lower` | `rgba(235, 232, 227, .25)` | Lower side of a split bar |
| `--allstar-box-columns` | `44px minmax(220px, 1fr) 52px repeat(6, 52px) 70px 60px 56px` | Box score columns |
| `--allstar-box-min-width` | 860px | Box score |
| `--allstar-box-min-width-mobile` | 660px | Mobile box score |
| `--allstar-box-sticky-column` | 184px | Mobile sticky player column |
| `--allstar-box-photo-size` | 36px | Box score photo |
| `--allstar-box-starter-size` | 6px | Starter square |
| `--allstar-box-monogram-size` | 38px | League-team monogram |
| `--allstar-box-total-fill` | `rgba(116, 157, 196, .06)` | Totals row and champion card fill |
| `--allstar-team-name-size` | 28px | Team card name |
| `--allstar-team-record-size` | 32px | Team card record |
| `--allstar-team-card-min` | 340px | Team card |
| `--allstar-roster-tile-min` | 48px | Roster tile |
| `--allstar-roster-tile-mobile` | 44px | Mobile roster tile |
| `--allstar-league-bar` | 3px | League-team bar |
| `--allstar-live-dot-size` | 7px | Live dot |
| `--allstar-live-dot-duration` | 1.4s | Live dot pulse |
| `--allstar-scroll-offset` | 24px | Scroll to `#games` |
| `--allstar-scroll-offset-mobile` | 64px | Scroll to `#games` on mobile |

Mapped to existing tokens: the ground is `--color-bg`; ink, muted and accent are `--color-ink`, `--color-muted`, `--color-accent`; accent text is `--color-accent-light`; the divider is `--color-divider`; the hero grid ink is `--color-grid-line` and its size `--playoffs-hero-grid-size` (56px); the plate aspect is `--playoffs-plate-ratio`; the count-up duration and timeout are `--playoffs-count-duration` and `--playoffs-count-timeout`; the 16:9 embed is `--video-aspect`; the 22px W/L square is `--result-square-size`; the 680px break is `--game-row-breakpoint`; hit targets are `--hit-target-size`; the focus ring is `--focus-ring-width` and `--focus-ring-offset`; label size and spacing are `--label-size` and `--label-letter-spacing`; the content width and side padding are `--content-max-width` and `--side-padding`.

## Strings

| Key (suggested) | English | Spanish |
|---|---|---|
| `nav_all_star` | All-Star | All-Star |
| `allstar_title` | All-Star | All-Star |
| `allstar_tag` | All-Star {year} | All-Star {year} |
| `allstar_stage_tag` | All-Star | All-Star |
| `allstar_unavailable` | Data isn't available right now. Check back later. | Los datos no están disponibles ahora. Vuelve más tarde. |
| `allstar_kicker_champions` | Champions of the day | Campeones del día |
| `allstar_kicker_live` | Live now | En vivo |
| `allstar_kicker_next` | Next edition | Próxima edición |
| `allstar_stat_games` | Games | Partidos |
| `allstar_stat_teams` | Teams | Equipos |
| `allstar_stat_championship` | Championship | Campeonato |
| `allstar_stat_attendance` | Attendance | Asistencia |
| `allstar_stat_games_today` | Games today | Partidos hoy |
| `allstar_stat_final` | Final | Finalizados |
| `allstar_stat_live` | Live now | En vivo |
| `allstar_cta_every_game` | Every game | Todos los partidos |
| `allstar_cta_mvp` | All-Star MVP | MVP del All-Star |
| `allstar_cta_follow` | Follow the games | Sigue los partidos |
| `allstar_cta_last` | Last edition | Última edición |
| `allstar_live_header` | Live · {round} | En vivo · {round} |
| `allstar_next_game` | Next: {label} | Siguiente: {label} |
| `allstar_row_date` | Date | Fecha |
| `allstar_row_venue` | Venue | Sede |
| `allstar_row_format` | Format | Formato |
| `allstar_to_be_confirmed` | To be confirmed | Por confirmar |
| `allstar_to_be_determined` | To be determined | Por determinar |
| `allstar_last_time` | Last time | La vez pasada |
| `allstar_last_link` | Every game, box score and highlight from {prev} → | Todos los partidos, estadísticas y resúmenes de {prev} → |
| `allstar_mvp_label` | All-Star MVP | MVP del All-Star |
| `allstar_mvp_tag` | MVP | MVP |
| `allstar_mvp_summary` | {pts} PTS · across {n} games | {pts} PTS · en {n} partidos |
| `allstar_mvp_hero_labels` | {pts} PTS · {n} games | {pts} PTS · {n} partidos |
| `allstar_mvp_profile` | Player profile → | Perfil del jugador → |
| `allstar_mvp_box_link` | Box score and highlights → | Estadísticas y resumen → |
| `allstar_games_title` | Games | Partidos |
| `allstar_round_championship` | Championship | Campeonato |
| `allstar_round_semifinals` | Semifinals | Semifinales |
| `allstar_round_robin` | Round Robin | Todos contra todos |
| `allstar_round_game` | All-Star Game | Partido de las Estrellas |
| `allstar_format_first_to` | First to {points} | A {points} puntos |
| `allstar_format_untimed` | Untimed | Sin reloj |
| `allstar_format_periods` | {count} period / {count} periods | plural, see `web/messages/es.json` |
| `allstar_format_minutes` | {minutes} min | {minutes} min |
| `position_guard` | Guard | Escolta |
| `position_forward` | Forward | Alero |
| `position_center` | Center | Pívot |
| `position_point_guard` | Point Guard | Base |
| `position_shooting_guard` | Shooting Guard | Escolta |
| `position_small_forward` | Small Forward | Alero |
| `position_power_forward` | Power Forward | Ala-pívot |
| `allstar_status_final` | Final | Final |
| `allstar_status_final_ot` | Final · OT | Final · TE |
| `allstar_status_live` | Live · {status} | En vivo · {status} |
| `allstar_highlights_unavailable` | Highlights not available | Resumen no disponible |
| `allstar_highlights_after_buzzer` | Highlights post after the final buzzer | El resumen se publica tras el final del partido |
| `allstar_venue` | Venue | Sede |
| `allstar_attendance` | Attendance | Asistencia |
| `allstar_broadcast` | Broadcast | Transmisión |
| `allstar_tipoff` | Tip-off | Salto inicial |
| `allstar_top5` | Top 5 | Top 5 |
| `allstar_stat_fg` | FG% | FG% |
| `allstar_stat_3pm` | 3PM | 3PE |
| `allstar_stat_reb` | Rebounds | Rebotes |
| `allstar_stat_ast` | Assists | Asistencias |
| `allstar_stat_stl` | Steals | Robos |
| `allstar_stat_blk` | Blocks | Tapones |
| `allstar_scheduled_title` | Tip-off · {time} | Salto inicial · {time} |
| `allstar_scheduled_body` | Box score, leaders and highlights appear once the game starts. | Las estadísticas, los líderes y el resumen aparecen cuando empieza el partido. |
| `allstar_legend_starter` | ■ Starter | ■ Titular |
| `allstar_legend_monogram` | Monogram · player's league team | Monograma · equipo del jugador en la liga |
| `allstar_box_hint` | Swipe for more columns | Desliza para ver más columnas |
| `allstar_col_pos` | Pos | Pos |
| `allstar_col_min` | Min | Min |
| `allstar_col_pts` | Pts | Pts |
| `allstar_col_reb` | Reb | Reb |
| `allstar_col_ast` | Ast | Asi |
| `allstar_col_stl` | Stl | Rob |
| `allstar_col_blk` | Blk | Tap |
| `allstar_col_fg` | FG | TC |
| `allstar_col_3p` | 3P | 3P |
| `allstar_col_pm` | +/− | +/− |
| `allstar_teams_title` | Teams | Equipos |
| `allstar_placement_champion` | Champion | Campeón |
| `allstar_placement_runner_up` | Runner-up | Subcampeón |
| `allstar_placement_eliminated` | Eliminated in the {round} | Eliminado en {round} |
| `allstar_placement_so_far` | So far today | Hasta ahora hoy |
| `allstar_placement_yet` | Yet to play | Por jugar |
| `allstar_result_row` | {label} · vs {opp} | {label} · vs {opp} |
| `allstar_result_ot` | OT | TE |
| `allstar_player_title` | {name} · {team} | {name} · {team} |

The format comes as parts (`targetPoints`, `untimed`, `periods`, `minutes`) and the page words it ("1 period · 12 min", "First to 40 · Untimed"); the known round labels ("Championship", "Semifinals", "Round Robin", "All-Star Game") and placements' round names are translated and any other is shown as sent; the champion, the status text and the clock come from the feed; the other keys are the fixed words around them. Strings for the Cup marks stay in `docs/design-cup.md` and for the playoffs marks in `docs/design-playoffs.md`.

## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601. Every value is computed by the backend; exact field names are set by `docs/api/all-star.md` in the issue that adds the feed. The feed is built on demand and expires like the games feed while the day is live; a finished edition is built once and kept.

### All-Star feed (`/feeds/all-star.json`)

- State (`before`, `live`, `after`) and the season year.
- The current edition: date, venue name and city, the format parts (built by the backend from the structured format and the note suffix, with no prose; the page words them), the teams, and the games.
  - Per team: code, name, record (wins, losses), the placement (`champion`, `runnerUp`, `eliminated` with the round label, `soFar`, `yetToPlay`) and the roster tiles (player id, name, photo, league team code and colors). All-Star teams carry no colors.
  - Per game: game id when it exists, round, label, status, status text, clock and period as the games feed sends them, scores, overtime flag, winner, tip-off, attendance, broadcasts (TV and streaming names), the two teams, the box scores, the team statistics (FG%, 3PM, rebounds, assists, steals, blocks, each with both values and the better side), the leaders (two per game, one per team), the Top 5 rows (sorted by points, then rebounds plus assists), the highlights when stored (`null` otherwise) and the "To be determined" flag for an unscheduled or team-less game.
  - Per box score player: id, name, jersey, position, starter flag, photo, the stat line (minutes, points, field goals, three pointers, free throws, rebounds, assists, turnovers, steals, blocks, offensive and defensive rebounds, fouls, plus-minus), and the league team (code, colors) resolved by id, or `null` when the player is not found.
- The MVP: the award name ("All-Star MVP"), the player (id, name, photo, jersey, league team), one line per game he played (round label, result text, points, rebounds, assists) and the day totals.
- The previous edition recap: the champion of the day, the Championship score, the MVP, the date and the venue; `null` when there is none.
- Per game, for the home card, the game page and the player page, a nullable `allStar` object with the round, and, on the player feed, a nullable All-Star tag value (the year) for the current season.
