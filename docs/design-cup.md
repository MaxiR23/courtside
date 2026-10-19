# Design: NBA Cup

The visual, interaction and data specification of the NBA Cup page (`/cup`), the Cup link in the nav, the bracket (levels 1 and 2), the matchup panel and sheet, the player card, the Cup games list and the Cup marks on the home card, the game page header and the team page header. It extends `docs/design.md`, `docs/design-standings-search.md` and `docs/design-profiles.md`: every token, rule and shared component defined there applies here, and only new values are listed under "New tokens".

## Overview

| Page | Route | Feeds |
|---|---|---|
| Cup | `/cup` | `/feeds/cup.json`, `/feeds/cup/matchups/{id}.json` |

- Current season only. The page exists from the draw on. When the groups have no teams yet it shows "Groups not drawn yet".
- The Cup has six groups (East Group A to C, West Group A to C) of five teams, 60 group games, and a knockout: two quarterfinals per conference, one semifinal per conference and the Championship.
- The page is rendered in the browser from a fallback page, as the other pages are.
- Stage, in order: `draw` (no table rows), `group` (rows, and no knockout game scheduled or none final), `quarterfinals`, `semifinals`, `championship`, `complete` (the Championship is final). The dates of each stage come from the scheduled games; a stage without games has no dates and reads "TBD".

## Implementation rules

Everything under "Implementation rules" in `docs/design.md`, `docs/design-standings-search.md` and `docs/design-profiles.md` applies, plus:

- **`/web` computes nothing.** Stage, stage dates, stage status, clinch tags, positions, games behind, differentials, "Currently ..." lines, projected pairings, starters, stat leaders, winners, progress counts ("N of 60 games played"), chip counts and group meta all come ready from the feeds. Slot labels and rules are the exception: the feed sends them as keys and parts (conference, letter, seed), never prose (`docs/api/cup.md`, Conventions), and the page writes the words.
- **Nothing is hardcoded in `/web`:** no venue, broadcast, date, team or group. No data source name, video platform or URL is written in `/web`.
- **Every user-facing string is translatable**, in English and Spanish. Long labels truncate with an ellipsis and never wrap in a table cell.
- **A value that is missing renders `—`.**
- **No Cup-only player averages** anywhere. Averages are the season averages.
- **Pan and zoom of the bracket only write `style.transform`.**
- **Shared components are reused:** nav row, `TeamMonogram`, `StatusTag`, `Kicker`, `BlueprintFrame`, `ClinchTag`, `StandingsTable` patterns, `NextGameCard` link pattern, the loading skeletons and the footer. A game row links to `/game/{id}` only when the game exists.

### New components

| Component | What it is |
|---|---|
| `CupHeader` | Season tag, state line, h1, champion block and stage strip |
| `StageStrip` | The four stage columns with dates and status |
| `GroupCard` | One group: title, meta, draw list or table, "More columns" toggle |
| `GroupTable` | The group table with tags |
| `WildCardTable` | One conference table of non-winners with the wild card line |
| `CupBracket` | The camera, the world, connectors, level switcher, controls and hint |
| `BracketNode` | One matchup node at level 1 and level 2 |
| `MatchupPanel` | Side panel (desktop) and full-screen sheet (mobile) |
| `MatchupTeamBlock` | Path and Roster blocks of one team |
| `PlayerCard` | The player card panel |
| `CupGames` | Filter chips and the date-grouped list |
| `CupGameRow` | One Cup game row |
| `CupMarkTag` | The `NBA Cup · {stage}` tag |
| `CupTeamLine` | The `{group} · {W}-{L}` line on the team page header, linking to /cup |

## Shared patterns

- Ground, ink, muted, accent, accent text, divider and row rules are the existing tokens. Headings Barlow Condensed 600, body Barlow, numbers `font-variant-numeric: tabular-nums`.
- Content max width 1320px, side padding `clamp(20px, 4vw, 48px)`, section gap `clamp(64px, 8vw, 104px)`, `scroll-margin-top: 72px`. Section header: h2 `clamp(28px, 3.4vw, 40px)`, uppercase, optional meta right.
- Tags: accent outline, 11px, .16em, uppercase, accent text (`StatusTag`).
- The 680px break is `--game-row-breakpoint`.

## Nav

- Links: Games · Standings · Cup, then the search trigger. Same rules as the standings page: two rows below 680px. Cup is active on `/cup`.

## Header

- Season tag (accent outline) and a state line: "Groups drawn · Play starts {date}" / "Group play · N of 60 games played" / "Quarterfinals" / "Semifinals" / "Championship" / "Complete". All text comes from the feed values.
- H1 "NBA Cup", `clamp(56px, 9vw, 128px)`.
- When complete, a champion block on the right: 52px monogram with accent border, "Champion", the full team name, linking to the team.
- **Stage strip**, 4 columns: Group play · Quarterfinals · Semifinals · Championship, each with its dates (or "TBD") and a status: Complete / In progress / Next / Upcoming. The current stage has a 2px accent top rule, a completed one 1px accent, the others a divider. 2x2 below 680px.
- **Section order:** draw and group stages: Groups, Wild card, Bracket, Games. Knockout stages: Bracket, Groups, Wild card, Games.

## Groups

- Six cards, `repeat(auto-fill, minmax(380px, 1fr))`, titled "East Group A" ... "West Group C". Meta on the right: "5 teams" / "N of 10 games" / "Final".
- **Draw:** the five teams (32px monogram, muted city and name), no numbers.
- **Played:** table Pos · Team (+ tag) · W-L · GB · Diff/G · Diff · Strk. A "More columns" toggle adds PF · PA · Home · Away · OT and widens the cards to 560px.
- **Tags** (from the feed only): `y` "Won group" and `x` "Wild card" have accent border and text. `e` "Eliminated" has a divider border and muted text, and the whole row is muted. A legend sits under the grid.
- Missing values render `—`. Team names truncate, never wrap.
- Rows are listed by position; a row without a position goes last, in feed order (a past season's groups included).

## Wild card

- One table per conference with the non-winners in conference order: Rank · Team · Group · W-L · Diff · PF.
- A dashed accent "Wild card line" under rank 1. The `x` tag shows when the feed has it.

## Bracket

Levels 1 and 2 only.

### World (desktop, 680px and wider)

- World 6300x1320, nodes 1100x560. Left to right: East QF (x 0, y 0 and 760), East SF (x 1300, y 380), Championship (x 2600, y 380), West SF (x 3900, y 380), West QF (x 5200, y 0 and 760). West rows are mirrored.
- Orthogonal SVG connectors with `vector-effect: non-scaling-stroke`: accent 1.5px when the feeder's winner is known, `rgba(235, 232, 227, .22)` 1px otherwise.
- Node background `#0f1215`, 1px border and accent corner ticks; the final has an accent border. Borders scale with 1/zoom.

### Camera

- One layer with translate and scale, `transform-origin: 0 0`.
- Wheel zooms around the cursor; trackpad scroll pans; ctrl+wheel zooms; drag pans with a 6px threshold. At fit, vertical scroll goes to the page.
- Zoom range: 0.75x fit to 4x.
- Controls: level switcher top-left (1 Bracket · 2 Round), + / - / fit top-right, hint line bottom-left.
- Fly animation 560ms, cubic in-out, zoom interpolated in log space.

### Levels

- **Level 1** (k < .36, k being the zoom): team codes at 150px and a score per slot; round labels above each column; the champion name under the final.
- **Level 2** (k >= .36): monogram tile, team name, "seed · group · record", score, venue, a "Neutral site" tag (semifinals and final), broadcast.
- **Undecided slot:** dashed tile, "To be decided", the rule text and, during group play, the "Currently XXX (W-L)" line.
- Slots before a game is scheduled show a label the page writes from the feed's keys and parts ("East #1 seed", "East wild card", "Winner of East QF 1") and the rule text. During group play the feed adds "Currently XXX (W-L)" from the conference table order. Seeds 1 to 3 are the group winners in conference order, the wild card is the fourth; pairings are seed 1 vs wild card and seed 2 vs seed 3. Once the game is scheduled, the game's own teams, date, venue and broadcast replace the projection.
- Click on a node opens the matchup panel.

### Mobile (under 680px)

- Vertical world 2400x3600: East QFs on top, East SF, Final, West SF, West QFs at the bottom.
- Fit shows the whole bracket at level 1 in a viewport of `min(70vh, 620px)`. No zoom controls. Tap opens the sheet. The page scrolls normally.

### Out of this design

Continuous zoom levels 3 and 4, pinch-to-enter and the ghost layer.

## Matchup panel

- Desktop: a 480px side panel fixed to the right edge of the browser window, full height. Mobile: a full-screen sheet.
- Header: round, date, venue, broadcast, "Neutral site" tag and, when the game exists, "Game page →".
- Both teams with scores and status (Final, Final/OT, vs).
- Per team, two blocks:
  - **Path:** every Cup game with W/L, opponent and score, each linking to its game page; then injuries.
  - **Roster:** 15 rows: number, name, position or injury code, PTS, REB, AST. Season averages from the existing averages adapter. A "Starting five" mark on the five rank-1 players of the depth chart, current season only; if a player is rank 1 in two positions or one is missing, only the existing ones are marked, never a fifth invented. A team without depth chart has no mark. The leader of each stat is shown in accent; the backend marks it.
- The Championship carries: "The Championship game does not count toward the regular-season record."
- Clicking a roster row opens the player card.
- Close with Esc or the close button.

## Player card

- Desktop: a 340px panel fixed to the left edge of the browser window, full height, opposite the matchup panel. Mobile: full screen.
- Content: photo (initials when missing), name, team, number, position, injury, season averages (PTS, REB, AST), height, weight, age, hometown, college, experience, and a link to the player page. No Cup-only averages.
- Previous / next buttons step through the roster of the team. Esc or the close button closes the card.

## Cup games

- Filter chips with counts: All · Group play · Quarterfinals · Semifinals · Championship.
- Grouped by date. Row: stage label · away (color bar, code, score) @ home · status or time · broadcast. Losers are muted.
- Undecided knockout games show their slot labels. The Championship row carries a "Not counted in standings" tag.
- Every scheduled row links to its game page. Single column below 680px.

## Cup marks elsewhere

Three small marks carry the Cup into pages that already exist. `/web` computes nothing for them: the stage, the group and the Cup record come from the feeds and the page only writes the words, and a mark whose field is absent is not drawn.

### Home game card

- A Cup game shows the tag `NBA Cup · {stage}` first in the card's center column, above the status line (first in the status line on the mobile row), using the existing `StatusTag` styling (accent outline, uppercase, 11px, .16em letter spacing, accent text). `{stage}` is `Group play`, `Quarterfinal`, `Semifinal` or `Championship`, the words for the contract values `group`, `quarterfinals`, `semifinals` and `championship`.
- A game that is not a Cup game shows no tag.
- The tag is plain text: it does not link and has no hover state. It truncates with an ellipsis and never wraps.

### Game page header

- The same tag, `NBA Cup · {stage}`, sits in the header's kicker line (the status line above the teams), as its first item, before the date and venue, with the same styling and truncation as on the home card.
- A non-Cup game shows no tag.

### Team page header

- During the current Cup, a line under the conference and division line reads `{group} · {W}-{L}`, for example `East Group A · 3-1`. The group name is written from the feed's parts as on `/cup` (`cup_group_name`, such as East Group A) and the record is the team's Cup record.
- Style: 13px, muted, tabular numbers; the group name in accent text. The line sits between the name block and the record, and wraps only at spaces.
- Outside the current Cup, and for a team with no group, the line is not drawn and the cells around it keep their order.
- The Cup record is the team's record in group play. The Championship game is not counted in it.
- The line links to `/cup`; it is not nested inside another link.

### Strings

| Key | English | Spanish |
|---|---|---|
| `cup_mark_tag` | `NBA Cup · {stage}` | `Copa NBA · {stage}` |
| `cup_stage_group` (existing) | Group play | Fase de grupos |
| `cup_stage_quarterfinal` | Quarterfinal | Cuartos de final |
| `cup_stage_semifinal` | Semifinal | Semifinal |
| `cup_state_final` (existing) | Championship | Final |
| `cup_group_name` (existing) | `{conference} Group {letter}` | `Grupo {letter} del {conference}` |

The line joins the group and the record with " · " in markup. The feed sends the stage as a value and the group as parts (conference, letter); the page writes the words with the keys above.

### Feed contract

- Game cards (home feed, game detail feed): a nullable `cup` object, `null` for a game that is not a Cup game, with `stage: CupRound` (`group`, `quarterfinals`, `semifinals`, `championship`).
- Team feed: a nullable `cup` object, `null` outside the current Cup or when the team has no group, with `group: CupGroupName` (`conference`: `east` or `west`, `letter`: `A`, `B` or `C`), `wins` and `losses`, as set in `docs/api/cup.md`.

## Edge cases

| Case | What shows |
|---|---|
| Groups not drawn | "Groups not drawn yet" in place of the groups; the header still shows |
| Draw without table rows | The five teams per group, monogram and name, no numbers |
| Partial group play | Tables with the rows the feed has; meta "N of 10 games"; progress "N of 60 games played" |
| Missing values | `—` in that cell |
| No clinch | No tag; the team name sits where the tag would start |
| Knockout games not scheduled | Dates read "TBD"; nodes show slot labels, rule text and, in group play, the "Currently" line |
| Championship not counted in the regular-season record | The note in the matchup panel and the "Not counted in standings" tag on its row |
| Team without depth chart | No "Starting five" mark |
| Player without photo | Initials in the photo tile |
| Unavailable feed | The nav row, then the home's 503 state: "Data isn't available right now. Check back later." |
| Spanish strings | Every string has a Spanish text; long labels truncate, never wrap in a table cell |

## States

| State | What shows |
|---|---|
| Loading | Skeletons shaped like the header and the first section, with the home's shimmer, stopped under reduced motion |
| Feed unavailable | See Edge cases; polling continues and the page fills in when a request succeeds |
| Matchup feed unavailable | The panel shows the same unavailable line; the bracket stays |
| Draw / group / knockout / complete | Per the stage rules in Overview and Header |

## Interactions and motion

| What | How |
|---|---|
| Polling | Cup page every 5 minutes once the feed's `stage` is `complete`, every 60 seconds otherwise; an open matchup panel every 60 seconds; paused while the tab is hidden and refreshed when it is visible again |
| Bracket camera | See Bracket: wheel, trackpad, ctrl+wheel, drag with 6px threshold |
| Fly animation | 560ms cubic in-out, log-interpolated zoom; none under reduced motion |
| Node click / tap | Opens the matchup panel or sheet |
| Roster row | Opens the player card; previous / next; Esc or close button closes |
| "More columns" | Toggles the extra group columns |
| Chips | Filter the Cup games; the selection is not kept between visits |
| Focus | `:focus-visible` as on the home |

## Responsive

- Under 680px: the nav is two rows, the stage strip is 2x2, the bracket uses the vertical world without zoom controls, the matchup panel and player card are full-screen sheets, and the Cup games list is a single column.
- Group cards reflow through their auto-fill grid; tables scroll horizontally with a sticky first column.

## New tokens

To add to `web/src/lib/styles/tokens.css` in the implementing issue. Values not listed map to existing tokens.

| Token (suggested) | Value | Use |
|---|---|---|
| `--cup-title-size` | `clamp(56px, 9vw, 128px)` | H1 |
| `--cup-champion-mark` | 52px | Champion monogram |
| `--cup-stage-rule-current` | 2px | Current stage rule |
| `--cup-stage-rule-done` | 1px | Completed stage rule |
| `--cup-group-min` | 380px | Group card min width |
| `--cup-group-wide` | 560px | Group card with more columns |
| `--cup-group-mark` | 32px | Draw monogram |
| `--bracket-world-width` | 6300px | Desktop world |
| `--bracket-world-height` | 1320px | Desktop world |
| `--bracket-node-width` | 1100px | Node |
| `--bracket-node-height` | 560px | Node |
| `--bracket-mobile-width` | 2400px | Mobile world |
| `--bracket-mobile-height` | 3600px | Mobile world |
| `--bracket-node-bg` | `#0f1215` | Node background |
| `--bracket-line-known-color` | accent (`var(--color-accent)`) | Connector with known winner |
| `--bracket-line-known-width` | 1.5px | Connector with known winner |
| `--bracket-line-open-color` | `rgba(235, 232, 227, .22)` | Other connectors |
| `--bracket-line-open-width` | 1px | Other connectors |
| `--bracket-level-threshold` | .36 | Level 1 / 2 switch |
| `--bracket-code-size` | 150px | Level 1 team code |
| `--bracket-zoom-min` | .75 (of fit) | Zoom floor |
| `--bracket-zoom-max` | 4 | Zoom ceiling |
| `--bracket-drag-threshold` | 6px | Drag threshold |
| `--bracket-fly-duration` | 560ms | Fly animation |
| `--bracket-mobile-viewport` | `min(70vh, 620px)` | Mobile viewport |
| `--cup-panel-width` | 480px | Matchup panel |
| `--cup-card-width` | 340px | Player card |
| `--bracket-viewport-height` | `clamp(360px, 36vw, 560px)` | Desktop bracket viewport height |
| `--bracket-node-padding` | 56px | Node inner padding (world units) |
| `--bracket-tile-size` | 120px | Level 2 team tile |
| `--bracket-name-size` | 64px | Level 2 team name |
| `--bracket-meta-size` | 36px | Level 2 meta line |
| `--bracket-score-size` | 110px | Score |
| `--bracket-label-size` | 64px | Undecided slot label |
| `--bracket-round-label-size` | 56px | Round label |
| `--bracket-champion-size` | 72px | Champion name |
| `--bracket-tick-size` | 40px | Node corner ticks |
| `--bracket-focus-width` | 2px | Node focus frame |
| `--cup-panel-z-index` | 2 | Matchup panel and player card layer |
| `--cup-card-photo-size` | 96px | Player card photo |

Mapped to existing tokens: the divider is `--color-divider`; accent text is `--color-accent-light`; label size and spacing are `--label-size` and `--label-letter-spacing`; the 680px break is `--game-row-breakpoint`.

## Strings

| Key (suggested) | English | Spanish |
|---|---|---|
| `nav_cup` | Cup | Copa |
| `cup_title` | NBA Cup | Copa NBA |
| `cup_not_drawn` | Groups not drawn yet | Grupos aún sin sortear |
| `cup_state_draw` | Groups drawn · Play starts {date} | Grupos sorteados · Comienza el {date} |
| `cup_state_group` | Group play · {n} of 60 games played | Fase de grupos · {n} de 60 partidos jugados |
| `cup_state_qf` | Quarterfinals | Cuartos de final |
| `cup_state_sf` | Semifinals | Semifinales |
| `cup_state_final` | Championship | Final |
| `cup_state_complete` | Complete | Completa |
| `cup_champion` | Champion | Campeón |
| `cup_stage_group` | Group play | Fase de grupos |
| `cup_tbd` | TBD | Por definir |
| `cup_status_complete` | Complete | Completa |
| `cup_status_in_progress` | In progress | En curso |
| `cup_status_next` | Next | Siguiente |
| `cup_status_upcoming` | Upcoming | Próximamente |
| `cup_group_teams` | {n} teams | {n} equipos |
| `cup_group_games` | {n} of 10 games | {n} de 10 partidos |
| `cup_group_final` | Final | Final |
| `cup_more_columns` | More columns | Más columnas |
| `cup_tag_y` | Won group | Ganó el grupo |
| `cup_tag_x` | Wild card | Comodín |
| `cup_tag_e` | Eliminated | Eliminado |
| `cup_wild_card` | Wild card | Comodín |
| `cup_wild_card_line` | Wild card line | Línea del comodín |
| `cup_col_pos` | Pos | Pos |
| `cup_col_team` | Team | Equipo |
| `cup_col_group` | Group | Grupo |
| `cup_col_rank` | Rank | Rango |
| `cup_bracket` | Bracket | Cuadro |
| `cup_level_1` | Bracket | Cuadro |
| `cup_level_2` | Round | Ronda |
| `cup_zoom_in` | Zoom in | Acercar |
| `cup_zoom_out` | Zoom out | Alejar |
| `cup_zoom_fit` | Fit | Ajustar |
| `cup_hint` | Scroll to zoom, drag to pan | Desplaza para ampliar, arrastra para mover |
| `cup_tbd_slot` | To be decided | Por decidir |
| `cup_currently` | Currently {team} ({w}-{l}) | Actualmente {team} ({w}-{l}) |
| `cup_neutral` | Neutral site | Sede neutral |
| `cup_game_page` | Game page → | Página del partido → |
| `cup_final` | Final | Final |
| `cup_final_ot` | Final/OT | Final/TE |
| `cup_vs` | vs | vs |
| `cup_path` | Path | Recorrido |
| `cup_roster` | Roster | Plantilla |
| `cup_starting_five` | Starting five | Quinteto inicial |
| `cup_final_note` | The Championship game does not count toward the regular-season record. | El partido de la Final no cuenta para el récord de temporada regular. |
| `cup_not_counted` | Not counted in standings | No cuenta en la clasificación |
| `cup_player_prev` | Previous player | Jugador anterior |
| `cup_player_next` | Next player | Jugador siguiente |
| `cup_player_page` | Player page | Página del jugador |
| `cup_close` | Close | Cerrar |
| `cup_filter_all` | All | Todos |
| `cup_filter_group` | Group play | Fase de grupos |
| `cup_filter_qf` | Quarterfinals | Cuartos de final |
| `cup_filter_sf` | Semifinals | Semifinales |
| `cup_filter_final` | Championship | Final |
| `cup_unavailable` | Data isn't available right now. Check back later. | Los datos no están disponibles ahora. Vuelve más tarde. |
| `cup_slot_seed` | {conference} #{seed} seed | {conference} · preclasificado {seed} |
| `cup_slot_wild_card` | {conference} wild card | Comodín del {conference} |
| `cup_slot_qf_winner` | Winner of {conference} QF {n} | Ganador de cuartos {n} del {conference} |
| `cup_slot_sf_winner` | Winner of {conference} SF | Ganador de la semifinal del {conference} |
| `cup_rule_best_group_winner` | Best group winner | Mejor ganador de grupo |
| `cup_rule_second_best_group_winner` | Second-best group winner | Segundo mejor ganador de grupo |
| `cup_rule_third_best_group_winner` | Third-best group winner | Tercer mejor ganador de grupo |
| `cup_rule_best_non_winner` | Best team that did not win its group | Mejor equipo que no ganó su grupo |
| `cup_rule_quarterfinal_winner` | Advances from the quarterfinal | Avanza desde cuartos de final |
| `cup_rule_semifinal_winner` | Advances from the semifinal | Avanza desde la semifinal |
| `cup_side_seed` | #{seed} seed | Preclasificado {seed} |
| `cup_card_hometown` | Hometown | Ciudad natal |
| `cup_card_experience` | Experience | Experiencia |
| `cup_matchup_loading` | Loading matchup | Cargando el cruce |

"Currently" lines, group titles and stage dates are sent by the feed; slot labels and rules are sent as keys and parts and the page writes the words with the `cup_slot_*` and `cup_rule_*` keys above. The other keys are the fixed words around them. Strings for the Cup marks are in the section below.


## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601. Every value is computed by the backend; exact field names are set by `docs/api/cup.md` in the issue that adds the feed.

### Cup feed (`/feeds/cup.json`)

- Stage, state line values, progress count (games played of 60) and the four stage entries with dates and status.
- The six groups: title, teams, meta, and table rows with position, W-L, GB, Diff/G, Diff, streak, PF, PA, home, away, OT and tag (`y`, `x`, `e` or null).
- The two conference wild card tables with rank, group, W-L, Diff, PF and tag.
- The bracket: per conference the QFs, SFs and the Championship, each with slot labels, rule text, "Currently" line, teams, seed, group, record, scores, status, date, venue, broadcast, neutral flag, winner, game id when the game exists.
- The Cup games list: stage, date, away, home, scores, status or time, broadcast, winner, slot labels for undecided games, the not-counted flag and the stage counts for the chips.
- The champion when complete.

### Matchup feed (`/feeds/cup/matchups/{id}.json`)

- Both teams' Path (every Cup game with result, opponent, score and game id; injuries) and Roster (15 players with number, name, position, injury status, PTS, REB, AST, starter flag, stat leader flags) and the player card fields: photo, height, weight, age, hometown, college, experience, player id.

