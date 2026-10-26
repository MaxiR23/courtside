# 0074. Home feed for a day with no games

- Status: Superseded by 0077 for its Cup, All-Star and playoffs dependencies only
- Date: 2026-10-26

## Context

On a day with no games the home draws only the nav: the hero has no game and the
schedule shows one muted row. The site should say why there are no games, what comes
next and what was played last. `/web` computes nothing (principle 2), so the scenario,
the dates, the statuses and the titles must come ready from the backend. The data
exists in feeds and adapters already in force: the season types, the season calendar,
the games job memory, the day feed, the Cup, All-Star and playoffs feeds, the player
identities (ADR 0061) and the resolved team colors (ADR 0068, ADR 0072).

## Decision

A new on-demand feed kind `home`, id `league`, stored at `feeds/home/league.json` only
when requested and served at `/feeds/home.json`, under rules G and H of
`source-rules.md`. The Pydantic models are the source of truth; the contract is
documented in `docs/api/home.md`.

**What it carries.**

- `scenario`: `offDay`, `allStarBreak`, `finalsPreview` or `offseason`. Only the
  backend decides it, from the dates: `offseason` between the end of the postseason and
  the start of the regular season; `allStarBreak` between the last regular-season game
  day before the All-Star date and the first after it; `finalsPreview` when the
  conference finals are complete and Finals Game 1 has not started; `offDay` otherwise.
- `comingUp`: the next big event starting in 14 days or less (one constant), or an event
  in progress, as a list of items each with a key, a date or dates and a status `done`,
  `now` or `upcoming`. Events: Opening Night, the Cup stages, All-Star, Play-In,
  Playoffs and Finals (Finals Game 1, only when the playoffs bracket has it). In the
  offseason it is always present, with the preseason start and Opening Night. An item
  with no date is left out, never invented. Null outside the window.
- `nextGame`: the first day with games after today in the next 14 days, its first start
  time and TV network, its game count and whether that day is inside the games feed window; null when
  there is none.
- `lastGames`: the most recent day with games before today, a title key (`lastNight`,
  `daysAgo` with the count, `beforeTheBreak`, `conferenceFinals`, `lastGamesPlayed`) and
  its games in a compact shape.
- `leaders`: one leader per category (points, rebounds, assists and blocks per game)
  with a title key `season`, `playoffs` or `previousSeason`.
- `finalsPath`: in the Finals preview only, the three series of each finalist.

**Sources.** The season types (preseason added as type 1, with the play-in, regular
season and postseason), the season calendar, one scoreboard read for the next game day,
the season leaders adapter, the player identities, and the games job memory
(`shown_days`, `shown_games`) for a day inside the games feed window, which the day feed
answers with 404. Any other last-games day comes from the day feed of that date, built
first as a dependency with its own budget.

**Dependencies, only inside their windows.** The Cup feed from the Cup's first game date
to its championship; the All-Star feed from February 1 to March 7 (its edition search
window, ADR 0065); the playoffs feed from the play-in start to the end of the
postseason. Outside its window a dependency is never built.

**Failures.** A missing field is `null` and a failed read nulls only the field it feeds.
The feed is never a 503 for a missing piece.

**Freshness.** Rebuilt at the first US Eastern day change after the build, and one hour
after the build while an item of `comingUp` is `now`.

**Read budget.** Declared in the module and in `source-rules.md`: season types 4, the
next game day scoreboard 1, leaders 1, player identities 4. Dependencies keep their own
budgets. There is no background job, prewarm or hidden job (ADR 0065).

**Display.** The front end loads the feed once, with no poller, only when the games feed
is in and today has no games. A day with games keeps the current home.

## Consequences

- One feed answers the whole no-games home; the web draws without rules.
- Only Courtside decides the scenario, so a date rule changes in one place.
- The home has no events beyond those listed in the Decision: All-Star weekend events and offseason
  events (Draft, free agency, Summer League, training camps) are not carried, because
  there is no verified data for them.
- Leaders exclude percentages: early in the season there is no qualifying minimum.
- Each implementing issue keeps `docs/api/home.md` exact.
