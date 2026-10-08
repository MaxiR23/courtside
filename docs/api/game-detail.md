# Game detail feed

One game with everything the game detail page shows: teams, score, team
statistics, box score, standings and more.

## Schema

[`api/schemas/game-detail.schema.json`](../../api/schemas/game-detail.schema.json),
generated from the models in `api/app/feeds/game_detail.py`. When this page
and the models disagree, the models win. The route is decided in
[ADR 0019](../adr/0019-game-detail-route-and-feed.md) and kept by
[ADR 0020](../adr/0020-source-rules.md); its refresh and serving follow
[`docs/source-rules.md`](../source-rules.md).

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
| `Venue`               | `name`, `city` (null when the source has no city), `photoUrl` (null when unknown)                                                                                        |
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
| `Injury`              | `playerId` (the athlete id of the league injury report, null when the source gives none), `displayName`, `status` (`out`, `doubtful`, `questionable`, `probable`, `day-to-day`), `comment` (null when none)                            |
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
  game is never rebuilt after a successful build, also after a restart, so
  they stay null.
- `winProbability` has at least one point, in non-decreasing
  `elapsedSeconds` order. The feed's validator checks it.
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

- Nothing is built without a request, except a final game's build.
- A pre-game feed (scheduled, delayed, postponed, canceled) is built on
  request. It expires 12 hours after its build with tip-off more than 48 hours
  away, 6 hours with tip-off 12 to 48 hours away, and 3 hours with tip-off
  less than 12 hours away or already passed. A stored feed whose game changed
  status is stale.
- A live feed is built on request from the summary the games job fetched, so
  there is one source request per live game per interval. It is fresh until
  the games job refreshes the day again. A request that finds it stale waits
  for the rebuild, so the score is never older than 30 seconds. A detail
  request waits at most 20 seconds in total, shared by the games refresh and
  the rebuild; when they end, the stored feed is served.
- A final feed is built once by the games job at the final time and, after a
  failure, 2, 4 and 6 hours after it
  ([ADR 0010](../adr/0010-final-game-attempts.md)). It is stored and never
  built again. The last stored feed stays served until then, and a request
  answers 503 when none is stored.
- Standings, league injuries and team schedules are read through the source
  cache with a 1-hour freshness.
- Stars, highlights and the highlights search URL are added when the feed is
  served, not stored.
- A failed build keeps the stored feed and is listed under `feeds` in
  `/health`; it is not retried for 10 minutes on request.
- The stored feed of a game that leaves the days shown is deleted by the
  cleanup, with no source request.

## Endpoint

- `GET /feeds/games/{id}.json` serves the feed through the on-demand cache
  with `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 404 with `{"detail": ...}` for an id outside the days shown,
  with no source request.
- It responds 503 with `{"detail": ...}` before the days shown are loaded,
  when the request's 20 seconds end before a missing feed is built, after a
  failed build, and for a final game with no stored feed.
- After a day change whose new-day fetch fails, the games already loaded (the
  previous days shown and any new day fetched) keep being served, stored
  finals included. An id not loaded answers 503 until every day shown is
  loaded, and 404 after that.
- An invalid feed is never published: the previous valid one stays served.
- Every feed request records presence.
