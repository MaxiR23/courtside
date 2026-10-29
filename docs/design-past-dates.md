# Design: Past dates and seasons

The visual, interaction and data specification of browsing past dates and past seasons: the calendar sheet opened from the date label of the home, the day page (`/day/[date]`), the season selector on `/standings`, `/team/[code]` and `/player/[id]`, the season tag, the franchise "Names" timeline on the team page, and the past game page. It extends `docs/design.md`, `docs/design-cup.md` and `docs/design-playoffs.md`: every token, rule and shared component defined there applies here, and only new values are listed under "New tokens". The games feed, its 7-day window and its live behavior do not change. This document is the specification the next five issues of this feature implement; it adds no behavior beyond the decisions recorded here.

## Overview

| Page | Route | Feeds |
|---|---|---|
| Home (calendar sheet) | `/` | `/feeds/games.json`, `/feeds/seasons/{season}/calendar.json` |
| Day | `/day/[date]` | `/feeds/days/{date}.json`, `/feeds/seasons/{season}/calendar.json` |
| Game | `/game/[id]` (unchanged) | `/feeds/games/{id}.json` |
| Standings | `/standings?season=YYYY` | `/feeds/seasons/{season}/standings.json` |
| Team | `/team/[code]?season=YYYY` | `/feeds/seasons/{season}/teams/{code}.json` |
| Player | `/player/[id]?season=YYYY` | `/feeds/seasons/{season}/players/{id}.json` |

- A season is identified by its end year. The label is "1993-94", written as `season_label` writes it. The first season is 1994 (1993-94). The season feeds serve the seasons from 1994 to the season before the current one (`stars.current_season`), and the calendar feed serves the current one too; a season outside that range is a 404 (ADR 0043). The current season is served by the existing feeds.
- Full coverage (every game of the day with the final score, the four quarters and both box scores) starts with the 1993-94 season. Older seasons are partial or empty and are not offered. Plays exist from 2004 and win probability only in recent seasons, so a past game can lack them.
- Game dates are UTC; the day shown is the US Eastern day, as the games job already handles it (`eastern_date`). A day with no game is a valid day with an empty list of games.
- Without `?season`, a page shows the current season as today and uses the existing feeds. With `?season` equal to the current season the page also uses the existing feeds. For a past season it uses the season feeds.
- The page of a past season shows the data as it was that season: final records and the names of that season (a past team page has no roster, ADR 0059). It has no live element.
- All routes are rendered in the browser from the fallback page (ADR 0020, ADR 0021); `docs/deploy.md` lists `/day/*`.

## Implementation rules

Everything under "Implementation rules" in `docs/design.md`, `docs/design-cup.md` and `docs/design-playoffs.md` applies, plus:

- **`/web` computes nothing.** The days with games, the first and last day, which days are in the games feed window, the season label, the weekday, the franchise name runs, the "retired" flag, the record, the standing and every value shown come ready from a feed. The page writes the fixed words around them. The exceptions that stay: the month grid lays the days of a month out in weeks from the dates the calendar feed sends, and the previous and next day with games are looked up in that feed's `days`.
- **A value that is missing renders `—`. A block that is missing hides its section** and leaves no gap. A team or player stat the source does not send is a missing value (ADR 0055); a box score row with no player id is left out (ADR 0055); a cold past build is paced and a rate limit shows the unavailable state until its retry (ADR 0056).
- **Nothing is hardcoded in `/web`:** no team, season list, date or franchise name. No data source name, video platform or URL is written in `/web`.
- **Every user-facing string is translatable**, in English and Spanish. Long labels truncate with an ellipsis and never wrap in a table cell.
- **Today's colors and logos only.** There are no colors or logos of past eras. A historical side (the `historical` flag of the side: the season's name, city or abbreviation differs from today's) is drawn with the neutral monogram (the guest sigla box) showing the season's abbreviation (`seasonCode`), with no team color and no strip, and links to today's team (ADR 0054). A side that is not historical keeps its colors on a past season.
- **No live element on a past season:** no next game, no injuries, no live badge, no depth chart, no Cup block, no titles of the current season. The feed sends these blocks as `null`.
- **Web settings** (one per feed, with the placeholders in braces):

| Setting | Placeholders |
|---|---|
| `CALENDAR_FEED_URL` | `{season}` |
| `DAY_FEED_URL` | `{date}` |
| `SEASON_STANDINGS_FEED_URL` | `{season}` |
| `SEASON_TEAM_FEED_URL` | `{season}`, `{code}` |
| `SEASON_PLAYER_FEED_URL` | `{season}`, `{id}` |

- **Api settings** for the franchise names: `SEASON_TEAM_URL` (`{season}`, `{team_id}`) and `SEASON_ROSTER_URL` (`{season}`, `{team_id}`). The existing settings whose endpoint takes a season query parameter do not change; the adapter sends the parameter.
- **Shared components are reused:** nav row, `DayStrip`, `GameCard`, `TeamMonogram`, `StatusTag`, `Kicker`, `StandingsTable` patterns, `RosterTable`, `Schedule`, `GameLog`, `SeasonsTable`, `TeamLeaders`, `TeamHeader`, `PlayerHeader`, `StageStrip` patterns, `SeriesSheet` and the Cup sheet pattern, the loading skeletons and the footer.

### New components

| Component | What it is |
|---|---|
| `DateButton` | The date label of the home nav row as a button with a chevron; opens the calendar |
| `CalendarSheet` | The calendar panel (desktop) and bottom sheet (mobile) |
| `CalendarMonth` | The month row with arrows and the month grid |
| `SeasonSelect` | The season select styled as the filter chips; used in the sheet and in the page headers |
| `DayHeader` | The day page header: date, season label, weekday, previous and next day, calendar button |
| `DayPage` | The `/day/[date]` page |
| `SeasonTag` | The "Season 2004-05" tag in the page headers |
| `NamesTimeline` | The franchise "Names" timeline on the team page |

## Calendar and day page

### Date button and calendar sheet

- Home keeps the `DayStrip` of 7 days. The date label in the nav row becomes a button: 44px hit target (`--hit-target-size`), a 12px chevron in muted after the label. It opens the calendar sheet and sets `aria-expanded`.
- **Desktop:** a 360px panel anchored below the label, with the page's 1px divider border and the surface background (`--color-surface`, #14171a).
- **Mobile (under 680px):** a bottom sheet, the pattern of the Cup and playoffs sheets: `translateY` slide of 0.5s `cubic-bezier(.2, .7, .1, 1)`, a maximum height of 86vh, a 60% scrim, the body scroll locked. Esc and a tap on the scrim close it.
- **Sheet header:**
  - A season selector: a select styled as the existing filter chips (Barlow Condensed 600, 14px, .08em, uppercase, a 1px border of ink at 25%, 36px tall). It lists "1993-94" to the current season, newest first.
  - A month row: previous and next arrows (36px, outlined) and the month name (Barlow Condensed 600, 18px, uppercase). The months outside the season's first and last day are not navigable; the arrows are disabled at the ends of the season's months.
- **Month grid:** 7 columns; a row of weekday initials (12px, .1em, muted); day cells of 40px (36px on mobile) with the day number in Barlow Condensed 600, 16px.
  - A day with games: ink text and a 4px accent square under the number. It is a link.
  - A day without games: ink at 30%, not clickable, not focusable.
  - Today: a 1px outline in accent light.
  - The selected day: accent fill with ground text.
- **Where a day goes:** a day inside the games feed window links to `/` with that day selected in the `DayStrip`, from the home and from the day page, and the day feed is not requested for it; any other day links to `/day/{date}`. The home sends a `?day=` of a past day outside its window to `/day/{date}`.
- **No day after today is a link.** A day with games after today is drawn as a day without games, and the month arrows stop at the month of today.
- Opening the sheet selects the season of the day being shown and the month of that day. With no day selected (the games feed is not in) it opens on the month of the date in the nav row.

### Day page (`/day/[date]`)

- The header and the nav of the home. The `DayStrip` is replaced by a day header:
  - The date, Barlow Condensed 600, `clamp(28px, 4vw, 40px)`.
  - The season label and the weekday, 12px, uppercase, muted.
  - Previous and next day arrows that skip the days without games, looked up in the `days` of the season's calendar feed. An arrow is hidden, not disabled, at the first and last day with games of the season.
  - The calendar button (the same `DateButton` behavior).
- Below the header, the same `GameCard` list as the home. Every game is final. A day with no game shows the existing empty-day message. Each game links to `/game/{id}`. A final game's card opens with its leaders and team stats, read from its game detail, and shows the highlight mark and the video when the stored game has one; the card does not say the stats are unavailable. A final game without a line score (an untimed All-Star game) has a card without expanded details (ADR 0051).
- A date that is inside the games feed window is not served by the day feed (it answers 404 for it): the page uses the games feed for it. A date before 1993-10-01 or after today is a 404 page state: the unavailable state of the home.
- Loading and unavailable states as the home.

### Past game page

- The layout is unchanged. The blocks the source does not carry (plays, win probability, injuries, season series, and in the rare old game the box score) are `null` in the feed and the page hides them; the feed's `leaders` serve the day cards and the past game page draws no leaders block (ADR 0057); hidden blocks leave no gap and the section tabs list only the sections that show.
- The header shows the season label next to the date.
- A side is resolved by team id through the fixed id map: it links to the franchise's team page by today's code and shows the name and city of that season's team object, with the neutral monogram showing the season's abbreviation when the side is historical. A side whose id is not in the map follows the guest rule (ADR 0025, ADR 0026).
- Marks (Cup, postseason, All-Star) are read case-insensitively from the note of the game. A game without a readable note has no mark.

## Seasons on standings, team and player

- **Season selector:** the same select styling, on the first line of the page header on `/standings`, `/team/[code]` and `/player/[id]`. Changing it navigates to `?season=YYYY`; the current season has no parameter. The seasons and labels are the `seasons` of the current calendar feed, whose first entry is the current season (ADR 0044): `/standings` lists every season, `/team/[code]` the seasons inside one of the feed's `names` runs, `/player/[id]` the seasons whose label matches a regular-season row plus the current season. When the calendar feed is unavailable the selector is hidden. On mobile it is full width under the header with a 44px hit target.
- **Season tag:** a past season shows "Season 2004-05" in the header: outlined, accent border, accent-light text, Barlow Condensed 600, 12.5px, .12em, uppercase. A past season shows no live element.

### Standings of a past season

- The same tables with the final records and the clinchers as the source sends them. The state line reads "Final standings". The seed separator lines after seeds 6 and 10 are not drawn: no feed says whether that season had a play-in (ADR 0044).

### Team page of a past season

- The record and the standing of that season, the schedule by month with results, no roster and no leaders block (ADR 0059; a team page stored before keeps them, the roster as `RosterTable` without the injury column). A block without data is hidden. No next game, no injuries, no depth chart, no Cup block, no titles. The Overview and Injuries sections are hidden with their tabs. A team exists in a season when that season's team object answers; whether it is active today is never read (ADR 0053), so a relocated franchise has its old seasons. A franchise with no team that season (404) shows "No team this season." with the selector. The league sides of the schedule are named from the schedule payloads, with the opponent's season abbreviation, and every final game links to its game page.

### Team page, every season: Names timeline

- Shown under the header when the franchise has more than one run; a franchise with one run shows no timeline.
- The runs hold one entry per identity of the franchise from 1994 (Seattle to 2008, then Oklahoma City), so a relocated franchise reaches its old seasons from the selector and from the timeline.
- Horizontal runs separated by 1px dividers. Each run shows:
  - The years in Barlow Condensed 600, 14px ("1967–2008"; the current run reads "2008–").
  - The name in 16px ink: the run's location and name.
  - The code in a 34x24 outlined sigla box (the guest sigla box).
- The current run is drawn in accent light. Each past run links to `/team/{code}?season={last end year of the run}`.
- The runs come from the `names` block of the team feed. Historical runs use the neutral monogram.

### Player page of a past season

- The game log of the season, the season row highlighted in the seasons table, the averages of that season.
- The header shows the team of that season: the game log picks the team, and its name comes from the stored franchise names run that holds the season. There is no number, draft cell or awards block (ADR 0059). The game log names each opponent from the game log payload, with its season abbreviation when historical, and each final game links to its game page. A retired player (`active` false) shows "Retired" in the team tag instead of a current team. A player with no current team who is still active (`team` null, `active` true) shows "Free agent" in the team tag on the current page; on a past season the team is null when no names run is stored yet (a cold page), and the header then draws no team tag at all, never "Free agent". The team of the feed takes precedence when it has one.
- A player with no game log that season shows the existing empty game log state (the game log section is hidden), the averages as the feed gives them, and the seasons table.

## Edge cases

| Case | What shows |
|---|---|
| Day with no games | The day page shows the day header and the existing empty-day message. In the calendar the day is muted and not clickable; the previous and next arrows skip it |
| Day before 1993-10-01 | The feed answers 404; the page shows the unavailable state. The calendar never offers the day: the first season is 1993-94 and months before its first day are not navigable |
| Future day beyond the window | A day after today is a 404; the page shows the unavailable state. No day after today is a link in the calendar, and the month arrows stop at the month of today |
| Today and window days opening from the calendar | A day inside the games feed window links to `/` with the day selected in the `DayStrip`; the day feed is not requested for it. Today has the 1px accent-light outline |
| Season with a lockout gap (1998-99 starts in February) | The calendar's first day is the first game day in February; earlier months are not navigable and the previous arrow is disabled at the first month. Months inside the gap, if the feed lists no day, show a grid with no linked day |
| 2019-20 restart (games in July and August) | The calendar lists the months of the restart; the grid links the days the feed lists, and the previous and next day arrows jump across the pause |
| Game without box score | The box score section is hidden; the score, the quarters and the other blocks show |
| Game without plays | The plays section is hidden |
| Game without win probability | The win probability chart is hidden; the score and the other blocks show |
| Side with a historical name | The side shows that season's name with the neutral monogram showing its season abbreviation, no team color and no strip, and links to the franchise's team page |
| Side whose id is unknown (guest) | The guest rule applies (ADR 0025, ADR 0026): the side shows its name and the neutral monogram and does not link |
| Team with one name run | No "Names" timeline |
| Team with four runs | The timeline shows four runs; on mobile it scrolls horizontally with scroll-snap; the current run is in accent light and each past run links to its last season |
| Player retired | "Retired" instead of a current team; no next game and no injury status |
| Player free agent | "Free agent" instead of a current team; no next game and no injury status. A past season with a null team and `active` true shows no team tag |
| Player with no game log that season | The game log section is hidden (the existing empty state); the averages and the seasons table show as the feed gives them |
| Headshot missing | The existing initials fallback |
| A season with no data for a block (leaders, schedule) | The section is hidden |
| Missing values | `—` in that cell |
| Season outside 1994 to the current season, or a malformed `?season` | The current season, as without `?season` |
| Unavailable feed (503) | The nav row, then the home's 503 state: "Data isn't available right now. Check back later." Polling is not used for a past feed |
| Spanish strings | Every string has a Spanish text; long labels truncate, never wrap in a table cell |

## States

| State | What shows |
|---|---|
| Loading | Skeletons shaped like the day header and the first section (the game card list, or the first block of the page), with the home's shimmer, stopped under reduced motion |
| Feed unavailable | See Edge cases |
| Calendar feed unavailable | The calendar button stays; the sheet opens with the unavailable message; the day page shows its games without the previous and next arrows |
| Calendar feed unavailable (season pages) | The selector is hidden and the page shows the current season |
| Empty day | The existing empty-day message |
| Past season | The "Season {label}" tag, no live element, hidden blocks without gap |

## Interactions and motion

| What | How |
|---|---|
| Date button | Opens the calendar; `aria-expanded`; focus moves into the sheet and returns to the button on close |
| Desktop panel | Opens anchored below the label; Esc and a click outside close it |
| Mobile sheet | `translateY` over 0.5s `cubic-bezier(.2, .7, .1, 1)`, a maximum height of 86vh, a 60% scrim, the body scroll locked; Esc and a tap on the scrim close it |
| Season select | Changes the season in the sheet and moves to the month of the selected day when it is in that season, else to the first month of the season; on a page it navigates to `?season=YYYY` |
| Month arrows | Move one month; disabled at the first and last month of the season |
| Day cell | A day with games navigates; a day without games does nothing |
| Day page arrows | Go to the previous or next day with games |
| Names timeline | Past runs navigate to the team page of the last season of the run; scroll-snap on mobile |
| Focus | `:focus-visible` as on the home |
| Reduced motion | The sheet appears without the slide |

## Responsive

- Under 680px: the calendar is a bottom sheet, the day cells are 36px, the season selectors are full width under the header, the timeline scrolls horizontally with scroll-snap, and every hit target is at least 44px.
- Desktop: the calendar is a 360px panel; the selector sits on the header's first line, at the right edge and top-aligned with it; a right column starts below it (`docs/design.md`, "Page header").

## New tokens

To add to `web/src/lib/styles/tokens.css` in the implementing issue. Values not listed map to existing tokens.

| Token (suggested) | Value | Use |
|---|---|---|
| `--past-panel-width` | 360px | Desktop calendar panel |
| `--past-select-height` | 36px | Season select |
| `--past-select-border` | ink at 25% | Season select border |
| `--past-select-size` | 14px | Season select text |
| `--past-select-letter-spacing` | .08em | Season select text |
| `--past-arrow-size` | 36px | Month arrow button |
| `--past-month-size` | 18px | Month name |
| `--past-weekday-size` | 12px | Weekday initials |
| `--past-weekday-letter-spacing` | .1em | Weekday initials |
| `--past-day-cell` | 40px | Day cell |
| `--past-day-cell-mobile` | 36px | Day cell on mobile |
| `--past-day-size` | 16px | Day number |
| `--past-day-mark` | 4px | Accent square under a day with games |
| `--past-day-off-ink` | ink at 30% | Day without games |
| `--past-day-title-size` | `clamp(28px, 4vw, 40px)` | Day page date |
| `--past-chevron-size` | 12px | Date button chevron |
| `--past-tag-size` | 12.5px | Season tag |
| `--past-tag-letter-spacing` | .12em | Season tag |
| `--past-names-year-size` | 14px | Names timeline years |
| `--past-names-name-size` | 16px | Names timeline name |
| `--past-sigla-width` | 34px | Names timeline sigla box |
| `--past-sigla-height` | 24px | Names timeline sigla box |
| `--past-sheet-duration` | 0.5s | Calendar sheet slide |
| `--past-sheet-max-height` | 86vh | Calendar sheet maximum height |
| `--past-sheet-scrim` | black at 60% | Calendar sheet scrim |

Mapped to existing tokens: the panel surface is `--color-surface`; the divider is `--color-divider`; accent is `--color-accent`; the outline of today and the current run is `--color-accent-light`; muted is `--color-muted`; the hit target is `--hit-target-size`; the sheet motion easing is `--ease`; the 680px break is `--game-row-breakpoint`; the focus ring is `--focus-ring-width` and `--focus-ring-offset`; the heading and body fonts are `--font-heading` and `--font-body`.

## Strings

| Key (suggested) | English | Spanish |
|---|---|---|
| `past_calendar_open` | Open calendar | Abrir calendario |
| `past_calendar_title` | Calendar | Calendario |
| `past_calendar_close` | Close | Cerrar |
| `past_season_select` | Season | Temporada |
| `past_month_prev` | Previous month | Mes anterior |
| `past_month_next` | Next month | Mes siguiente |
| `past_weekdays` | S M T W T F S | D L M X J V S |
| `past_day_prev` | Previous day | Día anterior |
| `past_day_next` | Next day | Día siguiente |
| `past_day_games` | Games on {date} | Partidos del {date} |
| `past_day_title` | Games | Partidos |
| `past_unavailable` | The existing `feed_unavailable`: Data isn't available right now. Check back later. | Los datos no están disponibles ahora. Vuelve más tarde. |
| `past_season_tag` | Season {label} | Temporada {label} |
| `past_standings_final` | Final standings | Clasificación final |
| `past_names_title` | Names | Nombres |
| `past_names_current` | {from}– | {from}– |
| `past_names_run` | {from}–{to} | {from}–{to} |
| `past_player_retired` | Retired | Retirado |
| `past_player_free_agent` | Free agent | Agente libre |
| `past_team_no_season` | No team this season. | Sin equipo esta temporada. |

The date, the season label, the weekday, the month names, the team names and the names of the runs come from the feeds or from the browser's date formatting in the page language; the other keys are the fixed words around them. The empty-day message reuses the string already in production. The missing value is "—" in both languages.

## Feed contract

Keys are camelCase. Nullable fields are always present and `null` when absent. Times are UTC, ISO 8601; a day is `YYYY-MM-DD` on the US Eastern day. Every value is computed by the backend. Exact field names are set by `docs/api` in the issues that add the feeds. Each feed is recorded in rule G (feeds built on demand), in `docs/api` and in one new ADR.

| Path | What it carries | Expiry |
|---|---|---|
| `/feeds/seasons/{season}/calendar.json` | The season label, the first and last day, the list of days with games and the dates of today's window | 24 hours in the current season; a past season is built once and kept |
| `/feeds/days/{date}.json` | The Day of the games feed, with the same Day and Game shapes as `docs/api/games.md`, for a US Eastern day outside the games feed's window | A day whose games are all final is built once and kept; a day with a non-final game expires 6 hours after its build |
| `/feeds/seasons/{season}/standings.json` | The standings feed of that season, same shape as today with season-scoped values | A past season is built once and kept |
| `/feeds/seasons/{season}/teams/{code}.json` | The team feed of that season, same shape as today with season-scoped values, with `names`; no roster or leaders (ADR 0059) | A past season is built once and kept |
| `/feeds/seasons/{season}/players/{id}.json` | The player feed of that season, same shape as today with season-scoped values | A past season is built once and kept |

- **Statuses:** a season outside 1994 to the season before the current one is a 404 for the season standings, team and player feeds (ADR 0043); the current season is served by the existing feeds, and the calendar feed serves the current season too. `/feeds/days/{date}.json` answers 404 for a day inside the games feed window, for a day before 1993-10-01 and for a day after today; the page uses the games feed for a day in the window.
- **Current season:** for the current season the page uses the existing feeds, not the season feeds. The calendar feed serves the current season too.
- **Null blocks of a past season:** the blocks that only exist for the current season are `null`: live status, next game, injuries, depth chart, the Cup block and the titles of the current season.
- **Team `names` block** (in the team feed of the current and of every past season): a list of `{from, to, name, location, code}` built from the per-season team objects from 1994 to the current season (a season whose object answers has a team, whatever its `isActive`) and merged into runs where name, location and code are equal; `to` is `null` for the current run. It is built once per team and kept while its build version is current, the current season read again when the list is 24 hours old ([ADR 0065](adr/0065-background-work-limited-to-games-highlights-and-stars.md)).
- **Past game detail:** `/feeds/games/{id}.json` also serves a game of a stored day feed, only when that game is final; any other game is a 404. It is built once and kept (rule D), and never refreshed by the games job. The blocks the source does not carry (plays, win probability, leaders, injuries, season series and, in the rare old game, the box score) are `null`. A side carries the team id, the name and city of that season's team object, today's code from the fixed id map, its season abbreviation (`seasonCode`) and the `historical` flag; the code is `null` only for an unknown id. A game registered by a past team schedule or player game log is served as well as a final game of a stored day feed (ADR 0053). A final game of the day feed has its stats available, read from its game detail (ADR 0054).
- **Marks:** the Cup, postseason and All-Star marks are read case-insensitively from the note of the game; before 2008 the postseason note carries no round and game number, and a game without a readable mark has none. The play-in exists from 2021 and the Cup from 2023-24.
- **Build version:** the kept past feeds (standings, team, player, Cup, Cup matchup, playoffs, Finals, All-Star, day and game detail) carry `buildVersion`. A stored feed of another or no version is served as stored and rebuilt on its next request, and a failed rebuild keeps it; the current feeds carry `null` (ADR 0053, ADR 0054).
