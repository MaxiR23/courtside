# 0042. Calendar seasons and the day's season

- Status: Accepted
- Date: 2026-10-15

## Context

Issue 247. The calendar sheet and the day page read the calendar feed and the day
feed of ADR 0040. The sheet needs the list of seasons for its selector and a way
to ask for the current season's calendar without knowing its end year. The day
page needs the season of the day it shows. The day page is for dates the front
end does not know at build time, and the calendar is not live data.

## Decision

- **`current` as a calendar id** resolves to the current season's end year
  before the cache, so it has the same stored file, body, ETag and expiry as the
  end-year path. It answers 503 while the season is unknown.
- **`seasons`** on the calendar feed runs from the current season down to 1994,
  newest first, each as an end year with its label. It is set again at serve
  time, so a kept past calendar never shows a stale list.
- **The day feed's `season`** is read from `leagues[0].season.year` of that day's
  scoreboard response, and `seasonLabel` is written as `season_label` writes it.
  A day whose season cannot be read fails the build.
- **`/day/{date}`** is rendered in the browser from the fallback page `200.html`,
  with no prerender, like the other routes with a param.
- **The day page and the calendar sheet load their feeds once** and are not
  polled.
- **The day page redirects a 404** for a date that is one of the games feed's
  days to `/?day=YYYY-MM-DD` with `replaceState`. Any other 404 shows the
  unavailable state. The calendar sheet links a day of the games feed to
  `/?day=` and any other day to `/day/{date}`.

## Consequences

- The scoreboard key is assumed, as ADR 0040's calendar key is. If it is wrong,
  every day build fails and answers 503.
- Day and calendar feeds stored before this change fail validation and are
  rebuilt on their next request.
- Until a stored day is rebuilt, its games are not past-game ids for ADR 0041.
- The day page has no games feed of its own, so its today is the browser clock's
  US Eastern date.
