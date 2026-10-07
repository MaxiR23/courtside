# Game detail feed

One game with everything the game detail page shows: teams, score, team
statistics, box score, standings and more.

## Schema

[`api/schemas/game-detail.schema.json`](../../api/schemas/game-detail.schema.json),
generated from the models in `api/app/feeds/game_detail.py`. When this page
and the models disagree, the models win. The route and the feed are decided
in [ADR 0019](../adr/0019-game-detail-route-and-feed.md).

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

The root is one game.

| Field                 | Type                      | Meaning                                                          | Present                               |
| --------------------- | ------------------------- | ---------------------------------------------------------------- | ------------------------------------- |
| `id`                  | string                    | Game identifier                                                  | always                                |
| `status`              | `GameStatus`              | `scheduled`, `live`, `final`, `delayed`, `postponed`, `canceled` | always                                |
| `startTime`           | time                      | Scheduled start, UTC                                             | always                                |
| `venue`               | `Venue`                   | Arena, city and photo                                            | always                                |
| `away`, `home`        | `DetailTeam`              | The two teams with their records                                 | always                                |
| `broadcast`           | string / null             | Broadcaster                                                      | null when unknown                     |
| `period`              | integer / null            | Current period, 5 and up are overtimes                           | required when `live`                  |
| `clock`               | string / null             | Game clock                                                       | required when `live`                  |
| `lineScore`           | `LineScore` / null        | Points per period for each team                                  | required when `live` or `final`       |
| `score`               | `Score` / null            | Current or final points                                          | required when `live` or `final`       |
| `winner`              | team code / null          | Code of the winning team: the away or the home team              | required when `final`, null otherwise |
| `teamStats`           | `DetailGameTeamStats` / null | Team statistics and the leader of each row                    | required when `live`                  |
| `stars`               | `Stars` / null            | The star of each team                                            | null when no data                     |
| `boxScore`            | `BoxScore` / null         | Player lines and totals for each team                            | null when no data                     |
| `winProbability`      | `WinProbabilityPoint[]` / null | Home win probability over the game, at least one point      | null when no data                     |
| `winProbabilityLeader` | `WinProbabilityLeader` / null | The team ahead at the latest win probability point and its win probability | null when even or no win probability |
| `winProbabilityPeriods` | `WinProbabilityPeriods` / null | Each period's start and the game's end, in elapsed seconds | null when no win probability |
| `injuries`            | `Injuries` / null         | Injury reports of each team                                      | null when no data                     |
| `lastGames`           | `LastGames` / null        | Latest games of each team                                        | null when no data                     |
| `standings`           | `Standings` / null        | Conference standing of each team                                 | null when no data                     |
| `seasonSeries`        | `SeasonSeries` / null     | Games between the two teams this season                          | null when no data                     |
| `highlights`          | `Highlight[]` / null      | Matched highlight videos, as in the [games feed](games.md)       | null when no data                     |
| `highlightsSearchUrl` | URL / null                | Link to search for highlights, as in the [games feed](games.md)  | null when no data                     |
| `videos`              | `Video[]` / null          | Related videos                                                   | null when no data                     |

For every optional section, `null` means the source has no data for it: the
page hides the section and its tab (`docs/design-game-detail.md`, "A section
with no data is hidden, together with its tab").

A `live` game requires `period`, `clock`, `lineScore`, `score` and
`teamStats`. A `final` game requires `lineScore`, `score` and `winner`. Any
other status has `winner` null. Every stat leader is the away or the home
code.

`stars` uses the `Stars` model of the [games feed](games.md).

## Nested objects

| Object                | Fields                                                                                                                                       |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `Record`              | `wins`, `losses`                                                                                                                             |
| `DetailTeam`          | `Team` fields (`code`, `name`, `city`) plus `record`                                                                                         |
| `Venue`               | `name`, `city`, `photoUrl` (null when unknown)                                                                                               |
| `DetailTeamStats`     | `TeamStats` fields (`fieldGoalPct`, `threePointPct`, `rebounds`, `assists`, `turnovers`) plus `freeThrowPct` (0 to 1), `steals`, `blocks`    |
| `TeamStatLeaders`     | one team code or null per row: `fieldGoalPct`, `threePointPct`, `freeThrowPct`, `rebounds`, `assists`, `turnovers`, `steals`, `blocks`       |
| `DetailGameTeamStats` | `away`, `home`: `DetailTeamStats`; `leaders`: `TeamStatLeaders`                                                                              |
| `BoxScore`            | `away`, `home`: `TeamBoxScore`                                                                                                               |
| `TeamBoxScore`        | `players`: `BoxScorePlayer[]`; `totals`: `BoxScoreTotals`                                                                                    |
| `BoxScorePlayer`      | `playerId`, `displayName`, `starter`, `minutes` (text), `plusMinus`, `photoUrl` plus the counting stats of `BoxScoreTotals`                   |
| `BoxScoreTotals`      | `points`, `fieldGoalsMade`, `fieldGoalsAttempted`, `threePointsMade`, `threePointsAttempted`, `freeThrowsMade`, `freeThrowsAttempted`, `offensiveRebounds`, `defensiveRebounds`, `rebounds`, `assists`, `turnovers`, `steals`, `blocks`, `fouls`, plus `fieldGoalPct`, `threePointPct`, `freeThrowPct` (0 to 1) |
| `WinProbabilityPoint` | `elapsedSeconds`, `homeWinProbability` (0 to 1)                                                                                              |
| `WinProbabilityLeader` | `teamCode` (the away or the home code), `winProbability` (0 to 1, above 0.5) |
| `GamePeriod`          | `number`, `startElapsedSeconds`                                                                                                              |
| `WinProbabilityPeriods` | `periods`: `GamePeriod[]`, `endElapsedSeconds`                                                                                             |
| `Injuries`            | `away`, `home`: `Injury[]`                                                                                                                   |
| `Injury`              | `displayName`, `status` (`out`, `doubtful`, `questionable`, `probable`, `day-to-day`), `comment` (null when none)                            |
| `LastGames`           | `away`, `home`: `LastGame[]`                                                                                                                 |
| `LastGame`            | `date`, `opponent` (team code), `isHome`, `result` (`win`, `loss`), `teamScore`, `opponentScore`                                             |
| `Standings`           | `away`, `home`: `TeamStanding`                                                                                                               |
| `TeamStanding`        | `conference` (`east`, `west`), `conferenceRank`, `record`, `homeRecord`, `awayRecord`, `lastTen`: `Record`                                   |
| `SeasonSeries`        | `totalGames`, `awayWins`, `homeWins`, `leader` (team code, null on a tie or before any game), `games`: `SeriesGame[]`                    |
| `SeriesGame`          | `date`, `away`, `home` (team codes), `isCurrent`, `score`: `Score` / null, `winner` (team code / null), `arena`                             |
| `Video`               | `title`, `duration` (text), `thumbnailUrl` (null when none), `linkUrl`                                                                       |

Rules that live in the code:

The feed's validators do not check two of these rules: the tie and
turnover direction of `teamStats.leaders`, and which games
`seasonSeries.games` holds. The source adapter applies them when it
builds the feed.

- `injuries.away` or `home` empty means no injuries reported; `injuries`
  `null` means no data.
- `lastGames` lists at most five games per team, newest first; a list may be
  empty.
- `seasonSeries.games` holds the completed games and this game, when the
  source lists it, in the source's order.
- A completed game has `score` and `winner`. This game is the one with
  `isCurrent`, and has null `score` and `winner` until the source reports it
  completed.
- `seasonSeries.leader` is the team with more wins, null on equal wins.
- No completed game is a first meeting.
- `teamStats.leaders.<row>` is `null` on a tie; for `turnovers` the lower
  value leads.
- On a `final` game, `teamStats` and `boxScore` are null together when
  the source had no player statistics when the feed was built. A final
  game is not rebuilt after a successful build (except once after a
  restart, see "Refresh behavior"), so they stay null.
- `winProbability` has at least one point.
- `winProbabilityLeader` is read off the last point of `winProbability` in feed
  order: the home team with that point's `homeWinProbability` above 0.5, the
  away team with 1 minus it below 0.5, null on exactly 0.5 and null without
  `winProbability`. The feed's validator checks it.
- `winProbabilityPeriods` exists only with `winProbability`. Periods are
  numbered from 1, the first starts at 0, and starts increase. Every point
  is at or before `endElapsedSeconds`. Period lengths come from the
  provider's game format. The number of periods is the regulation count or
  the highest period played, whichever is higher.

## Known cases

A completed series event without a winner flag fails that game's build, and
that game's last valid feed stays served. This is revisited only with a
recorded response that shows it.

## Refresh behavior

- A live game is rebuilt every 30 seconds.
- A final game is built at its final time and, after a failure, 2, 4 and 6
  hours after it, never after a success
  ([ADR 0010](../adr/0010-final-game-attempts.md)). The attempts are kept in
  memory, so after a restart a final game is built once more.
- Any other status (scheduled, delayed, postponed, canceled) is rebuilt every
  hour.
- Standings and league injuries are fetched once per run, and a team schedule
  at most once per run, only when a game is due.
- A feed is republished with no source call when its stars, highlights or
  highlights search URL change.
- A failed build keeps that game's last valid feed and never blocks the other
  games.
- The feed of a game that leaves the days shown is deleted.
- The job runs in its own task, apart from the games job, as the stars
  job does ([ADR 0014](../adr/0014-star-guarantees.md)).

## Endpoint

- `GET /feeds/games/{id}.json` serves the last published feed of the game with
  `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 404 with `{"detail": ...}` when no feed is published for that id.
- An invalid feed is never published: the previous valid one stays served.
