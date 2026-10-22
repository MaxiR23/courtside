# Game detail feed

One game with everything the game detail page shows: teams, score, team
statistics, box score, standings and more.

## Schema

[`api/schemas/game-detail.schema.json`](../../api/schemas/game-detail.schema.json),
generated from the models in `api/app/feeds/game_detail.py`. When this page
and the models disagree, the models win. The route is decided in
[ADR 0019](../adr/0019-game-detail-route-and-feed.md) and kept by
[ADR 0020](../adr/0020-source-rules.md); its refresh and serving follow
[`docs/source-rules.md`](../source-rules.md). The detail of a past game follows
[ADR 0041](../adr/0041-past-game-detail.md); its schema is this one.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted, except the retired `videos` field, which is dropped when a stored feed is read ([ADR 0027](../adr/0027-no-game-videos-section.md)).
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

The root is one game.

| Field                 | Type                      | Meaning                                                          | Present                               |
| --------------------- | ------------------------- | ---------------------------------------------------------------- | ------------------------------------- |
| `id`                  | string                    | Game identifier                                                  | always                                |
| `status`              | `GameStatus`              | `scheduled`, `live`, `final`, `delayed`, `postponed`, `canceled` | always                                |
| `startTime`           | time                      | Scheduled start, UTC                                             | always                                |
| `venue`               | `Venue` / null            | Arena, city and photo                                            | null on a final game built without its summary ([ADR 0064](../adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md)) |
| `away`, `home`        | `DetailTeam`              | The two teams with their records                                 | always                                |
| `broadcast`           | string / null             | Broadcaster                                                      | null when unknown                     |
| `period`              | integer / null            | Current period, 5 and up are overtimes                           | required when `live`                  |
| `clock`               | string / null             | Game clock                                                       | required when `live`                  |
| `lineScore`           | `LineScore` / null        | Points per period for each team                                  | required when `live` or `final`, except a `final` All-Star game, which may have none ([ADR 0051](../adr/0051-all-star-notes-and-untimed-games.md)) |
| `score`               | `Score` / null            | Current or final points                                          | required when `live` or `final`       |
| `winner`              | `away` / `home` / null    | The side with more points                                        | required when `final`, null otherwise |
| `teamStats`           | `DetailGameTeamStats` / null | Team statistics and the leader of each row                    | required when `live`                  |
| `leaders`             | `Leaders` / null          | The leader of each team, as in the [games feed](games.md) ([ADR 0057](../adr/0057-past-game-detail-leaders.md)) | set on a past game with a box score whose two sides have stat lines; null on a current game and when the box score lacks them |
| `stars`               | `Stars` / null            | The star of each team                                            | null when no data                     |
| `boxScore`            | `BoxScore` / null         | Player lines and totals for each team                            | null when no data                     |
| `winProbability`      | `WinProbabilityPoint[]` / null | Home win probability over the game, at least one point      | null when no data                     |
| `winProbabilityLeader` | `WinProbabilityLeader` / null | The team ahead at the latest win probability point and its win probability | null when even or no win probability |
| `winProbabilityPeriods` | `WinProbabilityPeriods` / null | Each period's start and the game's end, in elapsed seconds | null when no win probability |
| `injuries`            | `Injuries` / null         | Injury reports of each team                                      | null when no data or the read failed  |
| `lastGames`           | `LastGames` / null        | Latest games of each team                                        | null when no data                     |
| `standings`           | `Standings` / null        | Conference standing of each team                                 | null when no data or the read failed; a league side the standings lack has a null standing |
| `seasonSeries`        | `SeasonSeries` / null     | Games between the two teams this season                          | null when no data                     |
| `highlights`          | `Highlight[]` / null      | Matched highlight videos, as in the [games feed](games.md)       | null when no data                     |
| `highlightsSearchUrl` | URL / null                | Link to search for highlights, as in the [games feed](games.md)  | null when no data                     |
| `cup`                 | `GameCup` / null          | The Cup mark, as in the [games feed](games.md)                   | null when the game is not a Cup game  |
| `postseason`          | `GamePostseason` / null   | The play-in or playoff mark, as in the [games feed](games.md)    | null when the game is neither, and when a stored feed was written before the mark |
| `allStar`             | `GameAllStar` / null      | The All-Star mark, as in the [games feed](games.md)              | null when the game is not an All-Star game, and when a stored feed was written before the mark |
| `seasonLabel`         | string / null             | The game's season label, such as `2004-05`                       | set on a past game, null on a game of the days shown, and when a stored feed was written before the field |
| `buildVersion`        | integer / null            | The rules version of a kept past game detail ([ADR 0053](../adr/0053-season-level-rules-for-past-seasons.md)) | null on a current game and on a stored feed from before the field |

For every optional section, `null` means the source has no data for it: the
page hides the section and its tab (`docs/design-game-detail.md`, "A section
with no data is hidden, together with its tab").

A `live` game requires `period`, `clock`, `lineScore`, `score` and
`teamStats`. A `final` game requires `lineScore` (not a final All-Star game),
`score` and `winner`. Any
other status has `winner` null. Every stat leader is a side, `away` or
`home`.

`stars` uses the `Stars` model of the [games feed](games.md).

## Nested objects

| Object                | Fields                                                                                                                                       |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `Opponent`            | `code` (null for a guest without one), `name`, `city` (null when the source sends none), `guest`; as in the [games feed](games.md) ([ADR 0026](../adr/0026-one-guest-team-rule.md)); `logo` and `colors`, as in the [games feed](games.md) ([ADR 0068](../adr/0068-shared-team-identity-and-hero-accents.md)) |
| `Record`              | `wins`, `losses`                                                                                                                             |
| `DetailTeam`          | `GameTeam` fields (`code`, null for a guest without one, `name`, `city`, `guest`; `city` is null for a guest the source sends without one, such as an All-Star team) plus `record` (null for a guest, and for a league side the standings lack); `logo` and `colors` as in the games feed |
| `Venue`               | `name`, `city` (null when the source has no city), `photoUrl` (null when unknown)                                                                                        |
| `DetailTeamStats`     | `TeamStats` fields (`fieldGoalPct`, `threePointPct`, `rebounds`, `assists`, `turnovers`) plus `freeThrowPct` (0 to 1), `steals`, `blocks`; the three percentages and every count are null when the source sends none ([ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)) |
| `TeamStatLeaders`     | one side (`away` or `home`) or null per row: `fieldGoalPct`, `threePointPct`, `freeThrowPct`, `rebounds`, `assists`, `turnovers`, `steals`, `blocks`       |
| `DetailGameTeamStats` | `away`, `home`: `DetailTeamStats`; `leaders`: `TeamStatLeaders`                                                                              |
| `BoxScore`            | `away`, `home`: `TeamBoxScore`                                                                                                               |
| `TeamBoxScore`        | `players`: `BoxScorePlayer[]`; `totals`: `BoxScoreTotals`                                                                                    |
| `BoxScorePlayer`      | `playerId`, `displayName`, `starter`, `minutes` (text), `plusMinus` (null on every row of a game whose players all have 0), `photoUrl` (null only for a guest player without a headshot) plus the counting stats of `BoxScoreTotals`; `minutes` is null when the source has no minutes column                   |
| `BoxScoreTotals`      | `points`, `fieldGoalsMade`, `fieldGoalsAttempted`, `threePointsMade`, `threePointsAttempted`, `freeThrowsMade`, `freeThrowsAttempted`, `offensiveRebounds`, `defensiveRebounds`, `rebounds`, `assists`, `turnovers`, `steals`, `blocks`, `fouls` (each null when the source sends none, [ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)), plus `fieldGoalPct`, `threePointPct`, `freeThrowPct` (0 to 1; null when the source sends none) |
| `WinProbabilityPoint` | `elapsedSeconds`, `homeWinProbability` (0 to 1)                                                                                              |
| `WinProbabilityLeader` | `side` (`away` or `home`), `winProbability` (0 to 1, above 0.5) |
| `GamePeriod`          | `number`, `startElapsedSeconds`                                                                                                              |
| `WinProbabilityPeriods` | `periods`: `GamePeriod[]`, `endElapsedSeconds`                                                                                             |
| `Injuries`            | `away`, `home`: `Injury[]`, null for a guest side                                                                                                                  |
| `Injury`              | `playerId` (the athlete id of the league injury report, null when the source gives none), `displayName`, `status` (`out`, `doubtful`, `questionable`, `probable`, `day-to-day`), `comment` (null when none)                            |
| `LastGames`           | `away`, `home`: `LastGame[]`, null for a guest side                                                                                                                |
| `LastGame`            | `date`, `opponent`: `Opponent` (a league code, or a guest with its name and, when the source sends one, its code), `isHome`, `result` (`win`, `loss`), `teamScore`, `opponentScore`                                             |
| `Standings`           | `away`, `home`: `TeamStanding`, null for a guest side                                                                                                              |
| `TeamStanding`        | `conference` (`east`, `west`), `conferenceRank`, `record`, `homeRecord`, `awayRecord`, `lastTen`: `Record`                                   |
| `SeasonSeries`        | `totalGames`, `awayWins`, `homeWins`, `leader` (team code, null on a tie or before any game), `games`: `SeriesGame[]`                    |
| `SeriesGame`          | `date`, `away`, `home` (team codes), `isCurrent`, `score`: `Score` / null, `winner` (team code / null), `arena` (null when neither team schedule nor the current game knows it)                             |

Rules that live in the code:

The feed's validators do not check two of these rules: the tie and
turnover direction of `teamStats.leaders`, and which games
`seasonSeries.games` holds. The source adapter applies them when it
builds the feed.

- A guest side ([ADR 0025](../adr/0025-guest-teams.md)) has a null `record`,
  `standings`, `injuries`, `lastGames` and `stars` side, each null exactly
  when the side is a guest. `seasonSeries` is null on a guest game, and a
  guest side's schedule is never fetched.
- A league side's `standing` and `record` are null when the standings read
  failed or lack the team ([ADR 0064](../adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md));
  a guest side's stay null.
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
- `teamStats.leaders.<row>` is `null` on a tie, and when either team's value is
  null; for `turnovers` the lower value leads.
- Team turnovers, in `teamStats` and `boxScore.totals.turnovers`, are the team's
  `totalTurnovers` when the source sends it, else `turnovers`
  ([ADR 0052](../adr/0052-box-score-reading.md)).
- When every player of both teams has a plus-minus of 0, `plusMinus` is `null`
  on every row, and the game page hides the column. One non-zero value keeps
  every value as sent.
- A team percentage the source does not send is null in `teamStats` and
  `boxScore.totals`. A missing count stat still fails the build.
- On a `final` game, `teamStats` and `boxScore` are null together when
  the source had no player statistics when the feed was built. A final
  game is never rebuilt after a successful build, also after a restart, so
  they stay null.
- `winProbability` has at least one point, in non-decreasing
  `elapsedSeconds` order. The feed's validator checks it.
- `winProbabilityLeader` is read off the last point of `winProbability` in feed
  order: the `home` side with that point's `homeWinProbability` above 0.5, the
  `away` side with 1 minus it below 0.5, null on exactly 0.5 and null without
  `winProbability`. The feed's validator checks it.
- `winProbabilityPeriods` exists only with `winProbability`. Periods are
  numbered from 1, the first starts at 0, and starts increase. Every point
  is at or before `endElapsedSeconds`. Period lengths come from the
  provider's game format. The number of periods is the regulation count or
  the highest period played, whichever is higher.

## Past games

A final game of a stored [day feed](days.md) that the games job has not loaded
is served on the same route, with the same schema
([ADR 0041](../adr/0041-past-game-detail.md)). Any other id keeps the rules
above. A game of a day feed that is not final answers 404. A game that a past
team or player feed registered with its date is known too: the day feed of that
date is built first, and a game that day does not list as final answers 503
([ADR 0053](../adr/0053-season-level-rules-for-past-seasons.md)).

- The game's status, start time, broadcast, line score, score, winner, marks
  (`cup`, `postseason`, `allStar`), sides and `highlightsSearchUrl` come from the
  stored day feed. The sides are resolved by team id first, with the event's name
  and city; an unknown id is a guest. The marks are those of the day feed.
- The `venue`, `boxScore`, `teamStats`, `leaders`, `winProbability`,
  `winProbabilityLeader` and `winProbabilityPeriods` come from one game detail
  summary, the one read of the build, in a budget of 1
  ([ADR 0059](../adr/0059-bounded-past-page-reads.md)). The `leaders` follow the
  rule of ADR 0009. Each is null when the summary lacks it.
- `seasonLabel` is set from the summary's season. A summary without a readable
  season fails the build.
- `stars`, `injuries`, `lastGames`, `standings` and `seasonSeries` are null,
  and so is each side's `record`: they describe today, and the source reads no
  record of a past game. `highlights` is the stored highlight added when
  served, as a list of one, and null without one or on an All-Star game
  ([ADR 0048](../adr/0048-highlights-backfill-and-edition-video.md), [ADR 0065](../adr/0065-background-work-limited-to-games-highlights-and-stars.md)).

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
  answers 503 when none is stored. After the fourth failed attempt, the feed
  is built once, on the games job's last slot or on request, with the summary
  sections (`venue`, `teamStats`, `boxScore`, `winProbability` and
  `seasonSeries`) null ([ADR 0064](../adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md)).
- A past game's feed is built once on request, stored as its own kind and kept.
  It is never refreshed, and the games job never touches it. It is deleted when not served in 90 days and rebuilt on its next request ([ADR 0063](../adr/0063-bounded-state-and-kept-feeds.md)). A
  failed build answers 503 while nothing is stored and is not retried for 10
  minutes. A stored feed without the `leaders` key is stale: it is served, then
  rebuilt on its next request ([ADR 0057](../adr/0057-past-game-detail-leaders.md)).
- Standings, league injuries and team schedules are read through the source
  cache with a 1-hour freshness.
- The build is under a read budget of 5 that counts reads only: a rate-limited read fails as an ordinary one ([ADR 0067](../adr/0067-read-budgets-of-every-on-demand-build.md)).
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
- It responds 404 with `{"detail": ...}` for an id outside the days shown that
  is not a final game of a stored day feed, with no source request. The final
  games of the stored day feeds are indexed in memory at startup and whenever a
  day feed is published, so the check reads no file
  ([ADR 0066](../adr/0066-cut-read-amplification-of-on-demand-builds.md)).
- It responds 503 with `{"detail": ...}` before the days shown are loaded,
  when the request's 20 seconds end before a missing feed is built, after a
  failed build, and for a final game with no stored feed. It also responds 503
  for a past game whose build failed or is still running.
- After a day change whose new-day fetch fails, the games already loaded (the
  previous days shown and any new day fetched) keep being served, stored
  finals included. An id not loaded answers 503 until every day shown is
  loaded, and 404 after that.
- An invalid feed is never published: the previous valid one stays served.
- Every feed request records presence.

## Missing stats and rows without an id

A team or player stat the source does not carry is null, never a failure; a value
that is sent and is not a number still fails the read. A box score row with no
player id is skipped and logged once per game read, in the live, the past and the
past-players readers ([ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)).
