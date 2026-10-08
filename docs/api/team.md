# Team feed

One team with everything the team page shows: identity, record, leaders,
roster, injuries and schedule.

## Schema

[`api/schemas/team.schema.json`](../../api/schemas/team.schema.json),
generated from the models in `api/app/feeds/team.py`. When this page and the
models disagree, the models win. The route is decided in
[ADR 0021](../adr/0021-player-and-team-pages.md); the feed is served at
`/feeds/teams/{code}.json`.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

The root is one team.

| Field        | Type                 | Meaning                                                   | Present                |
| ------------ | -------------------- | --------------------------------------------------------- | ---------------------- |
| `code`       | team code            | Three capital letters                                     | always                 |
| `city`, `name` | string             | Identity                                                  | always                 |
| `conference` | `Conference`         | `east` or `west`                                          | always                 |
| `division`   | string               | Division name                                             | always                 |
| `colors`     | `TeamColors`         | `primary`, `secondary`: hex values such as `#112233`      | always                 |
| `arena`      | `Venue`              | `name`, `city` (null), `photoUrl` (null), as in the [game detail feed](game-detail.md) | always |
| `coach`      | `Coach` / null       | `name`, `seasons`                                         | null when unknown      |
| `season`     | season label         | Such as `2026-27`                                         | always                 |
| `record`     | `TeamRecord`         | Record, splits, rank, playoff position and points         | always                 |
| `leaders`    | `TeamLeaders`        | Points, rebounds and assists leaders                      | always                 |
| `roster`     | `RosterPlayer[]`     | Ordered by number, unnumbered players last                | always, may be empty   |
| `injuries`   | `TeamInjury[]`       | Injury reports of the team                                | always, may be empty   |
| `nextGame`   | `NextGame` / null    | The next game, as in the [player feed](player.md)         | null when none         |
| `schedule`   | `Schedule` / null    | Games grouped for display                                 | null when no data      |

## Nested objects

| Object          | Fields                                                                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `TeamColors`    | `primary`, `secondary`                                                                                                                      |
| `Coach`         | `name`, `seasons`                                                                                                                           |
| `SplitRecord`   | `Record` fields (`wins`, `losses`) plus `winPct` (0 to 1)                                                                                   |
| `TeamRecord`    | `SplitRecord` fields plus `home`, `away`, `lastTen`: `SplitRecord`; `streak`: `Streak` / null; `gamesBehind`; `conferenceRank` (1 to 15); `divisionRank` (1 to 5); `playoff`: `PlayoffPosition` / null before the first game; `pointsFor`, `pointsAgainst`: `PointsTotal`; `differential`: `Differential` |
| `Streak`        | `kind` (`win`, `loss`), `count`                                                                                                             |
| `PlayoffPosition` | `status` (`seed`, `playin`, `out`), `seed`                                                                                                |
| `PointsTotal`   | `perGame`, `total`                                                                                                                          |
| `Differential`  | `perGame`, `total` (may be negative)                                                                                                        |
| `TeamLeaders`   | `season`; `points`, `rebounds`, `assists`: `TeamLeader` / null                                                                              |
| `TeamLeader`    | `playerId`, `name`, `number` (null), `position`, `photoUrl` (null), `value`                                                                 |
| `RosterPlayer`  | `id`, `name`, `number` (null), `position` (null), `height` (text, null), `weight` (lb, null), `age`, `birthDate`, `birthplace`, `college`, `experience` (0 is a rookie), `photoUrl`; each null when unknown; `status` (`active` or an injury status) |
| `TeamInjury`    | `playerId`, `name`, `number` (null), `position` (null), `status`, `comment` (null when none), `updatedAt`                                   |
| `Schedule`      | `groups`: `ScheduleGroup[]` in display order; `defaultGroup`                                                                                |
| `ScheduleGroup` | `key` (such as `2025-10` or `playoffs`), `games`: `ScheduleGame[]`                                                                          |
| `ScheduleGame`  | `gameId`, `startTime`, `opponent`, `isHome`, `kind`, `tag`, `result` (null), `teamScore`, `opponentScore` (null), `broadcast` (null), `isNext`, `detailAvailable` |

`GameTag` and `NextGame` are documented in the [player feed](player.md).

## Rules that live in the code

- Win percentages are from 0 to 1; counts are not negative.
- A playoff `seed` matches its `status`: `seed` 1 to 6, `playin` 7 to 10,
  `out` 11 to 15.
- Before the first game, `conferenceRank` is the team's place in the
  provider's list.
- A leader with no position, like a leader no longer on the roster, is null.
- `roster` is ordered by jersey number as an integer, equal numbers allowed
  (`0` and `00`), players with a null number last.
- `schedule.defaultGroup` is the `key` of a group, and at most one game has
  `isNext`.
- When `schedule` is not null, the `isNext` game and `nextGame` agree: both
  absent, or the same `gameId`.
- A `GameTag` whose note format is not recognized keeps its `kind` with
  null `conference`, `round` and `game`. The builder applies this rule.

## Refresh behavior

- Built on request under rule G of
  [`docs/source-rules.md`](../source-rules.md) and expiring as its table
  says: when the team has a final game whose final time plus 1 hour is after
  the build, and in any case 7 days after the build.
- The builder is `build_team_feed` in `api/app/jobs/team_feed.py`; the
  endpoint is pending: added by a later issue.
