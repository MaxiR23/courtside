# Games feed

The games for the days shown on the site, with scores, status and game
details.

## Schema

[`api/schemas/games.schema.json`](../../api/schemas/games.schema.json),
generated from the models in `api/app/feeds/games.py`. When this page and
the models disagree, the models win.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when unknown.
- Times are UTC, as ISO 8601 with a timezone.
- `Day.date` is the US Eastern date (ADR 0007, "Day boundary").

## Feed

| Field         | Type    | Meaning                               | Present |
| ------------- | ------- | ------------------------------------- | ------- |
| `generatedAt` | time    | When the feed was generated           | always  |
| `days`        | `Day[]` | The days shown; the list may be empty | always  |

## Day

| Field   | Type     | Meaning                                 | Present |
| ------- | -------- | --------------------------------------- | ------- |
| `date`  | date     | US Eastern date of the day              | always  |
| `games` | `Game[]` | Games of the day; the list may be empty | always  |

## Game

| Field                 | Type                   | Meaning                                                          | Present                         |
| --------------------- | ---------------------- | ---------------------------------------------------------------- | ------------------------------- |
| `id`                  | string                 | Game identifier                                                  | always                          |
| `away`, `home`        | `Team`                 | The two teams                                                    | always                          |
| `status`              | `GameStatus`           | `scheduled`, `live`, `final`, `delayed`, `postponed`, `canceled` | always                          |
| `startTime`           | time                   | Scheduled start, UTC                                             | always                          |
| `venue`               | string                 | Arena name                                                       | always                          |
| `stars`               | `Stars`                | The star of each team                                            | always                          |
| `highlights`          | `Highlight[]`          | Matched highlight videos, may be empty                           | always                          |
| `broadcast`           | string / null          | Broadcaster                                                      | null when unknown               |
| `period`              | integer / null         | Current period, 5 and up are overtimes                           | required when `live`            |
| `clock`               | string / null          | Game clock                                                       | required when `live`            |
| `lineScore`           | `LineScore` / null     | Points per period for each team                                  | required when `live` or `final` |
| `score`               | `Score` / null         | Current or final points                                          | required when `live` or `final` |
| `winner`              | team code / null       | Code of the winning team: the away or the home team              | required when `final`, null otherwise |
| `leaders`             | `Leaders` / null       | Top scorer of each team                                          | required when `live` or `final` |
| `teamStats`           | `GameTeamStats` / null | Team statistics                                                  | required when `live` or `final` |
| `highlightsSearchUrl` | URL / null             | Link to search for highlights                                    | required when `final`           |

A `live` game requires `period`, `clock`, `lineScore`, `score`, `leaders`
and `teamStats`. A `final` game requires `lineScore`, `score`, `winner`, `leaders`,
`teamStats` and `highlightsSearchUrl`; any other status has `winner` null.
The other statuses add nothing.

## Nested objects

| Object      | Fields                                                                                                      |
| ----------- | ----------------------------------------------------------------------------------------------------------- |
| `Team`      | `code` (three capital letters), `name`, `city`                                                              |
| `Player`    | `playerId`, `firstName`, `lastName`, `teamCode`, `photoUrl`                                                 |
| `Leader`    | `playerId`, `displayName` (as the source gives it), `teamCode`, `photoUrl`, `points`, `rebounds`, `assists` |
| `Star`      | `Player` fields plus `shortName`                                                                            |
| `TeamStats` | `fieldGoalPct`, `threePointPct` (0 to 1), `rebounds`, `assists`, `turnovers`                                |
| `Highlight` | `title`, `channel`, `thumbnailUrl`, `embedUrl`                                                              |
| `LineScore` | `away`, `home`: points per period, at least one, overtimes appended                                         |
| `Score`     | `away`, `home`: points                                                                                      |
| `Leaders`   | `away`, `home`: `Leader`                                                                                    |
| `Stars`     | `away`, `home`: `Star`                                                                                      |

Rules that live in the code:

- When two players tie on points, the leader is the first in the provider's
  order.
- `TeamStats.turnovers` counts the players' turnovers. Turnovers charged to
  the team are not included.
- Stars: the current season's averages are used when any player on the
  current roster has them; otherwise the previous season's are used. A 404
  from the averages source means that season has no statistics yet.
- `winner` is set by the games job from the final score: the team with more
  points. A final game whose score is tied has no winner, so the feed is
  invalid and the previous one stays published.

## Refresh behavior

Per ADR 0007: the schedule and stars once a day in the morning US
Eastern time; every minute from a game's scheduled start until it is live;
every 30 seconds while it is live; highlights one attempt 1, 2 and 3 hours
after the final time.

- The morning fetch runs at `DAILY_FETCH_TIME` (US Eastern, `HH:MM`, default
  06:00).
- Between US Eastern midnight and that fetch, the feed still holds the
  previous day's 7 days.
- A game's final time is stored when the job sees it go from scheduled, live
  or delayed to final. A game already final the first time the job sees it has
  no final time, so it gets no highlight attempts and shows only the search
  link.

## Endpoint

- `GET /feeds/games.json` serves the last published feed with
  `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 503 with `{"detail": ...}` before the first publication.
- An invalid feed is never published: the previous valid one stays served.
