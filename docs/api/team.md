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
| `Coach`         | `name`, `seasons` (null)                                                                                                                    |
| `SplitRecord`   | `Record` fields (`wins`, `losses`) plus `winPct` (0 to 1)                                                                                   |
| `TeamRecord`    | `SplitRecord` fields plus `season` (label of the standings season, such as `2025-26`; in the preseason it is the previous season), `home`, `away`, `lastTen`: `SplitRecord`; `streak`: `Streak` / null; `gamesBehind`: games behind the leader of the team's conference (0 for the leader), null before the team's first game; `conferenceRank` (1 to 15); `divisionRank` (1 to 5); `playoff`: `PlayoffPosition` / null before the first game or without a seed; `pointsFor`, `pointsAgainst`: `PointsTotal`; `differential`: `Differential` |
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
| `ScheduleGame`  | `gameId`, `startTime`, `opponent`: `Opponent`, `isHome`, `kind`, `tag`, `result` (null), `teamScore`, `opponentScore` (null), `broadcast` (null), `isNext`, `detailAvailable` |

`GameTag`, `NextGame` and `Opponent` (the opponent of `NextGame` and of `ScheduleGame`) are documented in the [player feed](player.md).

## Rules that live in the code

- Win percentages are from 0 to 1; counts are not negative.
- `record.gamesBehind` is half the gap between the best wins minus losses of
  the team's conference and the team's own. It is computed by the same
  function as the conference rows of the [standings feed](standings.md), so
  both feeds give the same value: a standings row with a null value (the
  leader) is 0 here.
- A playoff `seed` matches its `status`: `seed` 1 to 6, `playin` 7 to 10,
  `out` 11 to 15.
- Before the first game, or without a seed, `conferenceRank` is the team's
  place in the provider's list.
- `record.season` can differ from `season`: the standings fall back to the
  last regular season (rule L of
  [`docs/source-rules.md`](../source-rules.md)).
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

- The id is the lowercase standard code (`okc`); any other id, such as `OKC`
  or `xyz`, is unknown and answers 404 with no source request.
- Nothing is built without a request: no job and no startup builds a team
  feed. The feed is stored at `feeds/teams/{code}.json` when first requested.
- Built on request under rule G of
  [`docs/source-rules.md`](../source-rules.md) and expiring as its table
  says: when the team has a final game whose final time plus 1 hour is after
  the build, and in any case 7 days after the build. The team's final games
  are the ones the games job holds and the games of the stored schedule that
  started after the build minus 1 day, so a game that already left the days
  shown still expires the feed.
- The sources read are the roster and the season leaders (24-hour
  freshness) and the team information, division standings, league injuries
  and season schedules (1-hour freshness), all through the source cache.
  The division standings add one request for the regular season when the
  configured one is not (rule L).
- `detailAvailable` is set when the feed is served, true for the games the
  games job holds in the days shown, and not stored.
- A failed build keeps the stored feed and is listed under `feeds` in
  `/health`; it is not retried for 10 minutes on request.
- Team feeds are never deleted.
- The builder is `build_team_feed` and the feed kind is `TeamFeeds`, both in
  `api/app/jobs/team_feed.py`.

## Endpoint

- `GET /feeds/teams/{code}.json` serves the feed through the on-demand cache
  with `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 404 with `{"detail": ...}` for a code that is not one of the 30 lowercase standard codes, with no source request.
- It responds 503 with `{"detail": ...}` when the request's 20 seconds end
  before a missing feed is built and after a failed build.
- A stale stored feed is served at once and rebuilt in the background. At
  most 4 feeds are built at once and one per feed.
- Every feed request records presence.
