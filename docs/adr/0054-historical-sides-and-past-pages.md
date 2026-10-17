# 0054. Historical sides and past pages

- Status: Accepted
- Date: 2026-10-17

## Context

Issue 269. The audit of the past season pages found that a league side of a past
feed was drawn with today's colors and today's code even when that season's
franchise had another name, city or abbreviation (the 2004-05 SuperSonics drawn
as Oklahoma City, in Thunder blue). The past day cards said the stats of every
final game were not available although its game detail is served (ADR 0041,
ADR 0053). The Cup selector dropped the season on show when it was before 2024.
The All-Star format reached the page as English text.

## Decision

- `seasonCode` and `historical` are two new fields of `Opponent` (ADR 0026), of
  `TeamFeed` and of `StandingsRow`. `seasonCode` is that season's abbreviation
  from the per-season team object (the provider code mapped to the standard code
  as in the names runs). `historical` is true when that season's name, city or
  abbreviation differs from the current season's team object. Both are set on
  every league side of the past standings, team, player, day, game detail,
  playoffs, Finals and Cup feeds; they are null and false on a current feed and
  on a guest side. The link code stays today's code from the fixed id map, as ADR
  0053 decided.
- The past playoffs, Finals and Cup sides are named by the season team object
  (name and city), as ADR 0053 names the sides of the other past feeds, so a
  historical side never shows a season code next to today's name. One core helper
  walks a built feed and names every league side; the section builders are not
  changed.
- The web draws a historical side as the guest sigla box showing `seasonCode`
  with no team color and no strip, linking to today's team. A side that is not
  historical keeps its colors on a past season. A past game log row and a past
  schedule row show the opponent's `seasonCode`.
- A final game of the day feed has `statsAvailability` `available` with null
  `leaders` and `teamStats`: they are read from its game detail, which is served
  for every final game from 1993-94 on. This supersedes ADR 0040's
  `unavailable` stats on a final game. `PastGame` replaces the rule of `Game` that
  `available` needs both.
- `/cup` lists the calendar's seasons from 2024 and the season on show, as ADR
  0044 sets for every selector. This supersedes the rule of ADR 0049 that the
  selector never offers a season below 2024.
- The All-Star edition's `formatLine` text is replaced by `format`, the parts
  `targetPoints`, `untimed`, `periods` and `minutes`, which the page words in its
  language. A stored All-Star feed with `formatLine` is invalid and is rebuilt on
  its next request.
- `SEASON_BUILD_VERSION` is 2, so every kept past feed is rebuilt with these
  fields on its next request.

## Consequences

- Ten schemas (games, game detail, team, player, Cup, Cup matchup, playoffs,
  Finals, All-Star and days) gain the two side fields, the standings and team
  schemas gain them on the row and the header, and the All-Star schema gains
  `AllStarFormat`. The front end types are regenerated.
- Every kept past feed is served as stored and rebuilt on its next request. A
  cold past playoffs rebuild reads about 1,300 summaries, cached in the state
  database after the first time.
- A past build reads the current season's team object of each franchise it
  names, besides the season's own; the source cache serves the repeat read.
- Past playoffs, Finals and Cup pages show that season's names for relocated
  franchises.
