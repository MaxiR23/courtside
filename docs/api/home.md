# Home feed

What the home shows on a day with no games, with every value ready to draw. The
scenario, the dates, the statuses and the titles are decided by the backend.

## Schema

`api/schemas/home.schema.json`, generated from the models in `api/app/feeds/home.py` by
`scripts/contract.sh`. When this page and the models disagree, the models win. The feed
is decided in [ADR 0074](../adr/0074-home-feed.md) and served at `/feeds/home.json`.

This page holds the planned contract. The implementing issues keep it exact: part 1
(scenario, `comingUp`, `nextGame`, `lastGames`) and part 2 (`leaders`, `finalsPath`).

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone. Dates are `YYYY-MM-DD` in US Eastern.

## Feed

| Field | Type | Meaning | Present |
| --- | --- | --- | --- |
| `season` | season label | Such as `2026-27` | always |
| `date` | date | Today in US Eastern | always |
| `scenario` | `HomeScenario` | `offDay`, `allStarBreak`, `finalsPreview` or `offseason` | always |
| `comingUp` | `ComingUpItem[]` / null | The events of the window, in date order | null outside the window |
| `nextGame` | `NextGame` / null | The first game day after today | null when none in 14 days |
| `lastGames` | `LastGames` / null | The most recent game day before today | null when unread or none |
| `leaders` | `HomeLeaders` / null | Four per-game leaders | null when unread (part 2) |
| `finalsPath` | `FinalsPath` / null | The road of each finalist | `finalsPreview` only (part 2) |

## Nested objects

| Object | Fields |
| --- | --- |
| `ComingUpItem` | `key` (`openingNight`, `cupGroupStage`, `cupKnockout`, `cupFinal`, `allStar`, `playIn`, `playoffs`, `finals`, `preseason`), `startDate`, `endDate` (null for a single day), `status` (`done`, `now`, `upcoming`) |
| `NextGame` | `date`, `firstTipOff` (UTC time or null), `broadcast` (TV network of the first game of that day, null when unknown), `gameCount`, `inGamesWindow` (the day is inside the games feed window, so `/?day=` can select it) |
| `LastGames` | `date`, `title`: `LastGamesTitle`, `games`: `LastGame[]` |
| `LastGamesTitle` | `key` (`lastNight`, `daysAgo`, `beforeTheBreak`, `conferenceFinals`, `lastGamesPlayed`), `days` (integer for `daysAgo`, else null) |
| `LastGame` | `id`, `away`, `home`: `LastGameSide`; `label` (`final`, `finalOvertime` or a playoff round and game number key) |
| `LastGameSide` | `code`, `name`, `logo` (null), `accent` (resolved color, null), `score`, `winner` |
| `HomeLeaders` | `title` (`season`, `playoffs`, `previousSeason`), `seasonLabel` (for `previousSeason`, else null), `categories`: `HomeLeader[]` in order points, rebounds, assists, blocks |
| `HomeLeader` | `category`, `playerId`, `name` (dash when the identity is not read), `photoUrl` (null), `team`: `HomeLeaderTeam` / null, `value` (ready text) |
| `HomeLeaderTeam` | `code`, `logo` (null), `accent` (null) |
| `FinalsPath` | `finalists`: two `FinalistPath` |
| `FinalistPath` | `code`, `name`, `logo`, `accent`, `series`: three `PathSeries` |
| `PathSeries` | `round` (key), `opponent`: `LastGameSide`-like team (`code`, `name`, `logo`, `accent`), `result` (such as `4–2`), `won` |

## Rules that live in the code

- The scenario is decided only here: `offseason` between the end of the postseason and
  the start of the regular season; `allStarBreak` between the last regular-season game
  day before the All-Star date and the first after it; `finalsPreview` when the
  conference finals are complete and Finals Game 1 has not started; `offDay` otherwise.
- `comingUp` is null unless the next big event starts in 14 days or less or one is in
  progress; in the offseason it is always present. An event with no date is left out.
- `nextGame` looks 14 days ahead in the season calendar and reads one scoreboard day.
- `lastGames` comes from the games job memory for a day inside the games feed window and
  from the day feed of that date otherwise.
- `leaders` for the regular season request the regular season explicitly; names and
  photos come from the player identities, at most 4 reads per build.
- A failed read nulls only its field; the feed is not a 503.

## Refresh

On demand. Rebuilt at the first US Eastern day change after the build, and one hour
after the build while an item of `comingUp` is `now`.

## Read budget

Season types 4, the next game day scoreboard 1, leaders 1, player identities 4. The Cup,
All-Star and playoffs feeds are built as dependencies only inside their windows and keep
their own budgets. The leaders URL is the Settings template `season_leaders_url`
(`{season}`).
