# Player feed

One player with everything the player page shows: identity, profile, season
summary, games, statistics, milestones and awards.

## Schema

[`api/schemas/player.schema.json`](../../api/schemas/player.schema.json),
generated from the models in `api/app/feeds/player.py`. When this page and
the models disagree, the models win. The route is decided in
[ADR 0021](../adr/0021-player-and-team-pages.md); the feed is served at
`/feeds/players/{id}.json`.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

The root is one player.

| Field          | Type                    | Meaning                                                            | Present                                  |
| -------------- | ----------------------- | ------------------------------------------------------------------ | ---------------------------------------- |
| `id`           | string                  | Player identifier                                                  | always                                   |
| `firstName`, `lastName` | string         | Identity                                                           | always                                   |
| `number`       | `JerseyNumber` / null   | Jersey number as text (`00` and `0` differ)                        | null when unknown                        |
| `position`     | string                  | Position name                                                      | always                                   |
| `team`         | `Team`                  | `code`, `name`, `city`, as in the [games feed](games.md)           | always                                   |
| `photoUrl`     | URL / null              | Photo                                                              | null when unknown                        |
| `injury`       | `PlayerInjury` / null   | Current injury report                                              | null when healthy                        |
| `profile`      | `Profile`               | Biographical data, each field null when unknown                    | always                                   |
| `summary`      | `Summary` / null        | Season averages with their league rank                             | null when no data                        |
| `nextGame`     | `NextGame` / null       | The team's next game                                               | null shows "Season over."                |
| `live`         | `PlayerLive` / null     | The live game of the player's team                                 | null when the team has no live game      |
| `lastGames`    | `GameLogEntry[]`        | Up to five games, newest first, All-Star and preseason excluded    | always, may be empty                     |
| `averages`     | `Averages`              | Regular season, playoffs and career averages                       | always                                   |
| `seasons`      | `Seasons`               | Season rows of the regular season and the playoffs                 | always                                   |
| `milestones`   | `Milestones` / null     | Counts of notable events                                           | null when no data                        |
| `gameLog`      | `GameLog` / null        | Every game of the season, newest first                             | null when no data                        |
| `awards`       | `Award[]`               | Awards with their seasons                                          | always, may be empty                     |

## Nested objects

| Object             | Fields                                                                                                                                         |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `Opponent`         | `code` (null for a guest without one), `name`, `city` (null when the source sends none), `guest`; as in the [games feed](games.md) ([ADR 0026](../adr/0026-one-guest-team-rule.md)) |
| `GameTag`          | `kind` (`cup`, `playoffs`, `allstar`), `conference` (`east`, `west` / null), `round` (1 to 4 / null, 4 is the Finals), `game` (number / null)  |
| `NextGame`         | `gameId`, `startTime`, `opponent`: `Opponent`, `isHome`, `tag`: `GameTag` / null, `arena`, `city` (null), `broadcast` (null), `detailAvailable`    |
| `PlayerInjury`     | `status` (the game detail feed's `InjuryStatus`), `comment` (null when none), `updatedAt`                                                      |
| `Profile`          | `height`: `Height`, `weight`: `Weight`, `birthDate`, `age`, `birthplace`: `Birthplace`, `college`, `draft`: `Draft` (null when undrafted), `seasons`, `debutSeason`; each null when unknown |
| `Height`           | `display` (text), `cm`                                                                                                                         |
| `Weight`           | `lb`, `kg`                                                                                                                                     |
| `Birthplace`       | `place`, `country` (null when unknown)                                                                                                         |
| `Draft`            | `year`, `round`, `pick`, `teamName`                                                                                                            |
| `Summary`          | `season`, `points`, `rebounds`, `assists`: `RankedStat`, `fieldGoalPct`: `RankedPercentage`                                                    |
| `RankedStat`       | `value`, `rank` (null when unranked); `RankedPercentage` has `value` from 0 to 1                                                               |
| `PlayerLive`       | `gameId`, `opponent`: `Opponent`, `isHome`, `period`, `clock`, `teamScore`, `opponentScore`, `line`: the game detail feed's `BoxScorePlayer` / null  |
| `GameLogEntry`     | `gameId`, `date`, `opponent`: `Opponent` (null for All-Star), `isHome`, `kind` (`regular`, `cup`, `playoffs`, `allstar`, `preseason`), `tag`, `result` (`win`, `loss`), `teamScore`, `opponentScore`, `minutes` (whole), `fieldGoalsMade`, `fieldGoalsAttempted`, `fieldGoalPct`, `threePointsMade`, `threePointsAttempted`, `threePointPct`, `freeThrowsMade`, `freeThrowsAttempted`, `freeThrowPct`, `rebounds`, `assists`, `blocks`, `steals`, `fouls`, `turnovers`, `points`, `detailAvailable` |
| `GameLog`          | `season`, `entries`: `GameLogEntry[]`                                                                                                          |
| `Averages`         | `regular`, `playoffs`: `SeasonAverageRow` / null; `career`: `AverageRow` / null                                                                |
| `AverageRow`       | `gamesPlayed` (at least 1), `minutes`, `fieldGoalPct`, `threePointPct`, `freeThrowPct`, `rebounds`, `assists`, `blocks`, `steals`, `fouls`, `turnovers`, `points`; `SeasonAverageRow` adds `season` |
| `Seasons`          | `regular`, `playoffs`: `SeasonSplit`                                                                                                           |
| `SeasonSplit`      | `perGame`, `totals`: `SeasonRow[]`; `career`: `CareerRows` / null (null without rows)                                                          |
| `CareerRows`       | `perGame`, `totals`: `StatRow`                                                                                                                 |
| `StatRow`          | `gamesPlayed`, `gamesStarted`, `minutes` (null in totals), `fieldGoalsMade`, `fieldGoalsAttempted`, `fieldGoalPct`, `threePointsMade`, `threePointsAttempted`, `threePointPct`, `freeThrowsMade`, `freeThrowsAttempted`, `freeThrowPct`, `offensiveRebounds`, `defensiveRebounds`, `rebounds`, `assists`, `blocks`, `steals`, `fouls`, `turnovers`, `points` |
| `SeasonRow`        | `StatRow` fields plus `season` (such as `2025-26`) and `teams` (at least one code)                                                             |
| `Milestones`       | `season`, `current`, `career`: `MilestoneCounts`                                                                                               |
| `MilestoneCounts`  | `doubleDoubles`, `tripleDoubles`, `disqualifications`, `ejections`, `technicals`, `flagrants`, `assistTurnoverRatio`, `stealTurnoverRatio`      |
| `Award`            | `name`, `count`, `seasons` (labels, at least one)                                                                                              |

`GameTag` and `NextGame` are shared with the [team feed](team.md).

## Rules that live in the code

- Percentages are from 0 to 1; counting stats are not negative; in every
  stat row and game log entry, made is not above attempted.
- Season labels look like `2025-26`; jersey numbers are text of one or two
  digits.
- `Draft.teamName` is the drafting franchise's current name.
- An award with no season is left out.
- `lastGames` lists at most five entries, newest first, with no All-Star or
  preseason game. The game log keeps preseason games, with `kind` `preseason`
  and no tag; averages and milestones come from the season stats and do not
  change.
- An `Opponent` is a league team or a guest ([ADR 0026](../adr/0026-one-guest-team-rule.md)):
  a guest without a code has a null `code` and the source's `name` and `city`,
  and an event whose opponent has neither a code nor a name is skipped.
- `gameLog.entries` are newest first. Only an All-Star entry has a null
  `opponent`.
- `seasons.*.perGame` and `seasons.*.totals` are newest first with one row
  per season. A season played for more than one team is one combined row
  whose `teams` lists every code.
- `minutes` is a number in every per game row and in `career.perGame`, and
  null in every totals row and in `career.totals`. Game log `minutes` are
  whole minutes.
- An averages row exists only with at least one game, otherwise it is null.
- `live.line`, when not null, has the `playerId` of this player. It is null
  before the player enters the box score.
- `profile.seasons` is the number of distinct regular seasons in the
  player's stats; `debutSeason` is the oldest of them. The feed's validator
  checks both against `seasons.regular.perGame`.
- A `GameTag` whose note format is not recognized keeps its `kind` with
  null `conference`, `round` and `game`. The builder applies this rule.

## Refresh behavior

- The id is a player of a roster the stars job fetched, with the team of the
  latest roster that lists him. Nothing is built without a request: no job
  and no startup builds a player feed. The feed is stored at
  `feeds/players/{id}.json` when first requested.
- Built on request under rule G of
  [`docs/source-rules.md`](../source-rules.md) and expiring as its table
  says: when the player's team has a final game whose final time plus 1 hour
  is after the build, and in any case 7 days after the build.
- The team feed is built first when it is missing or stale. The next game is
  the stored team feed's, so the team schedule is never fetched by a player
  build; a stale team feed whose rebuild fails is used as stored, and a
  missing one whose build fails fails the player build. The roster entry is
  read from the roster response in the source cache.
- `live` is taken from the live game of the player's team at serve time
  ([ADR 0021](../adr/0021-player-and-team-pages.md)): the game as the
  scoreboard knows it, and the player's line from that game's detail feed,
  null until he is in the box score. It is added when served and never
  stored. A live player request runs the 30-second refresh of the game and
  serves its detail feed, and waits at most 20 seconds in total.
- `detailAvailable` is set when the feed is served, true for the games the
  games job holds in the days shown, and not stored.
- A failed build keeps the stored feed and is listed under `feeds` in
  `/health`; it is not retried for 10 minutes on request.
- The feeds of players no longer on any roster are deleted after each run of
  the stars job, with no source request. Nothing is deleted before every
  roster has been fetched once.
- The builder is `build_player_feed` and the feed kind is `PlayerFeeds`, both
  in `api/app/jobs/player_feed.py`.

## Endpoint

- `GET /feeds/players/{id}.json` serves the feed through the on-demand cache
  with `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 404 with `{"detail": ...}` for an id found in no roster once every roster has been fetched, with no source request.
- It responds 503 with `{"detail": ...}` before every roster has been fetched once, when the request's 20 seconds end
  before a missing feed is built and after a failed build.
- A stale stored feed is served at once and rebuilt in the background. At
  most 4 feeds are built at once and one per feed.
- Every feed request records presence.
