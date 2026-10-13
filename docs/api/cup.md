# Cup feed

The NBA Cup: the draw, the six group tables, the wild card standings, the
knockout bracket and every Cup game, with every value ready to draw.

## Schema

[`api/schemas/cup.schema.json`](../../api/schemas/cup.schema.json), generated
from the models in `api/app/feeds/cup.py`. When this page and the models
disagree, the models win. The route is decided in
[ADR 0028](../adr/0028-cup-feed.md); the feed is served at `/feeds/cup.json`.
The data of the matchup panel is the [Cup matchup feed](cup-matchup.md), one
per slot id.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone; dates are US Eastern dates.
- Labels are keys and parts (conference, letter, seed), never prose: the page
  writes the words.
- Every team is an `Opponent`, as in the [games feed](games.md).

## Feed

| Field              | Type               | Meaning                                                              | Present |
| ------------------ | ------------------ | -------------------------------------------------------------------- | ------- |
| `season`           | season label       | Such as `2026-27`                                                    | always  |
| `drawn`            | boolean            | Whether the six groups have their teams                              | always  |
| `stage`            | `CupStage`         | `draw`, `group`, `quarterfinals`, `semifinals`, `championship`, `complete` | always |
| `firstGameDate`    | date / null        | The first group game                                                 | null when no group game is scheduled |
| `groupGamesPlayed` | integer (0 to 60)  | Final group games                                                    | always  |
| `groupGamesTotal`  | integer            | Always 60                                                            | always  |
| `champion`         | `Opponent` / null  | The winner of the championship                                       | set exactly when `stage` is `complete` |
| `stages`           | `StageEntry[]`     | Exactly 4, in the order group, quarterfinals, semifinals, championship | always |
| `groups`           | `CupGroup[]`       | Exactly 6: East A to C, then West A to C                             | always  |
| `wildCard`         | `WildCardTable[]`  | East then West                                                       | always  |
| `bracket`          | `BracketSlot[]`    | Exactly 7, in the order of `SlotId`                                  | always  |
| `games`            | `CupGames`         | Every Cup game by day, with counts                                   | always  |

## Nested objects

| Object           | Fields                                                                                                                                                                  |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CupRound`       | `group`, `quarterfinals`, `semifinals`, `championship`: the round of a game, a stage entry or a slot (also the `stage` of the `GameCup` mark on the games and game detail feeds) |
| `CupGroupName`   | `conference` (`east`, `west`), `letter` (`A`, `B`, `C`): the one shape of a group label                                                                                  |
| `StageEntry`     | `stage`: `CupRound`; `status`: `StageStatus` (`complete`, `in_progress`, `next`, `upcoming`); `firstDate`, `lastDate`: dates of the round's games, both set or both null  |
| `CupGroup`       | `name`: `CupGroupName`; `teams`: `Opponent[]` (up to 5, empty before the draw); `rows`: `GroupRow[]` (up to 5, empty before the first table); `gamesFinal` (0 to 10); `final` (true exactly when `gamesFinal` is 10) |
| `GroupRow`       | `position` (1 to 5, null); `team`: `Opponent`; `wins`, `losses`; `gamesBehind` (one decimal, null for the leader or when unknown); `differential`: `PerGameDifferential` / null; `total`: `TotalDifferential` / null; `streak`: `Streak` / null; `pointsFor`, `pointsAgainst` (integers, null); `home`, `away`, `overtime`: records such as `2-1` (null); `tag`: `CupTag` / null |
| `CupTag`         | `won_group`, `wild_card`, `eliminated`: from the clinch letter only; null with no clinch                                                                                 |
| `WildCardTable`  | `conference`; `rows`: `WildCardRow[]`                                                                                                                                    |
| `WildCardRow`    | `rank` (from 1); `team`: `Opponent`; `group`: `CupGroupName` / null; `wins`, `losses`; `total`: `TotalDifferential` / null; `pointsFor` (null); `tag`: `CupTag` / null   |
| `CupGames`       | `days`: `CupDay[]` by date; `counts`: `StageCounts`                                                                                                                      |
| `CupDay`         | `date`; `games`: `CupGame[]` (at least one) by start time, then id                                                                                                       |
| `StageCounts`    | `all` (the sum of the rounds), `group`, `quarterfinals`, `semifinals`, `championship`                                                                                    |
| `CupGame`        | `id`; `stage`: `CupRound`; `date` (US Eastern); `startTime`; `away`, `home`: `Opponent`; `status`: `GameStatus`; `score`: `Score` / null (set only when final); `winner` (`away`, `home`, null); `broadcast` (null); `venue`; `city` (null); `neutralSite`; `countsInStandings`; `detailAvailable` |
| `BracketSlot`    | `id`: `SlotId`; `round`: `CupRound`; `conference` (null for the final only); `top`, `bottom`: `SlotSide`; `game`: `CupGame` / null                                      |
| `SlotId`         | `east-qf-1`, `east-qf-2`, `east-sf`, `final`, `west-sf`, `west-qf-1`, `west-qf-2`                                                                                        |
| `SlotSide`       | `label`: `SlotLabel`; `rule`: `SlotRule`; `known`; `team`: `Opponent` / null; `projected`: `Projection` / null (never both a team and a projection)                      |
| `SlotLabel`      | `key`: `SlotLabelKey` (`seed`, `wild_card`, `quarterfinal_winner`, `semifinal_winner`); `conference`; `seed` (1 to 3, null); `quarterfinal` (1 to 2, null)                |
| `SlotRule`       | `best_group_winner`, `second_best_group_winner`, `third_best_group_winner`, `best_non_winner`, `quarterfinal_winner`, `semifinal_winner`                                 |
| `Projection`     | `team`: `Opponent`, `wins`, `losses`: the team that leads today, drawn as "Currently XXX (W-L)"                                                                          |
| `GameCup`        | `stage`: `CupRound`: the mark on the games feed and the game detail feed                                                                          |
| `TeamCup`        | `group`: `CupGroupName`, `wins`, `losses`: the mark on the team feed                                                                                                      |

`PerGameDifferential`, `TotalDifferential`, `Streak` and `Opponent` are as in
the [standings feed](standings.md), the [team feed](team.md) and the
[games feed](games.md).

## Rules that live in the code

1. **Teams.** A team's name and city come from the 30 schedules, where every
   league team appears as an opponent. A team no schedule shows has a null name
   and city.
2. **Games.** A Cup game is a schedule game whose note names a round. It is read
   from both teams' schedules and listed once, by game id: home is the team
   whose view is home. `status` is `final` when the game is completed, `live`
   while in progress, `postponed` when over but not completed, and `scheduled`
   otherwise. `winner` is the side with more points when final. `date` is the
   US Eastern date. `neutralSite` is true for the semifinals and the
   championship; `countsInStandings` is false for the championship only.
   `score` is set only for a final game. It is null while scheduled, live or
   postponed, because the schedules carry scores only for completed games.
   `detailAvailable` is set when the feed is served, from the games of the days
   shown, and is false in the stored file.
3. **Drawn.** `drawn` is true when every group has teams. Before that every
   group has empty `teams` and `rows`, the wild card tables are empty and the
   stage is `draw`.
4. **Group games.** A group game belongs to a group when both teams are in it.
   `gamesFinal` counts its final games and `final` is `gamesFinal == 10`.
   `groupGamesPlayed` is the sum of the groups' `gamesFinal`.
5. **A round is final** when it has all its games (group 60, quarterfinals 4,
   semifinals 2, championship 1) and every one is final. A round with no game
   or fewer than its full count is not final.
6. **Stage.** `draw` when no table has rows. `group` when there are rows and
   either no quarterfinal is scheduled or the group round is not final. Then the
   earliest of `quarterfinals`, `semifinals` and `championship` that is not
   final, and `complete` once the championship is final.
7. **Stages.** The dates are the first and last US Eastern date of the round's
   games, null with no game. Rounds before the current stage are `complete`,
   the current one is `in_progress`, the next is `next` and the rest are
   `upcoming`. Before the draw the group round is `next`.
8. **Group rows** keep the table's order. `position` is the table's seed (0 or
   none is null). `gamesBehind` is the table's text with one decimal and a dash
   is null. The differentials are signed (`+` and the minus sign U+2212, zero
   has no sign): the per game value to one decimal, the total to a whole
   number. `home`, `away` and `overtime` are kept only when they are records
   such as `2-1`. `tag` comes from the clinch letter only: `y` is `won_group`,
   `x` is `wild_card`, `e` is `eliminated`; an unknown letter is null and is
   logged with the team code.
9. **Seeds.** Rows 1 to 3 of a conference table are seeds 1 to 3 and row 4 is
   the wild card.
10. **Wild card.** Per conference, East then West: the conference table's rows
    from the fourth on, ranked from 1. `group` is the team's group.
11. **Bracket.** The 7 slots in `SlotId` order. Unscheduled sides carry these
    labels and rules:
    - Quarterfinal 1: top is seed 1 (`best_group_winner`), bottom is the wild
      card (`best_non_winner`).
    - Quarterfinal 2: top is seed 2 (`second_best_group_winner`), bottom is
      seed 3 (`third_best_group_winner`).
    - Semifinal: top is the winner of quarterfinal 1, bottom the winner of
      quarterfinal 2 (`quarterfinal_winner`).
    - Final: top is the East semifinal winner, bottom the West semifinal winner
      (`semifinal_winner`).
12. **Quarterfinal sides.** While the group round is not final and the table has
    rows, `projected` is the seed's team with its record and `known` is false.
    Once the group round is final, `known` is true, `team` is the seed's team
    and `projected` is null.
13. **Semifinal and final sides.** `known` is true and `team` is the winner when
    the feeder slot's game is final.
14. **Scheduled games.** A quarterfinal goes to its conference (from the draw),
    to `qf-1` when one of its teams is the conference's seed 1 or wild card, and
    to `qf-2` otherwise. A semifinal goes to its conference's `sf`, and the
    championship to `final`. A scheduled slot has `game` set, its sides' `team`
    from the game and `projected` null. `top` is the game's team that matches the
    top feeder (the seed, the quarterfinal 1 winner, the East team), else the
    home team. Two games in one slot, or a knockout team outside the draw, fail
    the build.
15. **Games list.** `days` by date, games by start time then id. Knockout slots
    with no game add nothing.
16. **Champion.** When `complete`, the winner of the championship.

The note of a game maps to its round:

| Note                      | Round           |
| ------------------------- | --------------- |
| `NBA Cup - Group Play`    | `group`         |
| `NBA Cup - Quarterfinals` | `quarterfinals` |
| `NBA Cup - Semifinals`    | `semifinals`    |
| `NBA Cup Championship`    | `championship`  |

Any other note is not a Cup game. The `cup` mark of the games, game detail and
team feeds uses the same round values.

The two Cup settings must return these payloads:

- `CUP_GROUP_URL` (with `{season}` and `{group}`): the teams collection of a
  group, an object with `items`, each `{"$ref": ...}` whose path has the
  provider's team id after `teams`. Links are never followed.
- `CUP_GROUP_STANDINGS_URL` (with `{season}` and `{group}`): the Cup table, an
  object with `name` (`inseason`) and `standings`, each row with a team link and
  `records`. The record of type `inseason` holds the `wins` and `losses` stats
  (required) and `playoffSeed`, `gamesBehind`, `differential`,
  `pointDifferential`, `pointsFor`, `pointsAgainst`, `streak`, `OTWins`,
  `OTLosses` and `clincher` (optional); the records of type `home` and `road`
  hold those records. A group id is fixed in the backend; the teams in a group
  change each season.

Edge cases: before the draw, a draw with no table rows, a round with fewer games
than its full count, a team no schedule shows, a row with only wins and losses,
and a row with no clinch are all valid.

## Refresh behavior

- The only id is `league`; the feed is stored at `feeds/cup/league.json`.
- Nothing is built without a request: no job and no startup builds the feed.
- The season is the end year of the latest roster the stars job fetched. When
  none was fetched and nothing is stored, the endpoint answers 503.
- Built on request under rule G of [`docs/source-rules.md`](../source-rules.md)
  and expiring as its table says: when any Cup game has a final time plus 1 hour
  after the build, and in any case 7 days after the build. Once the championship
  is final the feed is kept while its season is the current one, and expires
  under the normal rules when the season changes.
- The sources read are the teams and the table of each of the 6 groups, the table
  of each of the 2 conferences and the season schedule of the 30 teams (1-hour
  freshness), through the source cache.
- A failed group or conference read fails the build. A failed schedule read is
  skipped only when every drawn team still has its 4 group games among the
  schedules read and no knockout game can exist yet; otherwise the build fails.
  A knockout game can exist once any group row has a `won_group` or `wild_card`
  tag, or the group round is final among the schedules read.
- A failed build keeps the stored feed and is listed under `feeds` in `/health`;
  it is not retried for 10 minutes on request.
- The feed is never deleted.
- The builder is `build_cup_feed` and the feed kind is `CupFeeds`, both in
  `api/app/jobs/cup_feed.py`.

## Endpoint

- `GET /feeds/cup.json` serves the feed through the on-demand cache with
  `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current `ETag`.
- It responds 503 with `{"detail": ...}` after a failed read with nothing
  stored, before the season is known, and when the request's 20 seconds end
  before a missing feed is built.
- A stale stored feed is served at once and rebuilt in the background.
- Every feed request records presence.
