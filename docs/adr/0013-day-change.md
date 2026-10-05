# 0013. Day change

- Status: Accepted
- Date: 2026-10-05

## Context
ADR 0007's "Day boundary" and "Cadences" make the day the US Eastern date and
fetch the schedule of the 7 days shown once a day, in the morning. The games
job moved the window only then, so between US Eastern midnight and the
morning fetch the page showed the previous day as today. Raised in #59; the
owner decided in #60.

## Decision
- The feed's today, its middle day, changes at US Eastern midnight.
- While any game of the previous day is live, the previous day stays today
  and its games keep their live cadence.
- The first run after none of them is live moves the window: the new day is
  the middle day, the days not held yet are fetched, and the days outside the
  window are dropped.
- The morning run at `DAILY_FETCH_TIME` refreshes the schedule of the 7 days
  shown and never moves the window. The state cleanup of ADR 0011 stays with it.

## Consequences
- The feed contract does not change; the front end still reads the middle
  day as today.
- A start after midnight takes the calendar date as today, even if a game of
  the previous day is live; that game stays in the window, one day before the
  middle, with its live cadence.
- Only a live game holds the previous day: a delayed or not yet started game
  of the previous day does not.
- The stars job and its morning cadence do not change.
- Refines the "Day boundary" and "Cadences" of ADR 0007 without superseding
  it as a whole. ADR 0007 is not edited.
