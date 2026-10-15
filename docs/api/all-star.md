# All-Star feed

The All-Star weekend's game day: the edition (date, venue, format, teams and their
placement, and every game with its box scores, team statistics, leaders and Top 5),
the MVP, the recap of the previous edition and the previous edition as its after
view, with every value ready to draw, including every count.

## Schema

[`api/schemas/all-star.schema.json`](../../api/schemas/all-star.schema.json),
generated from the models in `api/app/feeds/all_star.py`. When this page and the
models disagree, the models win. The route and the rules are decided in
[ADR 0036](../adr/0036-all-star-feed.md); the feed is served at
`/feeds/all-star.json`. The design is [`design-all-star.md`](../design-all-star.md).

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone; dates are US Eastern dates.
- Labels are keys and parts (round label, placement kind), never prose: the page
  writes the words. The format line is the one text the page shows as sent.
- An All-Star team is an `Opponent` that is a guest (as in the
  [games feed](games.md)): it has a code or a name, no city, and no
  colors. The number of teams and rounds changes every year, so the feed is a list
  of games with a round label and N teams, never a fixed bracket.

## Feed

| Field      | Type                  | Meaning                                                               | Present |
| ---------- | --------------------- | --------------------------------------------------------------------- | ------- |
| `year`     | integer               | The season's end year, which is the edition's calendar year           | always  |
| `state`    | `AllStarState`        | `before`, `live`, `after`                                             | always  |
| `edition`  | `AllStarEdition`      | The current edition                                                   | always  |
| `mvp`      | `AllStarMvp` / null   | The All-Star MVP                                                      | null in `before`, and when the award or his box row is missing |
| `previous` | `AllStarRecap` / null | The recap of the previous edition                                     | null when not discovered, unreadable or without a final Championship |
| `previousEdition` | `AllStarPreviousEdition` / null | The previous edition with every game, team and its MVP, drawn as its after view | null when `previous` is null or a game of that edition is not final |

## Nested objects

| Object            | Fields                                                                                                                                                                                                                                                                  |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AllStarEdition`  | `date`: date / null; `venue`: `Venue` / null; `formatLine`: string / null; `teams`: `AllStarTeam[]`; `games`: `AllStarGame[]`; `counts`: `AllStarCounts`; `defaultGameId`: string / null, null exactly when there are no games, else the id of one of them. `editionHighlight`: `Highlight` / null (set when served; the previous edition has it too). At most one team is `champion` and one `runner_up`, and at most one game has `isNext`                                                                                         |
| `AllStarTeam`     | `team`: `Opponent` (a guest); `wins`, `losses`: from final games, the numbers of win and loss `results`; `results`: `AllStarTeamResult[]`; `placement`: `Placement`; `roster`: `RosterTile[]`                                                                                                                                                     |
| `Placement`       | `kind`: `champion`, `runner_up`, `eliminated`, `so_far`, `yet_to_play`; `roundLabel`: set exactly when `kind` is `eliminated`                                                                                                                                             |
| `RosterTile`      | `playerId`; `name`; `photoUrl` (null); `leagueTeam`: `LeagueTeam` / null                                                                                                                                                                                                 |
| `LeagueTeam`      | `code`: the standard team code; `colors`: `primary`, `secondary` (hex, null on a failed read)                                                                                                                                                                            |
| `AllStarGame`     | `id`; `startTime`; `status`; `statusText`, `clock`, `period`: as the games feed sends them (null when absent); `score`: `Score` / null; `overtime`; `winner`: `away`, `home` / null; `leading`: `away`, `home` / null; `attendance` (null); `broadcasts`: `Broadcast[]`; `roundLabel` (null); `championship`; `isNext`; `away`, `home`: `Opponent` / null; `toBeDetermined`; `boxScore`: `AllStarBoxScore` / null; `teamStats`: `AllStarTeamStat[]` / null; `leaders`: `Leaders` / null; `top5`: `Top5Row[]` (up to 5); `highlights`: `Highlight[]` / null (always null) |
| `Broadcast`       | `name`; `kind`: `tv` or `streaming`                                                                                                                                                                                                                                      |
| `AllStarBoxScore` | `away`, `home`: `AllStarTeamBox`                                                                                                                                                                                                                                         |
| `AllStarTeamBox`  | `players`: `AllStarBoxPlayer[]`; `totals`: `BoxScoreTotals` as in the [game detail feed](game-detail.md). `topPoints` is true on every player with the team's highest points, none when it is 0                                                                                                                                                                 |
| `AllStarBoxPlayer`| A `BoxScorePlayer` of the [game detail feed](game-detail.md) (id, name, starter flag, minutes, plus-minus, photo and the 14 stat columns) plus `jersey` (null), `position` (null), `leagueTeam`: `LeagueTeam` / null and `topPoints`                                                  |
| `AllStarTeamStat` | `stat`: `field_goal_pct`, `three_points_made`, `rebounds`, `assists`, `steals`, `blocks`; `away`, `home`: the values (percentages as fractions); `better`: `away`, `home` / null on a tie                                                                                  |
| `Top5Row`         | `playerId`; `name`; `photoUrl` (null); `side`; `leagueTeam` (null); `points`, `rebounds`, `assists`                                                                                                                                                                       |
| `AllStarMvp`      | `playerId`; `name`; `photoUrl` (null); `jersey` (null); `leagueTeam` (null); `lines`: `MvpLine[]` (at least 1); `totals`: `MvpTotals`                                                                                                                                     |
| `MvpLine`         | `gameId`; `roundLabel` (null); `result`: `win` or `loss` (the player's side); `teamScore`, `opponentScore`; `opponent`: `Opponent`; `points`, `rebounds`, `assists`                                                                                                       |
| `MvpTotals`       | `games`: the number of lines; `points`, `rebounds`, `assists`: the sums of the lines                                                                                                                                                                                      |
| `AllStarRecap`    | `year`; `date`; `venue` (null); `championship`: `AllStarResult`; `mvp`: `AllStarMvp` / null; `editionHighlight`: `Highlight` / null (set when served)                                                                                                                                                                               |
| `AllStarPreviousEdition` | The fields of `AllStarEdition` plus `mvp`: `AllStarMvp` / null. Its `date` is always set and equals `previous.date`; it has at least one game and every game is final |
| `AllStarCounts`   | `games`, `teams`: the lengths of `games` and `teams`; `final`, `live`: the numbers of final and live games |
| `AllStarTeamResult` | `gameId`; `roundLabel` (null); `result`: `win` or `loss` (the team's side); `teamScore`, `opponentScore`; `opponent`: `Opponent`; `overtime` |
| `AllStarResult`   | `gameId`; `away`, `home`: `Opponent`; `score`; `winner`; `overtime`                                                                                                                                                                                                       |

## Rules that live in the code

1. **Edition.** The edition is the day the discovery job stored. Its games are the
   All-Star games the scoreboard returns for that day, in start order, without
   canceled games or repeated ids.
2. **State.** `before`: no game is live or final, which includes no game discovered
   yet. The feed then carries the date and venue when known, `games: []`,
   `teams: []`, a null `formatLine` and a null `mvp`. `live`: at least one game is
   live, or at least one is final and not every game is final. `after`: there is at
   least one game and every game is final.
3. **Round label.** The note of a game is `NBA All-Star - <round>`, optionally
   followed by a format suffix that begins with `First team to N points wins`. The
   round, for example `Round Robin`, `Semifinals` or `Championship`, is the
   `roundLabel`. A game of the round `Championship` has `championship` true. A note
   that does not match gives a null label.
4. **Format line.** The edition's line is the line of the first game, in start order,
   that has one. A game has `First to N`, followed by ` · Untimed` when the suffix
   says `Untimed`; else, with a known format, `{periods} period(s) · {minutes} min`
   (`1 period · 12 min`, `4 periods · 12 min`); else none.
5. **Teams.** The distinct sides of the games, in order of first appearance (away,
   then home). A side whose game has no teams yet is not a team. `wins` and
   `losses` count final games only.
6. **Placements.** From final scores only. Once the game with `championship` true is
   final, its winner is `champion`, its loser `runner_up`, and every other team is
   `eliminated` with the round label of its last game that has one. Until then a team
   with a final game is `so_far` and one without is `yet_to_play`. Who advances is
   never inferred. A Championship with no teams is a game with `toBeDetermined`
   true and no `away` or `home`.
7. **Overtime.** True on a live or final game whose period is greater than the
   regulation periods of the game's format.
8. **Winner.** On a final game, the side with the higher score.
9. **Status text, clock and period.** As the scoreboard sends them for the game.
   The clock is M:SS, as in the games feed.
10. **Team statistics.** Six rows in the order of `AllStarTeamStat.stat`.
    Field goal percentage, rebounds, assists, steals and blocks come from the game
    detail's team statistics, the three pointers made from the box score totals. The
    higher value is `better`; a tie has none. Null without the box score.
11. **Top 5.** The box rows of both sides sorted by points, then rebounds plus
    assists, both descending, ties in source order; the first 5.
12. **League team.** The standard team code of the player's latest fetched roster,
    found by player id, with that team's colors. Null when the player is on no
    roster; the colors are null when the team info read failed.
13. **MVP.** The first winner of the award `all_star_mvp` of the season awards. One
    line per final game in which he has a box row, in start order; the totals are the
    sums. His name, photo and jersey come from his first box row. Null without the
    award or without a box row of his. A null MVP of an edition in play is logged as a
    warning with the season and the reason.
14. **Recap.** The previous season's edition read the same way: the Championship
    result, the date, the venue and its MVP. Null when that edition was not
    discovered, its day could not be read, or its Championship is not final.
15. **Counts.** The lengths of the shown games and teams, and the numbers of final
    and live games; all 0 in `before`.
16. **Default game.** In `after`, the game with `championship` true; else the first
    live game; else the first game not final; else the first game. Null without
    games.
17. **Next game.** In `live` only, the first game in start order that is neither
    live nor final, other than the default game.
18. **Leading side.** On a live game, the side with the higher score; none on a tie.
19. **Top points.** In each team box, every player with the highest points, when
    above 0.
20. **Team results.** Per team, its final games with a winner, in start order; the
    same games that make `wins` and `losses`.
21. **Previous edition.** The previous season's edition built with rules 1 to 13 and
    15 to 20 from the reads of the recap (no other read), with its MVP, set exactly
    when the recap is set and every game of that edition is final.
22. **Serve time.** `editionHighlight` is the stored video of the edition, set on
    the edition, on the previous edition and on the recap, else null. `highlights`
    is null on every game. Neither is ever stored ([ADR 0048](../adr/0048-highlights-backfill-and-edition-video.md)).
23. **Edition video.** The window of an edition is its game day (US Eastern) and
    the 3 days after it. The video is the first upload of the channel published in
    the window whose title has "All-Star", the year of the game day and
    "highlight" or "full", in any letter case. It is looked for once a day by the
    highlights backfill after the window has ended, is null when none is found,
    and is never replaced once stored.

## The payload each setting must return

- **`SCOREBOARD_URL`** (existing): per event `id`, `date`, `season.type` (the
  regular season is `2`), `status.type.name`, `status.type.shortDetail` (the status
  text), `status.period`, `status.displayClock`; in the first competition
  `type.abbreviation` (`ALLSTAR`), `notes[].headline`, `venue.fullName` and
  `competitors[]` with `homeAway`, `score` and `team` (`abbreviation`, `name`).
  A team with a code or a name is an All-Star team, with a null city (its
  `location` repeats its name and is not read); a team with neither is
  undecided and its side is null.
- **`GAME_DETAIL_URL`** (existing): besides the fields the game detail feed reads,
  `format.regulation.periods` and `format.regulation.clock` (seconds),
  `gameInfo.attendance`, `broadcasts[]` with `type.shortName` (`TV` or `Streaming`;
  any other value is skipped) and `media.shortName`, and on each box score athlete
  `jersey` and `position.abbreviation`. These keys are read leniently: a different
  or missing key only nulls that field. An attendance of zero is no attendance.
- **`SEASON_AWARDS_URL`** (existing): the award named `All-Star MVP` with its
  winner.
- **`TEAM_INFO_URL`** (existing): the colors of a league team that appears in a box
  score.

## Discovery

A job in the stars job's task runs once a day at `DAILY_FETCH_TIME`, after the stars
job, once the season is known. For the current season, then the previous one, it
reads the scoreboard days from February 1 to March 7 of the season's end year (35
days, 36 in a leap year) in order, until a day has All-Star games. It stores that
day and the game ids in the state database and never scans that season again. A
season with no All-Star game yet is scanned again at the next daily run. A failed
read records the failure, keeps what is stored and is retried 5 minutes later. A
season change makes the run due at once.

## Edge cases

Valid feeds include: no edition discovered, an edition with only scheduled games,
a Championship with no teams, a game with no box score or no team statistics, a
failed leaders read, a player on no roster, a failed team info read, no award yet,
an edition of two, three or four teams, an overtime game, no previous edition, a previous edition with a recap but a game
not final (no `previousEdition`), a live day between games (the default game is the
next not final, no next game beyond it) and a points tie for the top of a team box.

## Refresh behavior

- The only id is `league`; the feed is stored at `feeds/all-star/league.json`.
- Nothing is built without a request. It answers 503 until the stars job knows the
  season and has fetched every roster, and the discovery has completed a run.
- Built on request under rule G of [`docs/source-rules.md`](../source-rules.md): it
  expires 30 seconds after the build while its state is `live` or the edition's date
  is today (US Eastern), and a request that finds it stale waits for the rebuild;
  before the edition, when the discovery runs after the build; once every game is
  final, it is kept while its season is the current one, but only when it was built
  at least 1 hour after the latest time the feed first saw one of its games final;
  before that it is stale 30 seconds after the build.
- A cold build reads 1 scoreboard day and, per game (up to 4), one cached game
  detail response (the leaders, the sections and the extras share it), the team infos
  of the league teams in the box scores (1 hour cache) and the season awards, plus
  the same for the previous edition.
- The first build that sees a game final stores that time (table `all_star_finals`)
  before the reads and never overwrites it. The game reads have the freshness of the
  live interval (30 seconds) for a live game, 1 hour for a game not started, and the
  stored first-seen-final time for a final game, so a summary fetched while the game
  was live is read again.
- Every rebuild also reads the previous edition, which is finished data: its
  scoreboard day and its games' details are read with a 24-hour freshness, so they
  are requested about once a day and not every 30 seconds.
- The build fails and keeps the stored feed when the season is unknown, the current
  scoreboard day cannot be read, or the feed is invalid. Any other failed read only
  nulls its part.
- A failed build is not retried for 10 minutes on request.
- The builder is `build_all_star_feed` and the feed kind is `AllStarFeeds`, both in
  `api/app/jobs/all_star_feed.py`; the discovery is `AllStarDiscovery` in
  `api/app/jobs/all_star_discovery.py`.

## Endpoint

- `GET /feeds/all-star.json` serves the feed through the on-demand cache with
  `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current `ETag`.
- It responds 503 with `{"detail": ...}` when the feed is not ready, cannot be
  built with nothing stored, or the request's 20 seconds end before it is built.
- A stale stored feed is served at once and rebuilt in the background, except while
  the state is `live` or the edition's date is today, when the request waits for the
  rebuild.
- Every feed request records presence.

## Season feed

- `GET /feeds/seasons/{season}/all-star.json` serves the All-Star feed of a season
  from 1994, with the schema above (`schemas/all-star.schema.json`).
- The current season serves the feed above: the same stored file, body, `ETag` and
  expiry. Only a season before the current one is built as described here.
- The edition of a past season is the stored one, else the first February day
  (US Eastern) of that season's calendar that has All-Star games, which is then
  stored. A season with none answers 404, and is not scanned again until the
  backend restarts.
- The previous edition (`previous` and `previousEdition`) is found the same way and
  is null before 1994 or when it is not found.
- A game detail, sections, extras or awards read that answers 404 only nulls its
  part (the MVP is null when there is none). Any other failed read fails the build.
- The feed must build in the `after` state, or the build fails with a logged reason
  and nothing is stored.
- `leagueTeam` is null on every row, `highlights` is null on every game and
  `editionHighlight` is added when served.
- The feed is built once on request, stored at
  `feeds/season-all-star/{season}.json` and kept: it is never refreshed or deleted.
  A failed build is not retried for 10 minutes on request.
- The feed kind is `SeasonAllStarFeeds` in `api/app/jobs/season_all_star_feed.py`.

### Endpoint

- It responds 200 with `Cache-Control: public, max-age=10` and an `ETag`, and 304
  with no body when `If-None-Match` matches.
- It responds 404 for a season that is not a four-digit end year from 1994 to the
  current season, and for a past season with no edition found, with no source
  request for the former.
- It responds 503 with `{"detail": ...}` while the current season is not known,
  when the build fails with nothing stored, or the request's 20 seconds end before
  it is built.
