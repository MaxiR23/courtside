# 0044. Season selector sources

- Status: Accepted
- Date: 2026-10-15

## Context

Issue 251. The standings, team and player pages get a season selector and read
the season feeds of ADR 0043. `docs/design-past-dates.md` draws the selector
but names no source for its list, no rule for the current season and no rule for
an unknown `?season`.

## Decision

- **List and labels.** The seasons and their labels are the `seasons` of
  `/feeds/seasons/current/calendar.json`. The current season is its first entry
  (ADR 0042). The page computes no season and no label.
- **Per page.** `/standings` lists every season. `/team/{code}` lists the
  seasons inside one of the feed's `names` runs (a `to` of null runs to the
  current season; no `names` lists every season). `/player/{id}` lists the
  seasons whose label matches a regular-season row of the feed's `seasons`,
  plus the current season. The match is by label, with no arithmetic. The
  season on show is always in the list.
- **The query.** `?season=YYYY` with the end year. The current season has no
  parameter. An absent, malformed, unknown or current value shows the current
  season with the existing feeds and polling. A four-digit value waits for the
  calendar before the page chooses a feed. With the calendar unavailable the
  selector is hidden and the page shows the current season.
- **Past feeds.** A past season reads its season feed (ADR 0043) once and does
  not poll it. The settings are `SEASON_STANDINGS_FEED_URL`,
  `SEASON_TEAM_FEED_URL` and `SEASON_PLAYER_FEED_URL`.
- **Past team 404.** A franchise with no team that season shows "No team this
  season." with the selector.
- **Hidden blocks.** A past team page hides its Overview and Injuries sections
  and the roster status column. A past player page hides the next game card.
- **Seed lines.** The standings page of a past season does not draw the
  separator lines after seeds 6 and 10: no feed says whether that season had a
  play-in, and the lines mark the play-in era. The current season draws them
  as before.
- **Where `?season` is read.** The routes read it from `page.url`
  (`$app/state`): they are rendered in the browser only (`ssr = false`).

## Consequences

- One calendar request per page view when `CALENDAR_FEED_URL` is set.
- A deep link to a past season waits for the calendar; a failed calendar turns
  a past link into the current season.
- A season the calendar does not list is never offered.
- A past season that had a play-in shows no separator lines, even though it
  could have drawn them; a later feed that says so can bring them back.
