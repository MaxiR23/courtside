# 0040. Calendar and day feeds

- Status: Accepted
- Date: 2026-10-15

## Context

Issue 243. The page for past dates needs the days with games of a season and the
games of one past day. The games feed holds only the days shown, and its `Game`
requires a star on every league side, which no past season can give.

## Decision

- **Seasons are identified by their end year**, from 1994.
- **The calendar feed** (`/feeds/seasons/{season}/calendar.json`) is read from
  the scoreboard day of February 1 of the end year. Its days are the US Eastern
  dates of the calendar entries, sorted and unique; `firstDay` and `lastDay` are
  the first and last of them, and `windowDays` are the days of the stored games
  feed at build time. An unreadable entry is skipped and logged; a missing or
  empty calendar fails the build.
- **The calendar answers** 404, with no source request, for a season that is not
  four digits, is before 1994 or is after the current season, and 503 while the
  stars job does not know the current season.
- **The day feed** (`/feeds/days/{date}.json`) answers 404, with no source
  request, for an id that is not a real `YYYY-MM-DD` date, a date before
  1993-10-01, a date after today (US Eastern) and a day of the games feed: the
  stored window, or with none stored the days the games job would show (the
  games job's 7-day rule).
- **The games of a past day** are `PastGame`, a `Game` that replaces only the
  rule that a league side has a star: both stars are null and highlights are
  empty. A final game has `statsAvailability` `unavailable` with no detail
  request, because the scoreboard event carries no leaders or team totals; any
  other game has no stats fields. Sides are resolved by team id first, with the
  event's name and city; an unknown id follows the guest rule. The marks are
  read case-insensitively, in the games feed path too, and title-case notes give
  the same marks as before. A game that cannot be mapped or is not valid is
  skipped and logged by event id.
- **The expiries** (rule G): a calendar of the current season expires 24 hours
  after the build; a calendar of a past season built after its last day is kept.
  The last day guard keeps a calendar stored while its season was current from
  being frozen at the season change. A day with every game final, or with no
  game, is kept; a day with any other game expires 6 hours after the build.
- **The day feed stays outside** the games job, the hero, the highlights job,
  the live refresh and the cleanup of rule J. Its requests record presence like
  every feed request.

## Consequences

- Issue 3 serves past game detail.
- The day feed's stats stay unavailable until a recorded scoreboard event shows
  leaders and team totals.
- The provider's calendar keys are assumed (`leagues[0].calendar`): a different
  real shape fails every calendar build until the one provider model is fixed.
- The calendar lists every day the source lists, future days included; the page
  limits the dates.
