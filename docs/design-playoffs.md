# Design: Playoffs

The visual, interaction and data specification of the playoffs page (`/playoffs`), the Playoffs link in the nav, the 16-team bracket, the play-in and the full series page (`/playoffs/series`), the champion hero, the Finals MVP card, the Finals series, the road to the title, the head to head, the leaders, the awards, and the tournament tags and titles on the home card, the game page header and the team page header. It extends `docs/design.md` and `docs/design-cup.md`: every token, rule and shared component defined there applies here, and only new values are listed under "New tokens". The playoffs bracket is a plain grid at 1:1 with no camera (ADR 0071); the Cup keeps the shared camera (ADR 0034). The player card, games list, header, stage strip and marks are reused (ADR 0030, ADR 0031); nothing in the Cup behavior changes.

## Overview

| Page | Route | Feeds |
|---|---|---|
| Playoffs | `/playoffs` | `/feeds/playoffs.json`, `/feeds/playoffs/finals.json` |
| Full series | `/playoffs/series?id={SeriesId}` | the same feeds (the Finals feed only for the Finals leaders) |

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
- **The bracket is a plain grid at 1:1:** no translate, no scale and no import of `web/src/lib/bracket/` (ADR 0071).
- **Shared components are reused:** nav row, `TeamMonogram`, `StatusTag`, `Kicker`, `BlueprintFrame`, `ClinchTag`, `StandingsTable` patterns, `StageStrip`, `PlayerCard`, `CupGames` list patterns, the loading skeletons and the footer. A game row or a "Game page →" link goes to `/game/{id}` only when the game exists.
- **No headline and no story text** from any source is published. The page shows scores, leaders and numbers only.
- **No counting animation:** the hero shows its final values at once.

### New components

| Component | What it is |
|---|---|
| `PlayoffsHeader` | Season tag, state line, h1 and stage strip (reuses `StageStrip`) |
| `PlayoffPicture` | The two conference tables of the picture state, with the playoff and play-in lines |
| `PlayInStrip` | One play-in card per conference |
| `PlayoffBracket` | The 16-team bracket as a plain grid: the seven-column map, the vertical tree, the result panel (no camera, ADR 0071) |
| `SeriesNode` | One series card (desktop map and vertical tree) |
| `SeriesGameLine` | One game cell of a series, used in the result panel and the sheet |
| `SeriesSheet` | The bottom sheet of one series under 1180px |
| `SeriesPage` | The full series page |
| `ChampionHero` | The complete-state hero: trophy and label, h1, subline, logo, game strip |
| `TrophyDrawing` | The small original line-drawn trophy |
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

- Links: the desktop row reads Games · Standings · Tournaments ▾, with Cup, All-Star and Playoffs inside the dropdown, then the search trigger. Same rules as the other pages (`docs/design.md`, "Nav row (every page)"). Playoffs is active on `/playoffs`.

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
- **Playoff line:** a solid 1px divider line under seed 6, labeled "Playoffs". **Play-in line:** a solid 1px divider line under seed 10, labeled "Play-In". Seeds 7 to 10 sit between the two lines.
- Below the tables: the bracket with "To be decided" slots labeled by seed (see "Bracket"), then the play-in strip with its four slots (see "Play-in").
- The tables and the clinch tags are the standings values, not recomputed.

## Champion hero

The complete state opens with the hero (`ChampionHero`, used by `PlayoffsHeader`). It has no background photo, no stats row, no buttons and no plate.

- **Section:** full width, a 1px bottom divider, the ground background plus an 88px grid of 1px lines at ink 3.5%. Content max-width 1440px, centered. Padding top `clamp(40px, 6vw, 88px)`, sides `clamp(20px, 3vw, 40px)`, bottom `clamp(32px, 4vw, 48px)`.
- **Glow:** a radial circle of the champion's resolved team color (ADR 0068) at 32%, `min(900px, 80vw)` wide, anchored right behind the logo.
- **Main row:** a grid of `repeat(auto-fit, minmax(min(100%, 460px), 1fr))`.
  - **Left:** a small trophy line drawing (26x54, 1.5px stroke, accent light) beside the label "{year} NBA Champions" (13px, .16em tracking, uppercase, accent light). The H1 "{city}<br>{team}" at `clamp(72px, 10.5vw, 156px)`, line-height .82, uppercase. A subline (18px): "Won the series {W}–{L} over {opponent city} · {dates}"; the result, the opponent and the dates come from the feed.
  - **Right:** the champion's logo from the feed's `logo` object, up to 520px square, `object-fit: contain`, `filter: drop-shadow(0 30px 40px rgba(0, 0, 0, .6))`.
- **Game strip:** one equal column per Finals game played (4 to 7), under a 1px top border at ink 18%. Each column shows "G{n}" (11px, uppercase, muted) above the score from the champion's side (such as `105–95`) at `clamp(20px, 2.4vw, 28px)`; a win in ink, a loss muted. The whole strip is one link to the Finals series section on the page (the scroll the old "Relive the series" button did).
- **Mobile (under 680px):** the trophy is 16x34 and the label 11px; the logo is centered at 230px above the H1; the H1 is 72px; the subline 15px; the strip scores 18px; the grid background 44px.
- There is no franchise history and no records ticker, and no count-up.

### Trophy drawing

- The trophy is a small original line drawing in the site's blueprint style: a cup on a stepped base with two handles, drawn only with lines. It is not a copy of any real trophy and carries no name, no dimensions, no materials and no text.
- It is one inline SVG with a stroke and no fill, `vector-effect: non-scaling-stroke`, and an accessible title "{year} NBA Champions". It is decorative beside the label and hidden from assistive technology when the label is next to it.

## Finals MVP

Replaces the content of `FinalsMvpCard` and `ConferenceMvpCard` in their section of the page.

- H2 "Finals MVP", `clamp(32px, 3.4vw, 44px)`, uppercase, with a 24px gap below.
- **Two columns** of `minmax(0, 1fr) minmax(0, 1fr)`, gap 24px, `align-items: stretch`; one column under 900px.
- **Left: the MVP card** in a `BlueprintFrame`, with an inner grid of `200px minmax(0, 1fr)`.
  - **Photo panel:** min-height 250px, `overflow: hidden`, background `radial-gradient(circle at 50% 80%, <team resolved color at 32%>, transparent 70%)`. The feed's `photoUrl` cutout is 300px wide, bottom-anchored, centered, with `drop-shadow(0 14px 16px rgba(0, 0, 0, .6))`. No logo sits behind the player.
  - **Info panel:** padding `24px 28px`, a 1px left divider, `justify-content: space-between`. The label "Finals MVP" (11px, .16em, uppercase, accent light); the name (36px, uppercase); a team row (18px logo plus the team name, 13px, muted); a 2x2 stat grid, gap `16px 20px`, each cell a value (30px) above its label (10.5px, uppercase, muted): points per game, best game (the value in accent light), rebounds · assists, and games. The stats are the postseason averages of ADR 0061; there are no votes.
  - **Under 680px:** the inner grid is one column (`--playoffs-mvp-photo-columns-mobile`). The photo panel stacks above the info panel at full width, with the same 250px height, glow and cutout; the info panel keeps its padding and moves its divider from the left to the top, so the 2x2 stats fit.
- **Right: the conference finals MVPs:** two blueprint cards with a 12px gap, each `flex: 1`, so together they match the height of the left card. Each card is a grid of `120px minmax(0, 1fr) auto`: a photo cell at the full card height with a glow of the team color at 35% and the cutout 170px wide, bottom-anchored; a text cell with the award label ("East Finals MVP" or "West Finals MVP", 10.5px, accent light), the name (24px, uppercase) and the team name (12.5px, muted); and the team logo at 36px at the right edge with a 22px right margin, replacing the tricode text.
- **Missing data keeps its rules:** no Finals MVP hides the left card; no conference MVP hides that card; neither hides the section. A missing stat shows `—`.

## The series

- **Game tabs**, one per game played. Each tab shows `G{n}`, the winner code (accent when the champion won it), the score and "OT" when the game went to overtime. The active tab has a 2px accent bottom rule. Games 5 to 7 that are not scheduled have no tab.
- **Selected game:**
  - A 16:9 frame with the highlights when the feed has them, a placeholder otherwise (a blueprint frame with the label "Highlights not available").
  - A win probability chart (480x120 SVG): the curve of the champion side, a dashed 50% line, quarter dividers and the largest deficit marked with its value. When the feed has no curve, the chart is not drawn.
  - The score, the two leaders of the game with photos (name, team, line) and a link "Game page →".
- There is no headline and no story text.
- **Mobile:** the tabs become a horizontal snap scroller of 132px cards.
- The hero's game strip links to this section.

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

A plain grid at 1:1: no translate, no scale and no camera, so it renders sharp at every browser zoom (ADR 0071). The playoffs section does not import `web/src/lib/bracket/`. It replaces `PlayoffBracket`, `BracketNode` and `SeriesNode` usage on the page and restyles `SeriesSheet` and `PlayInStrip`. The Cup is not touched.

### Header

"{year} NBA Playoffs" (12px, accent light) and the H2 "Bracket" at `clamp(44px, 5vw, 72px)`. On the right, the helper text "Tap a series for the result. Tap it again to open the full series." (14px, muted).

### Desktop map (1180px and wider)

- **Seven columns**, left to right: East R1, East Semis, East Finals, NBA Finals, West Finals, West Semis, West R1. Tracks `repeat(3, minmax(0, 1fr)) minmax(0, 1.25fr) repeat(3, minmax(0, 1fr))`, gap 14px.
- **Column title:** 11px, uppercase, centered, with a bottom divider; the Finals title in accent light, the others muted.
- **Cards** spread with `justify-content: space-around` in a column whose height is set by the four first-round cards (no minimum height), so each later round sits between its two feeders and the whole bracket, its titles and its heading fit in one 1280x720 screen.
- **Series card:** a 1px border at ink 16%, background ground at 88%, padding `6px 12px`. Two team rows: the seed (11px, muted, right-aligned, 14px column), the logo 22px, the code 17px and the wins right-aligned in a 20px column. Under each row, 4 segments 3px tall with a 3px gap, filled in the team's resolved color (one per win) and empty at ink 12%. The eliminated team's row is at 50% opacity. Hover: accent border. Selected: background accent at 12% and an accent border.
- **Finals card:** padding `6px 14px`, a border of accent light at 45%, logo 30px, code 22px, wins 30px. No trophy and no extra height.

### Undecided series

- A dashed card with the slot label: "East #1 seed", "Winner of East R1 1", "Winner of East semifinal 1", "East play-in winner". During the regular season, a "Currently XXX" line from the standings seeds. They are not selectable.
- A series with one side decided shows that side and a dashed row for the other.
- The bracket always shows its 15 series and 16 slots, with or without data.

### Under 1180px: the vertical tree

No zoom and no sideways scroll at any width.

- **Seven rows** in the same order, each with a 9.5px centered label (NBA Finals in accent light), each an 8-column grid with a 4px gap. Cards span 2 columns: R1 at `1/3`, `3/5`, `5/7`, `7/9`; semifinals at `2/4` and `6/8`; the conference finals at `4/6`; the NBA Finals at `3/7`.
- **Card:** padding 5px; seed 8.5px, logo 14px, code 12px, wins 13px; segments 2px tall with a 2px gap. The Finals card: padding `6px 10px`, logo 20px, code 16px, wins 18px.

### Interaction

- The first tap selects a series. A second tap on the selected series, when it is complete, opens the full series page (`/playoffs/series`); an unfinished series stays selected.
- **Desktop:** the result panel shows below the bracket. The Finals series is selected by default once it has a game; before that nothing is selected and the panel is hidden.
- **Under 1180px:** the first tap opens the bottom sheet (`SeriesSheet`), which keeps its slide, scrim, Esc, body scroll lock and 86vh cap, and is styled: panel background `--playoffs-sheet-bg` (`#11161b`), a 1px accent top border, the winner logo at 36px, the round label, the headline at 24px, a 44px close button, the games in a 4-column grid and a full-width 48px accent button "Full series →".

### Result panel and sheet content

- A `BlueprintFrame` with 4 corner marks. **Top row:** the winner logo at 48px; the round label (11px, uppercase, muted) above the headline "{CODE} wins 4–2" or "{CODE} leads 3–2" (32px, uppercase); the other team's logo at 30px and 60% opacity. On the right, the accent button "Full series →" (accent background, ground text, 16px, uppercase; hover accent light) to the full series page. The wins and the winner come from the feed and are never counted by `/web`.
- **Games grid** `repeat(auto-fill, minmax(130px, 1fr))`, gap 10px. Each cell shows "G{n}", "at {HOME}", the OT tag in accent light ("OT", "2OT", from the game's `overtimePeriods`), the winner logo at 20px and "{CODE} {ws}–{ls}", and a 2px line in the winner's resolved color. A cell links to the game page when `detailAvailable`. A game that is not scheduled is not listed.

### Play-in

- Below the bracket: the H3 "Play-in". East and West side by side in `minmax(min(100%, 520px), 1fr)`, three cards each (7th vs 8th, 9th vs 10th, the 8th seed game). Each card: the label, two rows with the logo, the code and the points (the loser at 50%), and the note ("PHI → No. 7" in accent light, "MIA out" muted).
- A slot that is not decided reads "To be decided" with the regular season place ("Loser of 7th vs 8th", "Winner of 9th vs 10th"), as before. The slots fill as each game is final.
- It keeps its rule on which states show it: the strip appears in the `picture` and `playin` states; in later states it stays below the bracket as a record, collapsed to the outcomes.

### Out of this design

Zoom levels, pinch and rosters inside the bracket.

## Full series

A new page at `/playoffs/series?id={SeriesId}`, browser-rendered like `/playoffs` (`ssr = false`, the fallback page of `docs/deploy.md`). It keeps the `season` query parameter as `/playoffs` does and reads the same playoffs feed (for the Finals also the Finals feed, for the leaders). Designed at 390px; on wider screens the same layout is centered with a max-width of 720px. Component: `SeriesPage`.

- **Top bar:** "← Bracket" (back to `/playoffs`, same season, scrolled to the bracket) and "{year} NBA Playoffs" (10px, uppercase, muted).
- **Hero:** two glows in each team's resolved color at 22%, left and right; the round label (10px, accent light); a three-column row: the team (72px logo, code 20px, "No. {seed} seed" 10px muted, a 32x3 bar in its color), the score in the middle (72px, the leader in ink, the other muted), and the other team. The losing team is at 60% when the series is complete. The status line "{CODE} wins the series 4–1" or "{CODE} leads 3–2" (14px) and the dates of the first and last game (12px, muted).
- **"Game by game"** (H3, 24px): one card per game played or scheduled, linking to its game page when `detailAvailable`. The card: "Game {n}" (16px); "{date} · {venue}" (12px, muted; "at {HOME}" when the venue is null); the OT tag in accent light; a chevron. Two columns, each with the logo at 22px, the code at 16px and the points at 24px (the loser at 50%). For the Finals only, a leader line from the Finals feed ("{name} {pts} PTS · {name} {pts} PTS", 12px, muted). A 2px line in the winner's color.
- **Not available:** an unknown or undecided series id shows the existing "not available" message row with the back link.

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
| Series not started | The card shows the seeds and codes with wins `0` (or `—` when the feed has none) and empty segments; the result panel and the sheet list no games, or the scheduled ones only |
| Full series id unknown or undecided | The existing "not available" message row with the back link to the bracket |
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
| Polling | Playoffs and finals feeds every 5 minutes once the playoffs feed's `state` is `complete`, every 60 seconds otherwise; paused while the tab is hidden and refreshed when it is visible again |
| Series card | First tap selects (desktop: the result panel shows below; under 1180px: the sheet opens); a second tap on a complete selected series opens `/playoffs/series` |
| Hero game strip | One link that scrolls to the Finals series section |
| Game tabs | Select the game; the active tab has an accent bottom rule |
| Leader tabs | Switch the category |
| Head to head tabs | Switch the finalist in the averages table |
| Series sheet (under 1180px) | `translateY` over 0.5s, 60% scrim, body scroll locked, Esc and a tap on the scrim close it; none of the slide under reduced motion |
| Focus | `:focus-visible` as on the home |

## Responsive

- Under 680px: the nav is one row with the menu button, the stage strip is 2x2 plus one cell, the hero is compact (logo 230px above the H1, 72px H1), the game tabs and the award cards are snap scrollers (132px and 156px), the leader tabs are chips, the Finals MVP section is one column under 900px and its MVP card stacks the photo above the info panel, and the bracket is the vertical tree with a bottom sheet under 1180px, with no zoom and no sideways scroll. The full series page is designed at 390px and centered at 720px on wider screens.
- Tables scroll horizontally with a sticky first column.

## New tokens

To add to `web/src/lib/styles/tokens.css` in the implementing issue. Values not listed map to existing tokens.

| Token (suggested) | Value | Use |
|---|---|---|
| `--playoffs-title-size` | `clamp(56px, 9vw, 128px)` | H1 |
| `--playoffs-hero-title-size` | `clamp(72px, 10.5vw, 156px)` | Hero H1 (72px on mobile) |
| `--playoffs-hero-grid-size` | 88px | Hero grid background (44px on mobile) |
| `--playoffs-hero-grid-alpha` | .035 | Hero grid ink opacity |
| `--playoffs-hero-glow-alpha` | .32 | Hero, MVP photo panel glow of the team color |
| `--playoffs-hero-logo-size` | 520px | Hero logo, up to (230px on mobile) |
| `--playoffs-hero-strip-score-size` | `clamp(20px, 2.4vw, 28px)` | Hero game strip score (18px on mobile) |
| `--playoffs-hero-strip-rule` | ink at 18% | Hero game strip top border |
| `--playoffs-trophy-stroke` | 1.5px | Hero trophy line |
| `--playoffs-mvp-title-size` | `clamp(32px, 3.4vw, 44px)` | Finals MVP H2 |
| `--playoffs-mvp-photo-columns-mobile` | `minmax(0, 1fr)` | Finals MVP card inner grid under 680px |
| `--playoffs-mvp-photo-width` | 300px | Finals MVP cutout (170px for a conference MVP) |
| `--playoffs-conf-glow-alpha` | .35 | Conference MVP photo glow |
| `--playoffs-bracket-title-size` | `clamp(44px, 5vw, 72px)` | Bracket H2 |
| `--playoffs-bracket-break` | 1180px | Desktop map / vertical tree switch |
| `--playoffs-bracket-columns` | `repeat(3, minmax(0, 1fr)) minmax(0, 1.25fr) repeat(3, minmax(0, 1fr))` | Desktop map tracks |
| `--playoffs-bracket-gap` | 14px | Desktop map gap (4px in the vertical tree) |
| `--playoffs-card-border` | ink at 16% | Series card border |
| `--playoffs-card-bg` | ground at 88% | Series card background |
| `--playoffs-finals-card-border` | accent light at 45% | Finals card border |
| `--playoffs-selected-bg` | accent at 12% | Selected series card |
| `--playoffs-segment-height` | 3px | Wins segment (2px in the vertical tree) |
| `--playoffs-segment-empty` | ink at 12% | Empty wins segment |
| `--playoffs-sheet-bg` | `#11161b` | Series sheet panel |
| `--playoffs-sheet-button-height` | 48px | "Full series" button in the sheet |
| `--playoffs-sheet-close-size` | 44px | Sheet close button |
| `--playoffs-games-min` | 130px | Result panel game cell min width |
| `--playoffs-series-max-width` | 720px | Full series page on wide screens |
| `--playoffs-series-score-size` | 72px | Full series hero score |
| `--playoffs-series-glow-alpha` | .22 | Full series hero glows |
| `--playoffs-series-logo-size` | 72px | Full series hero logo |
| `--playoffs-hero-title-leading` | .82 | Hero H1 line height |
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
| `--playoffs-sheet-duration` | 0.5s | Mobile sheet |
| `--playoffs-sheet-max-height` | 86vh | Mobile sheet |
| `--playoffs-sheet-scrim` | `rgba(0, 0, 0, .6)` | Mobile sheet scrim |

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
| `playoffs_hero_label` | {year} NBA Champions | Campeones de la NBA {year} |
| `playoffs_hero_subline` | Won the series {won}–{lost} over {opponent} · {dates} | Ganó la serie {won}–{lost} ante {opponent} · {dates} |
| `playoffs_hero_strip` | Finals game scores | Resultados de las Finales |
| `playoffs_ecf_mvp` | East Finals MVP | MVP de la final del Este |
| `playoffs_wcf_mvp` | West Finals MVP | MVP de la final del Oeste |
| `playoffs_bracket_kicker` | {year} NBA Playoffs | Playoffs de la NBA {year} |
| `playoffs_bracket_help` | Tap a series for the result. Tap it again to open the full series. | Toca una serie para ver el resultado. Tócala otra vez para abrir la serie completa. |
| `playoffs_col_east_r1` | East R1 | 1.ª ronda Este |
| `playoffs_col_east_semis` | East Semis | Semis Este |
| `playoffs_col_east_finals` | East Finals | Final Este |
| `playoffs_col_nba_finals` | NBA Finals | Finales de la NBA |
| `playoffs_col_west_finals` | West Finals | Final Oeste |
| `playoffs_col_west_semis` | West Semis | Semis Oeste |
| `playoffs_col_west_r1` | West R1 | 1.ª ronda Oeste |
| `playoffs_result_wins` | {team} wins {won}–{lost} | {team} gana {won}–{lost} |
| `playoffs_result_leads` | {team} leads {leading}–{trailing} | {team} lidera {leading}–{trailing} |
| `playoffs_full_series` | Full series → | Serie completa → |
| `playoffs_game_at` | at {team} | en {team} |
| `playoffs_game_n` | G{n} | P{n} |
| `playoffs_ot_n` | {n}OT | {n}TE |
| `playoffs_sheet_close` | Close | Cerrar |
| `playoffs_playin_heading` | Play-in | Play-in |
| `playoffs_series_back` | ← Bracket | ← Cuadro |
| `playoffs_series_seed` | No. {seed} seed | Cabeza de serie n.º {seed} |
| `playoffs_series_status_wins` | {team} wins the series {won}–{lost} | {team} gana la serie {won}–{lost} |
| `playoffs_series_status_leads` | {team} leads {leading}–{trailing} | {team} lidera {leading}–{trailing} |
| `playoffs_series_by_game` | Game by game | Partido a partido |
| `playoffs_series_game` | Game {n} | Partido {n} |
| `playoffs_series_game_venue` | {date} · {venue} | {date} · {venue} |
| `playoffs_series_leaders` | {name} {pts} PTS · {name2} {pts2} PTS | {name} {pts} PTS · {name2} {pts2} PTS |
| `playoffs_series_unavailable` | This series isn't available. | Esta serie no está disponible. |
| `playoffs_finals_mvp` | Finals MVP | MVP de las Finales |
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
| `playoffs_champion` | Champion | Campeón |
| `playoffs_tbd_slot` | To be decided | Por decidir |
| `playoffs_currently` | Currently {team} | Actualmente {team} |
| `playoffs_slot_seed` | {conference} #{seed} seed | {conference} · cabeza de serie {seed} |
| `playoffs_slot_r1_winner` | Winner of {conference} R1 {n} | Ganador de la ronda 1 {n} del {conference} |
| `playoffs_slot_r2_winner` | Winner of {conference} semifinal {n} | Ganador de la semifinal {n} del {conference} |
| `playoffs_slot_r3_winner` | Winner of {conference} finals | Ganador de la final del {conference} |
| `playoffs_slot_playin_winner` | {conference} play-in winner | Ganador del play-in del {conference} |
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
