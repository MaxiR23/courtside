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
| `leaders` | `HomeLeaders` / null | Four per-game leaders | always null in this version; part 2 fills it |
| `finalsPath` | `FinalsPath` / null | The road of each finalist | always null in this version; part 2 fills it |

## Nested objects

| Object | Fields |
| --- | --- |
| `ComingUpItem` | `key` (`openingNight`, `cupGroupStage`, `cupKnockout`, `cupFinal`, `allStar`, `playIn`, `playoffs`, `finals`, `preseason`), `startDate`, `endDate` (null for a single day, else after `startDate`), `status` (`done`, `now`, `upcoming`) |
| `NextGame` | `date`, `firstTipOff` (UTC time), `broadcast` (TV network of the first game of that day, null when unknown), `gameCount` (positive integer), `inGamesWindow` (the day is inside the games feed window, so `/?day=` can select it) |
| `LastGames` | `date`, `title`: `LastGamesTitle`, `games`: `LastGame[]` (not empty) |
| `LastGamesTitle` | `key` (`lastNight`, `daysAgo`, `beforeTheBreak`, `conferenceFinals`, `lastGamesPlayed`), `days` (integer of 2 or more for `daysAgo`, else null) |
| `LastGame` | `id`, `away`, `home` (`Opponent`, the games feed's side: code, name, city, guest, seasonCode, historical, logo, colors, with the logo and colors added when served), `score` (`away`, `home`), `winner` (`away`, `home` or null), `label` (`final`, `finalOvertime`, `playIn`, `firstRound`, `conferenceSemifinals`, `conferenceFinals`, `finals`), `gameNumber` (1 to 7 for a playoff round or the Finals, else null), `accent` (`away`, `home` resolved colors, added when served, null in the stored file) |
| `HomeLeaders` | `title` (`season`, `playoffs`, `previousSeason`), `seasonLabel` (for `previousSeason`, else null), `categories`: `HomeLeader[]` in order points, rebounds, assists, blocks |
| `HomeLeader` | `category`, `playerId`, `name` (dash when the identity is not read), `photoUrl` (null), `team`: `HomeLeaderTeam` / null, `value` (ready text) |
| `HomeLeaderTeam` | `code`, `logo` (null), `accent` (null) |
| `FinalsPath` | `finalists`: two `FinalistPath` |
| `FinalistPath` | `code`, `name`, `logo`, `accent`, `series`: three `PathSeries` |
| `PathSeries` | `round` (key), `opponent`: team (`code`, `name`, `logo`, `accent`), `result` (such as `4–2`), `won` |

## Rules that live in the code

- The scenario is decided only here: `offseason` between the end of the postseason and
  the start of the regular season; `allStarBreak` between the last regular-season game
  day before the All-Star date and the first after it; `finalsPreview` when the
  conference finals are complete and Finals Game 1 has not started; `offDay` otherwise.
- `comingUp` is null unless the next big event starts in 14 days or less or one is in
  progress; in the offseason it is always present when an item has a date. An event with
  no date is left out. Once the window is open it lists the `now` items, the upcoming
  items starting in 14 days or less and the `done` items that ended 14 days ago or less,
  by start date, ties in the order of the keys. A `done` item alone never opens it.
- The status of an item is `upcoming` before its start date, `now` from the start date to
  the end date (the start date alone for a single day) and `done` after.
- The Cup items come from the stored Cup feed of the season (its first game date and its
  stages); with none, they are left out. The Finals item is the date of Finals Game 1 of
  the stored playoffs feed. The All-Star item is the date the All-Star build recorded.
- The season calendar is the calendar feed of the season, built first as a dependency
  (and the previous season's when the current one has no earlier day).
- Today is the games feed's today (ADR 0013): the middle of the days the games job
  shows, else the US Eastern date of the clock before the job's first run.
- `nextGame` looks 14 days ahead in the season calendar and reads one scoreboard day,
  only for a day outside the games feed window; postponed and canceled games are not
  counted.
- `lastGames` shows the last calendar day before today (the last one before the break in
  `allStarBreak`) and only final games with no All-Star mark. It comes from the games job
  memory for a day inside the games feed window and from the day feed of that date
  otherwise. The label is `playIn`, `firstRound`, `conferenceSemifinals`,
  `conferenceFinals` or `finals` from the game's postseason mark, else `finalOvertime`
  past the 4th period, else `final`; `gameNumber` comes with a playoff round.
- `leaders` for the regular season request the regular season explicitly; names and
  photos come from the player identities, at most 4 reads per build.
- A failed read nulls only its field; the feed is not a 503.

## Refresh

On demand. Rebuilt at the first US Eastern day change after the build, and one hour
after the build while an item of `comingUp` is `now` (the games feed's today, ADR 0013).
A build that needed the games job memory for the last or next game day while it was not
loaded has those fields `null`; it expires once the memory is loaded, or one hour after
the build, whichever comes first. A feed stored by an earlier process is treated the
same way, once, until the process builds it again.

## Read budget

Season types 4 (the postseason first, then three more of this season or two of the next)
and the next game day scoreboard 1, read only for a day outside the games feed window;
leaders 1 and player identities 4 come with part 2. The calendar feed, and the Cup,
All-Star, playoffs and day feeds, are built first as dependencies only inside their
windows and keep their own budgets. The leaders URL is the Settings template
`season_leaders_url` (`{season}`).

- **`SEASON_LEADERS_URL`** (`{season}`): `{"categories": [{"name", "leaders":
  [{"displayValue", "athlete": {"$ref"}, "team": {"$ref"}}]}]}`. The names read are
  `pointsPerGame`, `reboundsPerGame`, `assistsPerGame` and `blocksPerGame`; any other
  category is ignored. The athlete id is the path part after `athletes` in the link,
  and the link is never followed. The team code is the id after `teams` in the team
  link, mapped to a league team; it is null when the link is absent or is not a league
  team.
