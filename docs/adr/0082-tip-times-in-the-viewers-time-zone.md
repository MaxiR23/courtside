# 0082. Tip times in the viewer's time zone

- Status: Accepted
- Date: 2026-10-28

## Context

The feeds send UTC instants. `/web` showed every time in a fixed US Eastern
zone with an "ET" suffix, whatever the zone of the viewer. ADR 0013 sets the
NBA day in US Eastern, and the day strip, the schedule day groups, `/day/` and
the calendar rely on it.

## Decision

- Times, and a date shown together with its time, are formatted with
  `Intl.DateTimeFormat` in the browser's default zone, with no suffix. A
  24-hour language shows "20:30" with no day period.
- A date that names the game's day without a time, the day strip, the schedule
  day groups, the team schedule date columns, `/day/` and the calendar stay on
  the NBA day (US Eastern).
- One module, `web/src/lib/format/time.ts`, holds the helpers and the only
  `America/New_York` constant.
- Times are formatted only in the browser: every page except the home sets
  `ssr = false`, and the home formats only from feeds it loads in the browser.
- Tests pin `TZ=America/New_York` in the Vitest config.
- Not Temporal: Safari stable does not ship Temporal in full yet, and a
  polyfill would add weight for no gain, since `/web` only formats.

## Consequences

- A viewer outside US Eastern can see a late game listed under its NBA day with
  a time after local midnight.
- On the game page the header date (NBA day) and the "Tip-off" cell date (local)
  can differ by one day, as can the next-game card and the schedule row of the
  same game on the team page.
- On the home with no games, the "Next tip-off" day (viewer zone) can differ by
  one day from the "Go to {day}" label (NBA day) when both show.
- The `time_eastern` message is retired.
- There is no time zone picker.
