# Design: Playoffs

The visual, interaction and data specification of the playoffs page (`/playoffs`), the Playoffs link in the nav, the 16-team bracket and the play-in, the champion hero, the Finals MVP card, the Finals series, the road to the title, the head to head, the leaders, the awards, and the tournament tags and titles on the home card, the game page header and the team page header. It extends `docs/design.md` and `docs/design-cup.md`: every token, rule and shared component defined there applies here, and only new values are listed under "New tokens". The bracket camera is shared with the Cup (ADR 0034). The player card, games list, header, stage strip and marks are reused (ADR 0030, ADR 0031); nothing in the Cup behavior changes.

## Overview

| Page | Route | Feeds |
|---|---|---|
| Playoffs | `/playoffs` | `/feeds/playoffs.json`, `/feeds/playoffs/finals.json` |

- Current season only. The page exists all season long.
- The postseason has the play-in (four days in the middle of April: six games), four rounds of best-of-seven series (round 1, conference semifinals, conference finals, NBA Finals) and 15 series in all, eight in round 1, four in the conference semifinals, two in the conference finals and one in the Finals.
- The page is rendered in the browser from a fallback page, as the other pages are.
- Five states, in order:
  - `picture`: the regular season (and the preseason). No postseason game is scheduled yet. Seeds 1 to 10 per conference come from the standings feed, with the playoff line and the play-in line.
  - `playin`: the play-in games are scheduled or being played and round 1 has not started.
  - `playoffs`: round 1, the conference semifinals or the conference finals, whichever is the current round.
  - `finals`: the NBA Finals are scheduled or being played.
  - `complete`: the Finals series is complete.
- Which state the page is in, the current round, the stage dates and the stage statuses come from the feed.
- Games are the play-in games and the postseason games. A series is the round plus the pair of teams; its wins, its winner and its completion come from the feed and are never counted by `/web`; the page writes the summary ("QXA wins series 4–3", "Series tied 2–2", "QXA leads series 3–1") from the wins and the winner, in the page language, and shows none when a side's wins are missing. The feed's English summary string is never shown.

## Implementation rules

Everything under "Implementation rules" in `docs/design.md` and `docs/design-cup.md` applies, plus:

- **`/web` computes nothing.** State, current round, stage dates and statuses, seeds, clinch tags, games behind, series wins, series summaries, winners, stakes flags, context lines, the point differential, records, averages, leaders, ranks, the largest deficit, the best scoring game, bar values and which side of a bar is better, the number of games to show and every count all come ready from the feeds. The page writes the fixed words around them. Slot labels are the exception: the feed sends them as keys and parts (conference, round, seed, place), never prose, and the page writes the words.
- **Nothing is hardcoded in `/web`:** no team, venue, broadcast, date, round name list for a given year or award winner. No data source name, video platform or URL is written in `/web`.
- **Every user-facing string is translatable**, in English and Spanish. Long labels truncate with an ellipsis and never wrap in a table cell.
- **A value that is missing renders `—`. A block that is missing hides its section. The bracket always shows its slots.**
- **Pan and zoom of the bracket only write `style.transform`.**
- **Shared components are reused:** nav row, `TeamMonogram`, `StatusTag`, `Kicker`, `BlueprintFrame`, `ClinchTag`, `StandingsTable` patterns, `StageStrip`, the shared bracket camera (ADR 0034), `PlayerCard`, `CupGames` list patterns, the loading skeletons and the footer. A game row or a "Game page →" link goes to `/game/{id}` only when the game exists.
- **No headline and no story text** from any source is published. The page shows scores, leaders and numbers only.
- **Counting animation:** the hero counts up and a timeout forces the final values; under reduced motion the final values show at once.

### New components

| Component | What it is |
|---|---|
| `PlayoffsHeader` | Season tag, state line, h1 and stage strip (reuses `StageStrip`) |
| `PlayoffPicture` | The two conference tables of the picture state, with the playoff and play-in lines |
| `PlayInStrip` | One play-in card per conference |
| `PlayoffBracket` | The 16-team bracket: camera, world, connectors, level switcher, controls (reuses the shared bracket camera, ADR 0034) |
| `SeriesNode` | One series card at level 1 and level 2 |
| `SeriesGameLine` | One game row of a series: game number, home/away and score, used at level 2 and in the sheet |
| `SeriesSheet` | The mobile bottom sheet of one series |
| `ChampionHero` | The complete-state hero: tag, h1, champion, stats row, buttons, plate |
| `TrophyDrawing` | The original line-drawn trophy |
| `FinalsMvpCard` | The Finals MVP card |
| `ConferenceMvpCard` | A conference finals MVP card |
| `FinalsSeries` | Game tabs and the selected game |
| `WinProbabilityChart` | The win probability SVG |
| `RoadToTitle` | The two finalists' cards and their four series |
| `HeadToHead` | The record row, the mirrored bars and the postseason averages table |
| `MirroredBar` | One head to head bar |
| `PostseasonAverages` | The averages table with a tab per finalist |
| `PlayoffLeaders` | Category tabs, the leader card and ranks 2 to 5 |
| `AwardsGrid` | The awards cards and the team award lists |
| `AwardCard` | One award card |
| `TournamentTag` | The stage tag (`Play-In`, `Playoffs`, `NBA Finals`, `NBA Cup`) |
| `StakesFlag` | The stakes flag of a game |
| `TitleBadge` | A current season title on the team page header |

## Shared patterns

- Ground, ink, muted, accent, accent text, divider and row rules are the existing tokens. Headings Barlow Condensed 600, body Barlow, numbers `font-variant-numeric: tabular-nums`.
- Content max width 1320px, side padding `clamp(20px, 4vw, 48px)`, section gap `clamp(64px, 8vw, 104px)`, `scroll-margin-top: 72px`. Section header: h2 `clamp(28px, 3.4vw, 40px)`, uppercase, optional meta right.
- Tags: accent outline, 11px, .16em, uppercase, accent text (`StatusTag`).
- Team color: the team's color from the feed, used only for bars and strips next to the code, as in the standings tables. A winner is shown in ink, a loser muted.
- Photos: a tile with the player's photo; when it is missing, the player's initials. A photo never links by itself.
- The 680px break is `--game-row-breakpoint`.
- Corner ticks: accent ticks at the four corners, as on the Cup nodes and the blueprint frames.

## Nav

- Links: Games · Standings · Cup · Playoffs, then the search trigger. Same rules as the standings page: two rows below 680px. Playoffs is active on `/playoffs`.

## Header

- Season tag (accent outline) and a state line. The tag reads `{season}`. The state line, by state:
  - `picture`: "Playoff picture"
  - `playin`: "Play-In"
  - `playoffs`: "First round" / "Conference semifinals" / "Conference finals"
  - `finals`: "NBA Finals · Game 3 · NYK leads series 2–1" (the game number comes from the feed and the series summary is written by the page from the wins of the Finals series; before the first game, "NBA Finals")
  - `complete`: "Complete"
- H1 "Playoffs", `clamp(56px, 9vw, 128px)`. In the `complete` state the champion hero replaces the H1 (see "Champion hero").
- **Stage strip**, 5 columns: Play-In · Round 1 · Conf. semis · Conf. finals · Finals, each with its dates (or "TBD") and a status: Complete / In progress / Next / Upcoming. The current stage has a 2px accent top rule, a completed one 1px accent, the others a divider. In the `picture` state every stage reads "TBD" and "Upcoming", except the first, which reads "Next". 2x2 plus one full-width cell below 680px.
- **Section order:**
  - `complete`: Champion hero, Finals MVP, the series, road to the title, head to head, leaders, bracket, awards.
  - Every other state: bracket and play-in first (in the `picture` state, the conference tables first, then the bracket and the play-in strip), then leaders. The hype blocks (Finals MVP, the series, road to the title, head to head) appear as their data exists: the series and the head to head appear once the Finals are scheduled and have the data, the awards appear when the feed has awards.

## Picture state

- Two conference tables, East and West, reusing the standings table: seed, team (monogram, name), record, GB and the clinch tag. The rows are seeds 1 to 10 in conference order, from the standings data in the feed.
- **Playoff line:** a solid accent line under seed 6, labeled "Playoffs". **Play-in line:** a dashed accent line under seed 10, labeled "Play-In". Seeds 7 to 10 sit between the two lines.
- Below the tables: the bracket with "To be decided" slots labeled by seed (see "Bracket"), then the play-in strip with its four slots (see "Play-in").
- The tables and the clinch tags are the standings values, not recomputed.

## Champion hero

The complete state opens with the hero.

- 56px grid background of ink at 3.5%.
- **Left column:**
  - Tag `{year} NBA Finals` (accent outline) and a line `{Team} win series 4–1 · {dates}`; the result and the dates come from the feed.
  - H1 "Champions", `clamp(76px, 12.5vw, 196px)`, line-height .82.
  - A 58px monogram with a two-color strip and the full team name.
  - A ruled row of four stats: postseason record, home record, road record and the point differential in accent. The point differential is summed by the backend from the postseason game scores.
  - The stats count up over 1.4s; a 1.6s timeout forces the final values. Under reduced motion the final values show at once.
  - Two buttons: "Relive the series" (the page's only solid button; it scrolls to the series section) and "Full bracket" (outline; it scrolls to the bracket).
- **Right column:** a plate with a 26:30 ratio and accent corner ticks. It holds the original trophy drawing, drawn in accent light at a 1.3px line, or the Finals MVP photo when the feed has no drawing flag. The label `{year} champions` sits at the top left.
- There is no franchise history and no records ticker.
- **Mobile:** a compact hero; the trophy is 150px tall beside the headline; the stats are 2x2.

### Trophy drawing

- An original line drawing in the site's blueprint style: a cup on a stepped base, two handles, thin construction lines and small tick marks, drawn only with lines. It is not a copy of any real trophy. It carries no name, no dimensions and no materials, and no text.
- It is one inline SVG with a stroke and no fill, `vector-effect: non-scaling-stroke`, and an accessible title "{year} champions".

## Finals MVP

- A card with corner ticks. The photo sits on a radial accent glow. Under it: the name and the label "Finals MVP".
- A 2x2 grid: postseason points per game, the best game points in accent (the best scoring game of the series, from the box scores), rebounds · assists, and games. There are no votes.
- **Conference finals MVPs** sit beside it as horizontal cards (photo, name, "East finals MVP" or "West finals MVP", team code).
- When the feed has no Finals MVP, the card is not drawn and the conference finals MVPs show alone; with neither, the section is hidden.

## The series

- **Game tabs**, one per game played. Each tab shows `G{n}`, the winner code (accent when the champion won it), the score and "OT" when the game went to overtime. The active tab has a 2px accent bottom rule. Games 5 to 7 that are not scheduled have no tab.
- **Selected game:**
  - A 16:9 frame with the highlights when the feed has them, a placeholder otherwise (a blueprint frame with the label "Highlights not available").
  - A win probability chart (480x120 SVG): the curve of the champion side, a dashed 50% line, quarter dividers and the largest deficit marked with its value. When the feed has no curve, the chart is not drawn.
  - The score, the two leaders of the game with photos (name, team, line) and a link "Game page →".
- There is no headline and no story text.
- **Mobile:** the tabs become a horizontal snap scroller of 132px cards.
- A click on a game inside the Finals series in the bracket selects that game here and scrolls to the section.

## Road to the title

- Two cards, one per finalist: monogram, full name, the seed and regular season record (`#1 seed · 64-18`) and the postseason record.
- Under each card, four rows, one per series: round · opponent seed · opponent (monogram, name, a team bar) · result (`4–1`, with W or L). Losses are muted.
- A finalist whose path is incomplete (a series without data) shows the rows the feed has.

## Head to head

- A record row: both finalists' postseason record.
- **Eight mirrored bars**, in this order: points per game, FG%, eFG%, assists, rebounds, blocks, steals, technical fouls. The better side is drawn in its team color and ink; the other side is muted. For technical fouls, lower is better. The feed sends the values and which side is better.
- Then the **"Postseason averages"** table with a tab per finalist: 30px photo, player, PTS, REB, AST, BLK, FG%, one row per roster player. A player without postseason stats shows `—` in every stat cell and sits at the end of the table.

## Leaders

- Nine category tabs: points, rebounds, assists, steals, blocks, field goal percentage, three-pointers made, double-doubles and minutes. Chips on mobile.
- The leader card: photo, name, team and the value at 56 to 84px (`clamp`), with the category label. Ranks 2 to 5 as rows: rank, photo, name, team, value.
- A category with fewer than five leaders shows the ranks the feed has.

## Awards

- A grid of cards for the awards the feed has (up to 20): MVP, Defensive Player of the Year, Rookie of the Year, Sixth Man, Most Improved, Clutch Player, Finals MVP, East and West finals MVP, All-Star MVP, Cup MVP, the Cup All-Tournament team, All-NBA 1st, 2nd and 3rd teams, All-Rookie 1st and 2nd teams, All-Defensive 1st and 2nd teams and the Twyman-Stokes award. There is no coach card.
- **Player awards:** a card with a short code (English: MVP, DPOY, ROY, 6MOY, MIP, CPOY, FMVP, ECF MVP, WCF MVP, ASG MVP, CUP MVP; Spanish: MVP, JDA, NDA, SHA, JMM, JCA, MVP FINALES, MVP ESTE, MVP OESTE, MVP ALL-STAR, MVP COPA; the strings table has the keys), the photo, the award name, the name and the team.
- **Team awards** (teams of five players): a card with the award name and a list of one row per winner the feed sends (photo, name, team code). A tie gives six rows (ADR 0055). On a past season the team code is the season's code.
- Mobile: a horizontal snap scroller of 156px cards.
- No votes are shown.

## Bracket

Levels 1 and 2, as in the Cup, with 16 teams.

### World (desktop, 680px and wider)

- World 1400x650. Seven columns, 176px wide, every 204px, left to right: East round 1 · East semifinals · East finals · NBA Finals · West finals · West semifinals · West round 1.
- Row centers: round 1 at 105, 235, 365 and 495; the semifinals at 170 and 430; the conference finals and the Finals at 300.
- **Series card:** two 33px rows. Each row: seed, a 4px team bar, the code and the wins. The loser is muted. The Finals card has an accent border and a "Champion" label when the series is complete.
- **Connectors:** orthogonal SVG lines at ink 20%, with `vector-effect: non-scaling-stroke`. A connector whose feeder series is complete is drawn at accent.
- Card frames, dashed frames and the focus ring are drawn in the connectors layer with `vector-effect: non-scaling-stroke`, as on the Cup nodes, so borders keep their width at every zoom.

### Camera

- The Cup camera: one layer with translate and scale, `transform-origin: 0 0`, a transition of 0.8s `cubic-bezier(.2, .7, .1, 1)`.
- **Level 1** fits the whole bracket. **Level 2** fits one series plus its games, up to 4.4x. The list of games fades in (0.45s, with a 0.35s delay): rows `G1 · at NYK`, the winner and the score in ink, the loser muted, "OT" in accent. A game that is not scheduled is not listed.
- **Controls:** a segmented switch "1 Bracket / 2 Series" at the top left; previous and next at the top right, cycling the 15 series in bracket order; the keyboard arrows and Esc; a click outside the series zooms out. In the Finals card a click on a game selects it in the series section.
- Under reduced motion the camera moves without the transition.

### Undecided series

- A dashed card with the slot label: "East #1 seed", "Winner of East R1 1", "Winner of East semifinal 1", "East play-in winner". During the regular season, a "Currently XXX" line from the standings seeds.
- A series with one side decided shows that side and a dashed row for the other.
- The bracket always shows its 15 series and 16 slots, with or without data.

### Play-in

- One card per conference with three games: 7th vs 8th, 9th vs 10th and the game for the 8th seed. Each game shows the two teams, the score once played and the outcome ("PHI → No. 7", "MIA out").
- A slot that is not decided reads "To be decided" with the regular season place ("Loser of 7th vs 8th", "Winner of 9th vs 10th"). The slots fill as each game is final.
- The strip appears in the `picture` and `playin` states; in later states it stays below the bracket as a record, collapsed to the outcomes.

### Mobile (under 680px)

- Stacked rounds, in this order: East round 1 (2x2) → East semifinals → East finals → NBA Finals → West finals → West semifinals → West round 1.
- A tap on a series opens a bottom sheet: a `translateY` slide of 0.5s, a maximum height of 86vh, a 60% scrim, the body scroll locked. It shows the score and every game of the series in 44px rows, each linking to its game page. Esc and a tap on the scrim close it.
- There are no zoom controls.

### Out of this design

Continuous zoom levels with rosters inside the bracket, and pinch-to-enter.

## Tournament tags and titles

Marks on pages that already exist, extending the Cup marks (ADR 0031). `/web` computes nothing for them: the stage, the context and the stakes flag come from the feeds, and a mark whose field is absent is not drawn. A regular season game carries no tag.

### Stage tag

| Game | Tag | Style |
|---|---|---|
| Play-in game | `Play-In` | ink 35% border, ink text |
| Playoff game (rounds 1 to 3) | `Playoffs` | ink 35% border, ink text |
| NBA Finals game | `NBA Finals` | solid accent, ground text |
| Cup game | `NBA Cup · {stage}` | as today |

Same size, letter spacing and truncation as the Cup tag: 11px, .16em, uppercase, ellipsis, no wrap. The tag is plain text: it does not link and has no hover state.

### Context line

- Muted caps, after the tag: `West finals · Game 7`, `Game 5 · NYK leads series 3–1` (the Finals), `East · 7th vs 8th` (the play-in). The feed sends the round, the game number, the series wins and winner and the play-in place as values; the page writes the words, the series summary included.

### Stakes flag

- At most one flag per game, computed by the backend from the series wins: "Game 7", "Elimination", "Can clinch", "Clinched". The page draws the flag the feed sends and never decides which one. It is an accent outline tag next to the context line.

### Home game card

- The stage tag first in the card's center column, above the status line (first in the status line on the mobile row), then the context line, then the stakes flag. A regular season game shows nothing.

### Game page header

- The stage tag as the first item of the kicker line, before the date and the venue; then the context line and the stakes flag. Same truncation as on the home card.

### Team page header

- Titles for the current season only, in the header's name block:
  - `{year} NBA Champions`: solid accent, ground text.
  - `{year} NBA Cup Champions`: accent outline.
  - `East Champions` / `West Champions`: accent outline.
- A team can carry more than one title; they wrap at spaces. A team without a title shows none and the cells around keep their order. Titles do not link.
- The Cup line (`{group} · {W}-{L}`) is unchanged.

## Edge cases

| Case | What shows |
|---|---|
| Preseason | `picture` state. The tables show the teams with `—` in every value and no clinch tags; the lines are drawn; the bracket shows all its slots labeled by seed and "To be decided"; the stage strip reads "TBD" |
| Regular season | `picture` state. Seeds 1 to 10 per conference from the standings, the playoff and play-in lines, clinch tags from the feed, and "Currently XXX" in the bracket slots |
| Play-in before any game | The four slots show "To be decided" with the regular season places (7th, 8th, 9th, 10th); the games show their date and time |
| Play-in after each game | The card shows the score and the outcome ("PHI → No. 7", "MIA out"); the winner fills its slot; the 8th seed game takes the loser of 7th vs 8th and the winner of 9th vs 10th; the bracket slot fills when the seed is decided |
| Series with games 5 to 7 not scheduled | No tab, no row, no list entry for them; the series summary still shows ("Series tied 2–2") |
| Series not started | The card shows the seeds and codes with wins `0` (or `—` when the feed has none); no games list; level 2 shows the first game's date and venue when scheduled |
| Game with overtime | "OT" after the score in the tab, in the games list in accent, and in the sheet row; "Final/OT" in the status |
| No highlights | The 16:9 placeholder "Highlights not available"; the rest of the game block shows |
| Win probability missing | The chart is not drawn; the score, the leaders and the link show |
| Missing values | `—` in that cell, bar or stat |
| Finalists' roster players without postseason stats | A row with the player and `—` in each stat cell, after the rows with stats |
| Awards without a photo | Initials in the photo tile |
| Team awards | Lists of five rows with photo (or initials), name and team code; a list with fewer than five shows the rows the feed has |
| Award without a winner | The card is not drawn |
| Missing block | The section is hidden; the section order does not change |
| Unavailable feed | The nav row, then the home's 503 state: "Data isn't available right now. Check back later." |
| Finals detail feed unavailable | The hype sections (Finals MVP, series, road to the title, head to head) are hidden; the hero, the bracket, the leaders and the awards stay |
| Spanish strings | Every string has a Spanish text; long labels truncate, never wrap in a table cell |

## States

| State | What shows |
|---|---|
| Loading | Skeletons shaped like the header and the first section, with the home's shimmer, stopped under reduced motion |
| Feed unavailable | See Edge cases; polling continues and the page fills in when a request succeeds |
| Finals detail unavailable | See Edge cases; the bracket stays |
| Picture / play-in / playoffs / finals / complete | Per the state rules in Overview and Header |

## Interactions and motion

| What | How |
|---|---|
| Bracket camera | The Cup camera: 0.8s `cubic-bezier(.2, .7, .1, 1)`; none under reduced motion |
| Series zoom | Level 2 game list fades in over 0.45s with a 0.35s delay |
| Prev / next, arrows, Esc | Cycle the 15 series in bracket order; Esc and a click outside zoom out |
| Finals card game click | Selects the game in the series section |
| Hero stats | Count up over 1.4s; a 1.6s timeout forces the final values; none under reduced motion |
| Game tabs | Select the game; the active tab has an accent bottom rule |
| Leader tabs | Switch the category |
| Head to head tabs | Switch the finalist in the averages table |
| Mobile series sheet | `translateY` over 0.5s, 60% scrim, body scroll locked |
| Focus | `:focus-visible` as on the home. A Tab onto a card outside the level 2 view shifts the camera so the card is visible, as in the Cup. The arrow keys move the focus to the newly selected card. Every focus ring, the Finals game buttons included, stays 2px at any zoom |

## Responsive

- Under 680px: the nav is two rows, the stage strip is 2x2 plus one cell, the hero is compact (trophy 150px, stats 2x2), the game tabs and the award cards are snap scrollers (132px and 156px), the leader tabs are chips, the bracket is stacked rounds with a bottom sheet and no zoom controls.
- Tables scroll horizontally with a sticky first column.

## New tokens

To add to `web/src/lib/styles/tokens.css` in the implementing issue. Values not listed map to existing tokens.

| Token (suggested) | Value | Use |
|---|---|---|
| `--playoffs-title-size` | `clamp(56px, 9vw, 128px)` | H1 |
| `--playoffs-hero-title-size` | `clamp(76px, 12.5vw, 196px)` | Hero H1 |
| `--playoffs-hero-title-size-mobile` | `clamp(36px, 12vw, 76px)` | Hero H1 under the mobile layout, next to the trophy |
| `--playoffs-hero-title-leading` | .82 | Hero H1 line height |
| `--playoffs-hero-grid-size` | 56px | Hero grid background |
| `--playoffs-hero-grid-alpha` | .035 | Hero grid ink opacity |
| `--playoffs-champion-mark` | 58px | Champion monogram |
| `--playoffs-plate-ratio` | 26 / 30 | Hero plate |
| `--playoffs-trophy-stroke` | 1.3px | Trophy line |
| `--playoffs-trophy-mobile-height` | 150px | Mobile trophy |
| `--playoffs-count-duration` | 1.4s | Hero count-up |
| `--playoffs-count-timeout` | 1.6s | Final values forced |
| `--playoffs-stage-columns` | 5 | Stage strip |
| `--playoffs-tag-border` | ink at 35% | Play-In and Playoffs tags |
| `--playoffs-mark-gap` | 6px | Gap inside the postseason mark |
| `--playoffs-series-tab-mobile` | 132px | Game tab card on mobile |
| `--playoffs-award-card-mobile` | 156px | Award card on mobile |
| `--playoffs-wp-width` | 480px | Win probability viewBox |
| `--playoffs-wp-height` | 120px | Win probability viewBox |
| `--playoffs-leader-value-size` | `clamp(56px, 7vw, 84px)` | Leader value |
| `--playoffs-avatar-size` | 30px | Averages table photo |
| `--playoffs-tab-rule` | 2px | Active game tab rule |
| `--playoffs-card-photo-size` | 96px | Finals MVP and award card photo |
| `--playoffs-world-width` | 1400px | Desktop world |
| `--playoffs-world-height` | 650px | Desktop world |
| `--playoffs-column-width` | 176px | Bracket column |
| `--playoffs-column-step` | 204px | Bracket column spacing |
| `--playoffs-row-height` | 33px | Series card row |
| `--playoffs-team-bar` | 4px | Series card team bar |
| `--playoffs-line-color` | ink at 20% | Connector |
| `--playoffs-camera-duration` | 0.8s | Camera transition |
| `--playoffs-camera-easing` | `cubic-bezier(.2, .7, .1, 1)` | Camera transition |
| `--playoffs-series-zoom-max` | 4.4 | Level 2 zoom ceiling |
| `--playoffs-games-fade` | 0.45s | Game list fade |
| `--playoffs-games-fade-delay` | 0.35s | Game list fade delay |
| `--playoffs-sheet-duration` | 0.5s | Mobile sheet |
| `--playoffs-sheet-max-height` | 86vh | Mobile sheet |
| `--playoffs-sheet-scrim` | `rgba(0, 0, 0, .6)` | Mobile sheet scrim |
| `--playoffs-sheet-row` | 44px | Mobile sheet game row |
| `--playoffs-viewport-height` | `clamp(360px, 46vw, 650px)` | Bracket viewport (not in the design: plan choice) |
| `--playoffs-game-row-height` | 8px | Level 2 game row, in world units (plan choice) |
| `--playoffs-game-text-size` | 4px | Level 2 game text, in world units (plan choice) |
| `--playoffs-games-gap` | 4px | Gap between a card and its games, in world units (plan choice) |

Mapped to existing tokens: the divider is `--color-divider`; accent text is `--color-accent-light`; label size and spacing are `--label-size` and `--label-letter-spacing`; the 680px break is `--game-row-breakpoint`; ground text on the accent tag is the ground token.

## Strings

| Key (suggested) | English | Spanish |
|---|---|---|
| `nav_playoffs` | Playoffs | Playoffs |
| `playoffs_title` | Playoffs | Playoffs |
| `playoffs_state_picture` | Playoff picture | Panorama de playoffs |
| `playoffs_state_playin` | Play-In | Play-In |
| `playoffs_state_r1` | First round | Primera ronda |
| `playoffs_state_r2` | Conference semifinals | Semifinales de conferencia |
| `playoffs_state_r3` | Conference finals | Finales de conferencia |
| `playoffs_state_finals` | NBA Finals | Finales de la NBA |
| `playoffs_state_complete` | Complete | Completa |
| `playoffs_stage_playin` | Play-In | Play-In |
| `playoffs_stage_r1` | Round 1 | Ronda 1 |
| `playoffs_stage_r2` | Conf. semis | Semis conf. |
| `playoffs_stage_r3` | Conf. finals | Finales conf. |
| `playoffs_stage_finals` | Finals | Finales |
| `playoffs_tbd` | TBD | Por definir |
| `playoffs_status_complete` | Complete | Completa |
| `playoffs_status_in_progress` | In progress | En curso |
| `playoffs_status_next` | Next | Siguiente |
| `playoffs_status_upcoming` | Upcoming | Próximamente |
| `playoffs_unavailable` | Data isn't available right now. Check back later. | Los datos no están disponibles ahora. Vuelve más tarde. |
| `playoffs_line_playoffs` | Playoffs | Playoffs |
| `playoffs_line_playin` | Play-In | Play-In |
| `playoffs_col_seed` | Seed | Cl. |
| `playoffs_col_team` | Team | Equipo |
| `playoffs_col_record` | Record | Récord |
| `playoffs_col_gb` | GB | DIF |
| `playoffs_east` | East | Este |
| `playoffs_west` | West | Oeste |
| `playoffs_hero_tag` | {year} NBA Finals | Finales de la NBA {year} |
| `playoffs_hero_result` | {team} win series {score} · {dates} | {team} ganan la serie {score} · {dates} |
| `playoffs_hero_title` | Champions | Campeones |
| `playoffs_hero_champions` | {year} champions | Campeones {year} |
| `playoffs_hero_record` | Postseason record | Récord de postemporada |
| `playoffs_hero_home` | Home | Local |
| `playoffs_hero_road` | Road | Visitante |
| `playoffs_hero_diff` | Point differential | Diferencial de puntos |
| `playoffs_relive` | Relive the series | Revive la serie |
| `playoffs_full_bracket` | Full bracket | Cuadro completo |
| `playoffs_finals_mvp` | Finals MVP | MVP de las Finales |
| `playoffs_ecf_mvp` | East finals MVP | MVP de la final del Este |
| `playoffs_wcf_mvp` | West finals MVP | MVP de la final del Oeste |
| `playoffs_mvp_ppg` | Points per game | Puntos por partido |
| `playoffs_mvp_best` | Best game | Mejor partido |
| `playoffs_mvp_reb_ast` | REB · AST | REB · AST |
| `playoffs_mvp_games` | Games | Partidos |
| `playoffs_series` | The series | La serie |
| `playoffs_game_tab` | G{n} | P{n} |
| `playoffs_ot` | OT | TE |
| `playoffs_no_highlights` | Highlights not available | Resumen no disponible |
| `playoffs_win_probability` | Win probability | Probabilidad de victoria |
| `playoffs_largest_deficit` | Largest deficit: {n} | Mayor desventaja: {n} |
| `playoffs_game_page` | Game page → | Página del partido → |
| `playoffs_road` | Road to the title | El camino al título |
| `playoffs_road_opponent_seed` | #{seed} | n.º {seed} |
| `playoffs_road_seed` | #{seed} seed · {record} | Cabeza de serie {seed} · {record} |
| `playoffs_round_1` | Round 1 | Ronda 1 |
| `playoffs_round_2` | Conference semifinals | Semifinales de conferencia |
| `playoffs_round_3` | Conference finals | Finales de conferencia |
| `playoffs_round_4` | NBA Finals | Finales de la NBA |
| `playoffs_h2h` | Head to head | Frente a frente |
| `playoffs_bar_ppg` | Points per game | Puntos por partido |
| `playoffs_bar_fg` | FG% | % de tiro |
| `playoffs_bar_efg` | eFG% | % de tiro efectivo |
| `playoffs_bar_ast` | Assists | Asistencias |
| `playoffs_bar_reb` | Rebounds | Rebotes |
| `playoffs_bar_blk` | Blocks | Tapones |
| `playoffs_bar_stl` | Steals | Robos |
| `playoffs_bar_tech` | Technical fouls | Faltas técnicas |
| `playoffs_averages` | Postseason averages | Promedios de postemporada |
| `playoffs_col_player` | Player | Jugador |
| `playoffs_col_pts` | PTS | PTS |
| `playoffs_col_reb` | REB | REB |
| `playoffs_col_ast` | AST | AST |
| `playoffs_col_blk` | BLK | TAP |
| `playoffs_col_fg` | FG% | %T |
| `playoffs_leaders` | Leaders | Líderes |
| `playoffs_leader_pts` | Points | Puntos |
| `playoffs_leader_reb` | Rebounds | Rebotes |
| `playoffs_leader_ast` | Assists | Asistencias |
| `playoffs_leader_stl` | Steals | Robos |
| `playoffs_leader_blk` | Blocks | Tapones |
| `playoffs_leader_fg` | Field goal % | % de tiro |
| `playoffs_leader_3pm` | 3-pointers made | Triples anotados |
| `playoffs_leader_dd` | Double-doubles | Dobles-dobles |
| `playoffs_leader_min` | Minutes | Minutos |
| `playoffs_awards` | Awards | Premios |
| `playoffs_award_mvp` | Most Valuable Player | Jugador Más Valioso |
| `playoffs_award_dpoy` | Defensive Player of the Year | Jugador Defensivo del Año |
| `playoffs_award_roy` | Rookie of the Year | Novato del Año |
| `playoffs_award_6moy` | Sixth Man of the Year | Sexto Hombre del Año |
| `playoffs_award_mip` | Most Improved Player | Jugador Más Mejorado |
| `playoffs_award_cpoy` | Clutch Player of the Year | Jugador Clutch del Año |
| `playoffs_award_fmvp` | Finals MVP | MVP de las Finales |
| `playoffs_award_ecf` | East finals MVP | MVP de la final del Este |
| `playoffs_award_wcf` | West finals MVP | MVP de la final del Oeste |
| `playoffs_award_asg` | All-Star MVP | MVP del All-Star |
| `playoffs_award_cup` | NBA Cup MVP | MVP de la Copa NBA |
| `playoffs_award_cup_team` | NBA Cup All-Tournament Team | Quinteto del Torneo de la Copa NBA |
| `playoffs_award_all_nba` | All-NBA {n} Team | Mejor quinteto de la NBA ({n}.º) |
| `playoffs_award_all_rookie` | All-Rookie {n} Team | Mejor quinteto de novatos ({n}.º) |
| `playoffs_award_all_defense` | All-Defensive {n} Team | Mejor quinteto defensivo ({n}.º) |
| `playoffs_award_twyman` | Twyman-Stokes Teammate Award | Premio Twyman-Stokes al compañero |
| `playoffs_bracket` | Bracket | Cuadro |
| `playoffs_level_1` | Bracket | Cuadro |
| `playoffs_level_2` | Series | Serie |
| `playoffs_prev` | Previous series | Serie anterior |
| `playoffs_next` | Next series | Serie siguiente |
| `playoffs_champion` | Champion | Campeón |
| `playoffs_tbd_slot` | To be decided | Por decidir |
| `playoffs_currently` | Currently {team} | Actualmente {team} |
| `playoffs_slot_seed` | {conference} #{seed} seed | {conference} · cabeza de serie {seed} |
| `playoffs_slot_r1_winner` | Winner of {conference} R1 {n} | Ganador de la ronda 1 {n} del {conference} |
| `playoffs_slot_r2_winner` | Winner of {conference} semifinal {n} | Ganador de la semifinal {n} del {conference} |
| `playoffs_slot_r3_winner` | Winner of {conference} finals | Ganador de la final del {conference} |
| `playoffs_slot_playin_winner` | {conference} play-in winner | Ganador del play-in del {conference} |
| `playoffs_game_at` | G{n} · at {team} | P{n} · en {team} |
| `playoffs_game_home` | G{n} · vs {team} | P{n} · ante {team} |
| `playoffs_sheet_close` | Close | Cerrar |
| `playoffs_playin_title` | Play-In | Play-In |
| `playoffs_playin_7v8` | 7th vs 8th | 7.º contra 8.º |
| `playoffs_playin_9v10` | 9th vs 10th | 9.º contra 10.º |
| `playoffs_playin_8th` | 8th seed game | Partido por el 8.º puesto |
| `playoffs_playin_to_seed` | {team} → No. {seed} | {team} → n.º {seed} |
| `playoffs_playin_out` | {team} out | {team} eliminado |
| `playoffs_playin_loser` | Loser of {game} | Perdedor de {game} |
| `playoffs_playin_winner` | Winner of {game} | Ganador de {game} |
| `playoffs_tag_playin` | Play-In | Play-In |
| `playoffs_tag_playoffs` | Playoffs | Playoffs |
| `playoffs_tag_finals` | NBA Finals | Finales de la NBA |
| `playoffs_context_series` | {round} · Game {n} | {round} · Partido {n} |
| `playoffs_context_finals` | Game {n} · {summary} | Partido {n} · {summary} |
| `playoffs_series_wins` | {team} wins series {won}–{lost} | {team} gana la serie {won}–{lost} |
| `playoffs_series_leads` | {team} leads series {leading}–{trailing} | {team} lidera la serie {leading}–{trailing} |
| `playoffs_code_mvp` | MVP | MVP |
| `playoffs_code_dpoy` | DPOY | JDA |
| `playoffs_code_roy` | ROY | NDA |
| `playoffs_code_6moy` | 6MOY | SHA |
| `playoffs_code_mip` | MIP | JMM |
| `playoffs_code_cpoy` | CPOY | JCA |
| `playoffs_code_fmvp` | FMVP | MVP FINALES |
| `playoffs_code_ecf` | ECF MVP | MVP ESTE |
| `playoffs_code_wcf` | WCF MVP | MVP OESTE |
| `playoffs_code_asg` | ASG MVP | MVP ALL-STAR |
| `playoffs_code_cup` | CUP MVP | MVP COPA |
| `playoffs_context_playin` | {conference} · {game} | {conference} · {game} |
| `playoffs_context_round_1` | {conference} round 1 | Ronda 1 del {conference} |
| `playoffs_context_round_2` | {conference} semifinals | Semifinales del {conference} |
| `playoffs_context_round_3` | {conference} finals | Final del {conference} |
| `playoffs_context_game` | Game {n} | Partido {n} |
| `playoffs_flag_game_7` | Game 7 | Partido 7 |
| `playoffs_flag_elimination` | Elimination | Eliminación |
| `playoffs_flag_can_clinch` | Can clinch | Puede ganar la serie |
| `playoffs_flag_clinched` | Clinched | Serie ganada |
| `playoffs_title_champions` | {year} NBA Champions | Campeones de la NBA {year} |
| `playoffs_title_cup` | {year} NBA Cup Champions | Campeones de la Copa NBA {year} |
| `playoffs_title_east` | East Champions | Campeones del Este |
| `playoffs_title_west` | West Champions | Campeones del Oeste |

The series wins and winner (the page writes the summary, "NYK leads 3-1" or "Series tied 2-2", from them), stage dates, the "Currently" team, play-in outcomes and the point differential come from the feed; slot labels and play-in slots are sent as keys and parts, and the page writes the words with the keys above. The other keys are the fixed words around them. Strings for the Cup marks stay in `docs/design-cup.md`.

## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601. Every value is computed by the backend; exact field names are set by `docs/api/playoffs.md` in the issues that add the feeds. Both feeds are built on demand and expire with the rules recorded in `docs/architecture.md`: after a postseason game is final they refresh within the hour, and once the Finals series is complete they are built once and kept.

### Playoffs feed (`/feeds/playoffs.json`)

- State (`picture`, `playin`, `playoffs`, `finals`, `complete`), the current round, the state line values (the finals game number and series summary), and the five stage entries with dates and status.
- The picture tables: per conference, seeds 1 to 10 with team, record, GB, clinch tag and the line markers.
- The play-in: per conference the three games with teams, scores, status, date, game id when the game exists, the outcome and the slots with their regular season places.
- The bracket: the 15 series in bracket order, each with round, conference, slot labels as keys and parts, both teams (code, name, color, seed), wins per team and the series summary from the feed, status, winner, the "Currently" team during the regular season, and the games played (game number, date, home and away, scores, overtime flag, winner, game id when it exists, venue, broadcast).
- The champion block when complete: team, series result, dates, postseason record, home, road and the point differential, and the drawing flag for the plate.
- The leaders: nine categories, each with the five leaders (rank, player, photo, team, value).
- The awards: the awards with winners (player or team of five players, photo, team) and the code of each.
- The conference finals MVPs and the Finals MVP block (name, photo, postseason averages).
- Per game, for the home card, the game page and the team page: a nullable `postseason` object with `stage` (`playin`, `playoffs`, `finals`), the round, the game number, the series summary, the play-in place and one `stakes` value (`game_7`, `elimination`, `can_clinch`, `clinched`, or `null`); and a nullable list of current season titles on the team feed.

### Finals feed (`/feeds/playoffs/finals.json`)

- The Finals games, one per game played: score, overtime flag, winner, the two leaders with photos, the win probability curve of the champion side, the largest deficit, the highlights when stored (`null` otherwise), and the game id.
- The Finals MVP card: postseason points, rebounds, assists, games and the best scoring game of the series from the box scores.
- The road to the title: for each finalist, the seed and regular season record, the postseason record and the four series (round, opponent seed, opponent, result).
- The head to head: the postseason records and the eight bars with both values and which side is better.
- The postseason averages of both rosters: per player the photo, PTS, REB, AST, BLK and FG%, with `null` values for a player without postseason stats; the whole block is `null` on a past season (no read carries them, ADR 0058) and the table is hidden.
