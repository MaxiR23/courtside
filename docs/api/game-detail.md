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
| `Injuries`            | `away`, `home`: `Injury[]`                                                                                                                   |
| `Injury`              | `displayName`, `status` (`out`, `doubtful`, `questionable`, `probable`, `day-to-day`), `comment` (null when none)                            |
| `LastGames`           | `away`, `home`: `LastGame[]`                                                                                                                 |
| `LastGame`            | `date`, `opponent` (team code), `isHome`, `result` (`win`, `loss`), `teamScore`, `opponentScore`                                             |
| `Standings`           | `away`, `home`: `TeamStanding`                                                                                                               |
| `TeamStanding`        | `conference` (`east`, `west`), `conferenceRank`, `record`, `homeRecord`, `awayRecord`, `lastTen`: `Record`                                   |
| `SeasonSeries`        | `totalGames`, `awayWins`, `homeWins`, `games`: `SeriesGame[]`                                                                                |
| `SeriesGame`          | `date`, `away`, `home` (team codes), `score`: `Score`, `arena`                                                                               |
| `Video`               | `title`, `duration` (text), `thumbnailUrl` (null when none), `linkUrl`                                                                       |

Rules that live in the code:

- `injuries.away` or `home` empty means no injuries reported; `injuries`
  `null` means no data.
- `lastGames` lists at most five games per team, newest first; a list may be
  empty.
- `seasonSeries.games` empty is a first meeting; on a final game the list
  includes this game.
- `teamStats.leaders.<row>` is `null` on a tie; for `turnovers` the lower
  value leads.
- `winProbability` has at least one point.
