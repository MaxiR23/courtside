# Playoffs feed

The postseason: the picture tables, the play-in, the bracket of 15 series, the
champion, the postseason leaders and the season awards, with every value ready
to draw.

## Schema

[`api/schemas/playoffs.schema.json`](../../api/schemas/playoffs.schema.json),
generated from the models in `api/app/feeds/playoffs.py`. When this page and the
models disagree, the models win. The route and the rules are decided in
[ADR 0032](../adr/0032-playoffs-feed.md); the feed is served at
`/feeds/playoffs.json`. The design is [`design-playoffs.md`](../design-playoffs.md).

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone; dates are US Eastern dates.
- Labels are keys and parts (conference, seed, series number), never prose: the
  page writes the words.
- Every team is an `Opponent` of the league (never a guest) with its colors, as
  in the [games feed](games.md) and the [standings feed](standings.md).

## Feed

| Field              | Type                  | Meaning                                                                                  | Present |
| ------------------ | --------------------- | ---------------------------------------------------------------------------------------- | ------- |
| `season`           | season label          | Such as `2026-27`                                                                        | always  |
| `state`            | `PlayoffsState`       | `picture`, `playin`, `playoffs`, `finals`, `complete`                                    | always  |
| `postseasonDates`  | `DateSpan`            | From the first day of the play-in window to the last day of the postseason window        | always  |
| `currentRound`     | integer (1 to 3) / null | The round the page highlights                                                          | set exactly when `state` is `playoffs` |
| `finalsGame`       | integer (1 to 7) / null | The number of the latest Finals game that is live or final                             | null before Finals game 1 and outside `finals` and `complete` |
| `finalsSummary`    | string / null         | The Finals series summary derived from the games, such as `SAS leads series 2-1`         | null with `finalsGame`, and null while no Finals game is final |
| `stages`           | `PlayoffStageEntry[]` | Exactly 5: `playin`, `round_1`, `round_2`, `round_3`, `finals`                           | always  |
| `picture`          | `PictureTable[]`      | East then West                                                                           | always  |
| `playIn`           | `PlayIn[]` / null     | East then West; null for a season without a play-in (before 2021)                        | null only in a season feed |
| `bracket`          | `Series[]`            | Exactly 15, in the order of `SeriesId`                                                   | always  |
| `champion`         | `Champion` / null     | The champion block                                                                       | set exactly when `state` is `complete` |
| `leaders`          | `LeaderGroup[]` / null | Exactly 9, in the order of `LeaderCategory`                                             | null when the read failed or no category has a leader |
| `buildVersion`     | integer / null        | The rules version of a kept season feed ([ADR 0053](../adr/0053-season-level-rules-for-past-seasons.md)) | null on a current feed and on a stored feed from before the field |
| `awards`           | `Award[]` / null      | The awards with at least one winner on a current roster, in code order                   | null when the read failed or none has a winner |

## Nested objects

| Object               | Fields                                                                                                                                                                             |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DateSpan`           | `firstDate`, `lastDate`: the first is on or before the last                                                                                                                         |
| `PlayoffStageEntry`  | `stage`: `PlayoffStage`; `status`: `PlayoffStageStatus` (`complete`, `in_progress`, `next`, `upcoming`); `firstDate`, `lastDate`: US Eastern dates of the stage's games, both set or both null |
| `PlayoffTeam`        | An `Opponent` of the league plus `colors`: `StandingsColors` (`primary`, `secondary`, null when the team info read failed)                                                         |
| `PictureTable`       | `conference`; `rows`: `PictureRow[]` (up to 10)                                                                                                                                     |
| `PictureRow`         | `seed` (1 to 15, null); `team`: `PlayoffTeam`; `wins`, `losses` (null); `gamesBehind` (one decimal, null for the leader); `clinch`: `Clinch` / null; `line`: `playoffs` on row 6, `playin` on row 10, null on any other row |
| `PlayIn`             | `conference`; `games`: `PlayInGame[]` (exactly 3, in the order `seven_eight`, `nine_ten`, `eighth_seed`)                                                                            |
| `PlayInGame`         | `kind`: `PlayInGameKind`; `top`, `bottom`: `PlayInSlot`; `game`: `PlayoffGame` / null; `outcome`: `PlayInOutcome` / null (set exactly when the game is final with a winner)        |
| `PlayInSlot`         | `label`: `PlayInSlotLabel`; `team`: `PlayoffTeam` / null; `currently`: `PlayoffTeam` / null (never both)                                                                            |
| `PlayInSlotLabel`    | `key`: `place`, `loser_of` or `winner_of`; `place` (7 to 10, set exactly for `place`); `game`: `PlayInGameKind` (set exactly for `loser_of` and `winner_of`)                         |
| `PlayInOutcome`      | `seed` (7, 8 or null); `loserOut`: true when the loser is out                                                                                                                       |
| `PlayoffGame`        | `id`; `date` (US Eastern); `startTime`; `away`, `home`: `Opponent`; `status`: `GameStatus`; `score`: `Score` / null (set when final); `winner` (`away`, `home`, null; only when final); `overtime` (false before the game; true when the period is 5 or more); `venue`; `broadcast` (null); `detailAvailable` |
| `SeriesGame`         | A `PlayoffGame` plus `number` (1 to 7), from the game note                                                                                                                          |
| `Series`             | `id`: `SeriesId`; `round` (1 to 4); `conference` (null for the Finals only); `top`, `bottom`: `SeriesSide`; `status`: `upcoming`, `in_progress`, `complete`; `summary` (derived: `{code} wins series 4-{n}`, `{code} leads series {a}-{b}`, `Series tied {a}-{a}`; null while upcoming); `winner` (team code, set exactly when complete); a complete series has the `wins` of both sides; `games`: `SeriesGame[]` (up to 7, in start order, only the games the source lists) |
| `SeriesId`           | `east-r1-1` to `east-r1-4`, `east-r2-1`, `east-r2-2`, `east-r3`, `finals`, `west-r3`, `west-r2-1`, `west-r2-2`, `west-r1-1` to `west-r1-4`                                          |
| `SeriesSide`         | `label`: `SeriesLabel`; `team`: `PlayoffTeam` / null; `seed` (1 to 15, only with a team; null with a team in a season feed without seeds); `wins` (0 to 4, counted from the series' final games, null while the series is upcoming, only with a team); `currently`: `PlayoffTeam` / null (never both a team and `currently`) |
| `SeriesLabel`        | `key`: `seed` (seeds 1 to 6; 1 to 8 in a season feed before 2021; in a season without seeds, the slot's nominal seed), `playin_winner` (seeds 7 and 8, only with a play-in), `round_1_winner`, `round_2_winner`, `round_3_winner`; `conference`; `seed` (1 to 8; for `seed` and `playin_winner`); `series` (1 to 4; for `round_1_winner` and `round_2_winner`) |
| `Champion`           | `team`: `PlayoffTeam`; `wins` (always 4); `losses` (0 to 3); `firstDate`, `lastDate`: the Finals games; `record`, `home`, `road`: postseason records such as `16-6` (null when the record read failed); `pointDifferential`: `TotalDifferential` over the champion's final postseason games |
| `LeaderCategory`     | `points`, `rebounds`, `assists`, `steals`, `blocks`, `field_goal_pct`, `threes_made`, `double_doubles`, `minutes`                                                                   |
| `LeaderGroup`        | `category`; `leaders`: `PlayoffLeader[]` (up to 5)                                                                                                                                   |
| `PlayoffLeader`      | `rank` (the position in the source list, so a left out leader leaves a gap in the current feed; the past feed never leaves one out); `playerId`; `name` ("—" on a past season when the identity read failed, [ADR 0061](../adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md)); `photoUrl` (null, also null on a past season when the identity read failed); `teamCode` (in a past season, the leader's team link); `value` (text as the source sends it); `seasonCode` (the team's abbreviation in that past season from the standings payload of the past playoffs build (ADR 0058), null on a current feed; [ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)) |
| `Award`              | `code`: `AwardCode`; `team` (1 to 3 for `all_nba`, 1 to 2 for `all_rookie` and `all_defensive`, null for any other award); `winners`: `AwardWinner[]` (at least 1: every winner the source sends, ties included)                      |
| `AwardCode`          | `mvp`, `dpoy`, `roy`, `sixth_man`, `mip`, `cpoy`, `finals_mvp`, `east_finals_mvp`, `west_finals_mvp`, `all_star_mvp`, `cup_mvp`, `cup_all_tournament`, `all_nba`, `all_rookie`, `all_defensive`, `twyman_stokes` |
| `AwardWinner`        | `playerId`; `name`; `photoUrl` (null); `teamCode` (on a past season, the winner's team link, else null; otherwise the team of the award, else the player's roster team; null); `seasonCode` (the team's abbreviation in that past season from the standings payload of the past playoffs build (ADR 0058), null on a current feed; [ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md))                                                                     |

`Opponent`, `Score`, `GameStatus`, `Clinch` and `TotalDifferential` are as in the
[games feed](games.md) and the [standings feed](standings.md).

## Rules that live in the code

1. **Reads.** Before the first day of the play-in window (US Eastern) the build
   reads no scoreboard day and the state is `picture`. From that day it reads every
   US Eastern date of the play-in window and of the postseason window.
2. **Games.** A game is a postseason game by the season type of its event: 5 is
   the play-in and 3 is the postseason. A canceled game is dropped and a repeated
   game id keeps one game. `date` is the US Eastern date of the start time;
   `winner` is the side with more points of a final game; `overtime` is true for
   a live or final game whose period is 5 or more.
3. **State.** `complete` when a Finals team has four counted wins;
   else `finals` when any Finals game was read; else `playoffs` when any round 1
   game is live or final; else `playin` on or after the first day of the play-in
   window; else `picture`.
4. **Stages.** The play-in is complete when its 6 games are final. A round or the
   Finals is complete when all its series are complete (8, 4, 2 and 1). A stage is
   `in_progress` when a game of it is live or final and it is not complete, `next`
   when it is the first stage after the last one complete or in progress (the
   play-in in `picture`), and `upcoming` otherwise. Stage dates are the first and
   last US Eastern dates of its games.
5. **Current round.** Set only in `playoffs`: the latest round (1 to 3) with a
   live or final game; the round after it when that round is complete (at most 3);
   1 when none has started.
6. **Finals line.** `finalsGame` is the number of the latest Finals game that is
   live or final and `finalsSummary` the derived summary of the Finals.
7. **Picture.** Per conference, the first 10 teams in seed order (a team with no
   seed goes last, then the source's conference order). `gamesBehind` is the
   conference games behind from wins and losses. When the standings are of
   another season than the feed's or every team has 0 games (the preseason), the
   rows keep the order but `seed`, `wins`, `losses`, `gamesBehind` and `clinch`
   are null and no side carries `currently`.
8. **Play-in notes.** A play-in game is placed by its note:

   | Note                                                   | Conference | Kind          |
   | ------------------------------------------------------ | ---------- | ------------- |
   | `NBA Play-In - East - 7th Place vs 8th Place`          | East       | `seven_eight` |
   | `NBA Play-In - East - 9th Place vs 10th Place`         | East       | `nine_ten`    |
   | `NBA Play-In - East - 8th Seed Game`                   | East       | `eighth_seed` |
   | the same three with `West`                             | West       | the same kinds |

   A note that matches none, or a second game of one kind in a conference, fails
   the build. A game not yet live or final with an undecided
   side is ignored, and a live or final game with a team outside the league fails
   the build.
9. **Play-in slots.** In `seven_eight` and `nine_ten` the home team is the higher
   place (7th hosts 8th, 9th hosts 10th) and sits on `top`. In `eighth_seed`, `top`
   is the loser of `seven_eight` and `bottom` the winner of `nine_ten`, set once
   those games are final. In `picture` (and not in the preseason) a place slot
   carries `currently`, the team with that place in the standings. Outcomes are
   set for a final game with a winner: `seven_eight` is seed 7 and not out,
   `nine_ten` is out with no seed, `eighth_seed` is seed 8 and out.
10. **Series.** A type 3 game is grouped by round and pair of teams. The round
    comes from the competition type:

    | Competition type | Round |
    | ---------------- | ----- |
    | `RD16`           | 1     |
    | `QTR`            | 2     |
    | `SEMI`           | 3     |
    | `FINAL`          | 4     |

    An unknown type fails the build. The game number comes from the end of the
    note (` - Game N`); a note without it fails the build.
11. **Placement.** Round 1 is placed by the seeds of the pair, the lower seed on
    top; both teams must be of one conference:

    | Series | Seeds |
    | ------ | ----- |
    | `r1-1` | 1 and 8 |
    | `r1-2` | 4 and 5 |
    | `r1-3` | 3 and 6 |
    | `r1-4` | 2 and 7 |

    Seeds 1 to 6 are the standings seeds. Seeds 7 and 8 are the winner of the
    7th vs 8th game and the winner of the 8th seed game. Round 2 is placed by the
    round 1 series its teams came from (`r1-1` and `r1-2` feed `r2-1`, `r1-3` and
    `r1-4` feed `r2-2`), the top being the team of the upper feeder. Round 3 is
    fed by `r2-1` and `r2-2` of its conference. The Finals is fed by the two round
    3 series, the East team on top. A team that cannot be placed, a pair of seeds
    outside the table, a live or final game with a team outside the league and two
    series in one slot fail the build. A game not yet live or final with an undecided
    side is ignored, so its slots keep their standings or label value.
12. **Series values.** Counted from the final games of the series, never read
    from the source's series object. A final game counts for the side whose source
    winner flag is the only true one, else for the side with more points; a game
    that is not final never counts. `wins` per side; `status` is `complete` when a
    team has four wins, `in_progress` when any game is final, else `upcoming` (a
    series whose only played game is live is upcoming); `summary` is
    `{code} wins series 4-{n}` (`n` the loser's wins), `{code} leads series {a}-{b}`
    (`a` the leader's wins) or `Series tied {a}-{a}`. An upcoming series has null
    wins and summary. `winner` is the team with four wins; two teams with four
    wins in one series fail the build.
13. **Undecided sides.** A slot with no game has the label of its place in the
    bracket. Round 1: from `playin` on, seeds 1 to 6 carry their team and seeds 7
    and 8 the team that won that seed once decided; in `picture` the side carries
    `currently`, the team with that seed in the standings. Later rounds carry the
    winner of the feeder series once it is complete.
14. **Champion.** Set when complete: the team and its result from the counted
    Finals wins, the dates of the Finals games, `record`, `home` and `road` from
    the postseason record read, and the point differential summed over the
    champion's final postseason games (type 3 only), with the minus sign U+2212
    when negative. The champion block has no drawing flag.
15. **Leaders.** The first five entries of each of the nine categories, with the
    rank of their position in the source list. The name and photo come from the
    rosters the stars job keeps; a leader on no current roster is left out.
16. **Awards.** The awards the source lists with winners, matched by name
    ignoring case (see below). Winners on no current roster are dropped, then the
    awards left with no winner. The Finals MVP and the two conference finals MVPs
    are awards. The Finals MVP averages ship with the finals feed.
17. **Window.** `postseasonDates` runs from the US Eastern date of the start of
    the play-in window to the US Eastern date of the end of the postseason window.

## The payload each setting must return

Each URL is a template configured in the backend settings; the value is never in
the repository. The shape each must return:

- **`SEASON_TYPE_URL`** (`{season}`, `{type}`): the object of one season type with
  `startDate` and `endDate`, both timestamps with a timezone, the end after the
  start. Type 2 is the regular season, 5 the play-in and 3 the postseason.
- **`SCOREBOARD_URL`** (existing): besides the fields the games feed reads, the
  postseason reads on each event `season.type`; on the first competition
  `type.abbreviation` (the competition type), the first `notes[].headline`, and
  `series`: `summary`, `completed`, `totalCompetitions` and `competitors[]` with
  the team `id` and `wins`; and the `status.period` of a live or final game. The
  games feed reads the season type, the competition type, the first note and the
  series object too, for its `postseason` mark
  ([ADR 0035](../adr/0035-playoffs-marks-in-core-feeds.md)).
- **`POSTSEASON_LEADERS_URL`** (`{season}`): `{"categories": [{"name", "leaders":
  [{"displayValue", "athlete": {"$ref"}, "team": {"$ref"}}]}]}`. The names read are
  `pointsPerGame`, `reboundsPerGame`, `assistsPerGame`, `stealsPerGame`,
  `blocksPerGame`, `fieldGoalPercentage`, `3PointsMadePerGame`, `doubleDouble` and
  `minutesPerGame`; any other category is ignored. The athlete id is the path part
  after `athletes` in the link, and the link is never followed. The team code is
  the id after `teams` in the team link, mapped to a league team; it is null when
  the link is absent or is not a league team.
- **`TEAM_POSTSEASON_RECORD_URL`** (`{season}`, `{team_id}`): `{"items":
  [{"name", "summary"}]}` with the names `overall`, `Home` and `Road` and a
  summary such as `16-6`; anything else is null.
- **`TEAM_POSTSEASON_STATS_URL`** (`{season}`, `{team_id}`): `{"splits":
  {"categories": [{"stats": [{"name", "value"}]}]}}`, flattened by name. The names
  read are `avgPoints`, `avgRebounds`, `avgAssists`, `avgBlocks`, `avgSteals`,
  `fieldGoalPct`, `effectiveFGPct`, `technicalFouls` and `gamesPlayed`; a plus
  minus statistic is never read. The playoffs feed does not read this setting; the finals feed reads it.
- **`SEASON_AWARDS_URL`** (`{season}`): a paged index
  `{"count", "pageIndex", "pageSize", "pageCount", "items": [{"$ref"}]}`, of which
  only `items` is read, and only its first page; then each item's link is read (1
  hour cache), an award document `{"name", "winners": [{"athlete": {"$ref"},
  "team": {"$ref"}}]}`; `team` may be absent. A winner whose team is absent or is not a league team (an All-Star side) has no team. A missing or invalid award document
  fails the read like an invalid index. The names
  read, compared ignoring case: `MVP`, `Defensive Player of the Year`, `Rookie of
  the Year`, `Sixth Man of the Year`, `Most Improved Player`, `Clutch Player of the
  Year`, `Finals MVP`, `NBA Eastern Conference Finals MVP`, `NBA Western Conference
  Finals MVP`, `All-Star MVP`, `NBA Cup MVP`, `NBA Cup All-Tournament Team`, `All-NBA 1st
  Team`, `All-NBA 2nd Team`, `All-NBA 3rd Team`, `All-Rookie 1st Team`, `All-Rookie
  2nd Team`, `All-Defensive 1st Team`, `All-Defensive 2nd Team` and
  `Twyman-Stokes Teammate of the Year Award`. An award with no winners (the coach and the
  executive of the year) is skipped; an unknown name with winners is skipped and
  logged by name.

## Marks on the core feeds

The games, game detail and team feeds carry marks that read this section's
data ([ADR 0035](../adr/0035-playoffs-marks-in-core-feeds.md)). The `postseason`
mark of a game is described in the [games feed](games.md). The team `titles` are
described in the [team feed](team.md); they read this feed's `champion` and its
`east-r3` and `west-r3` series, from the stored feed only.

## Edge cases

Valid feeds include: the preseason (no record, seed or clinch), a `picture` with
no game read, a play-in with no game scheduled, a series with games 5 to 7 not
listed, a series with a summary and no game, a champion with no record, `leaders`
or `awards` null, a category with fewer than five leaders, a leader rank gap, and
a team with null colors.

## Refresh behavior

- The only id is `league`; the feed is stored at `feeds/playoffs/league.json`.
- Nothing is built without a request: no job and no startup builds the feed.
- The season is the end year of the latest roster the stars job fetched. When
  none was fetched or not every roster is fetched, and nothing is stored, the
  endpoint answers 503.
- Built on request under rule G of [`docs/source-rules.md`](../source-rules.md)
  and expiring as its table says: when any postseason game (a game of the feed, or
  a final game of the games job dated inside `postseasonDates`) has a final time
  plus 1 hour after the build; while the state is `picture`, also when any game
  of the league has a final time plus 1 hour after the build; at the start of the
  play-in window (US Eastern midnight) when the build precedes it; and in any case
  7 days after the build. Once the Finals series is complete the feed is kept
  while its season is the current one, and expires under the normal rules when
  the season changes.
- A cold build reads 2 season types, the division standings, 30 team infos, the
  leaders and the awards, one scoreboard day per day of both windows from the first
  day of the play-in window (about 70), and the champion's postseason record when
  the Finals series is complete. Source freshness is 1 hour, except the scoreboard
  days at 30 seconds, shared with the games job.
- A failed season type, standings or scoreboard day read fails the build, and so
  does a postseason game the build cannot place. A failed leaders read gives
  `leaders: null`, a failed awards read `awards: null`, a failed team info read
  null colors for that team and a failed record read null `record`, `home` and
  `road`.
- A failed build keeps the stored feed and is listed under `feeds` in `/health`;
  it is not retried for 10 minutes on request.
- `detailAvailable` is set when the feed is served, from the games the games job
  holds, and is never stored as true.
- The feed is never deleted.
- The builder is `build_playoffs_feed` and the feed kind is `PlayoffsFeeds`, both
  in `api/app/jobs/playoffs_feed.py`.

## Endpoint

- `GET /feeds/playoffs.json` serves the feed through the on-demand cache with
  `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current `ETag`.
- It responds 503 with `{"detail": ...}` after a failed read with nothing
  stored, before the season or the rosters are known, and when the request's 20
  seconds end before a missing feed is built.
- A stale stored feed is served at once and rebuilt in the background.
- Every feed request records presence.

## Season feed

The playoffs of a past season ([ADR 0046](../adr/0046-season-playoffs-feeds.md)),
served at `/feeds/seasons/{season}/playoffs.json`, with the same schema and models
as the feed above. `{season}` is the end year of the season, from 1994 to the
current season.

- The current season serves the feed above: same stored file, body, ETag and
  expiry.
- A past season is built under a read budget of 63 source reads plus 45
  leader reads plus one read per award winner
  ([ADR 0058](../adr/0058-bounded-past-competition-reads.md),
  [ADR 0061](../adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md)): the season
  standings (1), the postseason schedule of the first 8 teams of each conference
  (10 from 2021; per conference the seeded teams in seed order, then the unseeded
  by best record), which gives every game with its season type (`seasonType.type`: 3, 5, missing as 3,
  any other skipped), its winner flags and its competition type when the source
  sends one (20), the play-in window (1) and its scoreboard days (5, the window's Eastern dates, its end included) from 2021, the
  leaders (1), the awards (up to 26), the records of the two finalists (2) and the
  game details of the Finals games (7), the sides of games resolved by provider
  id first and named as the [Cup feed](cup.md) rule 1 reads a name from a
  schedule. It reads no postseason window, no bracket scoreboard day, no team
  info, no roster and no game detail outside the Finals. At most four reads are in
  flight at once, with no pause. A read past the budget, and a 429 or 503, fail
  the build with a logged reason and nothing stored.
- The first 5 leaders of each category and every award winner are named from
  their athlete object, read once through the player identity cache (kept 30
  days, at most eight reads in flight, the other reads at four). A player whose
  read failed is kept with his id, the name "—" and no photo, and is read again on
  the next build; a rate limit stops the build. Nobody is left out. The team of a
  leader or winner is their own team link.
- The colors of a team come from the team info the source cache already holds,
  else they are null.
- The league sides are named from the standings payload (its abbreviation, name
  and location), with `seasonCode` and `historical`
  ([ADR 0054](../adr/0054-historical-sides-and-past-pages.md),
  [ADR 0058](../adr/0058-bounded-past-competition-reads.md)). The Finals feed
  takes the names of the stored season playoffs feed.
- A season before 2021 has no play-in: the window is not requested, `playIn` is
  null, seeds 1 to 8 are the standings seeds and every round 1 label is a seed.
  Its `playin` stage entry is `upcoming` with null dates, and a page does not draw
  it.
- When no postseason game has a known competition type, the rounds are derived
  from the series: a series is round k when it is the k-th series of both teams,
  the Finals is the only series across the conferences, and the rounds have 8, 4,
  2 and 1 series. Anything else fails the build and the reason is logged. A
  postseason where only some games have a type fails as the current feed does.
- A round 1 team with no seed places its series by the round 2 series it feeds,
  and the side seeds are null. Each round 1 label keeps the nominal seed of its slot (1/8, 4/5, 3/6,
  2/7), which the label model requires; a page does not draw the label when a team
  is placed.
- A game whose note has no game number takes its position in its series in start
  order. Play-in and game notes are read in any letter case.
- The champion's record is the one of the team with four counted wins over the
  Finals games, never the team of the source's series object.
- The leaders, the awards and the champion's record are null only when the source
  answers 404. Any other failed read fails the build.
- It must build as `complete`, or the build fails and nothing is stored.
  `detailAvailable` is false.
- Refresh: built on request, stored at `feeds/season-playoffs/{season}.json`, kept
  for good (rule G of [`docs/source-rules.md`](../source-rules.md)): never
  deleted, and rebuilt on its next request when its `buildVersion` is not the
  version of this kind, the current one plus 1
  ([ADR 0061](../adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md)).
  A failed build with nothing stored is retried after 10 minutes.
- The kind is `SeasonPlayoffsFeeds` in `api/app/jobs/season_playoffs_feed.py`.
- Endpoint: it serves with `Cache-Control: public, max-age=10` and an `ETag`, and
  responds 304 for a matching `If-None-Match`. It responds 404 with no source
  request for a season that is not four digits, is before 1994 or is after the
  current season. It responds 503 while the current season is not known, after a
  failed read with nothing stored, and when the request's 20 seconds end before a
  missing feed is built.

# Finals feed

The Finals: the games that are final with their leaders, the win probability of
the curve team and its largest deficit, the Finals MVP, the road of each finalist,
the head to head bars and the postseason averages of both rosters.

## Schema

[`api/schemas/playoffs-finals.schema.json`](../../api/schemas/playoffs-finals.schema.json),
generated from the models in `api/app/feeds/playoffs_finals.py`. When this page
and the models disagree, the models win. The route and the rules are decided in
[ADR 0033](../adr/0033-playoffs-finals-feed.md); the feed is served at
`/feeds/playoffs/finals.json`. The conventions are those of the playoffs feed
above. Every list with one entry per finalist lists the Finals top side (the East
team), then the bottom side.

## Finals feed

| Field          | Type                   | Meaning                                                              | Present |
| -------------- | ---------------------- | -------------------------------------------------------------------- | ------- |
| `season`       | season label          | Such as `2026-27`                                                    | always  |
| `status`       | `SeriesStatus`        | `upcoming`, `in_progress`, `complete`: the status of the Finals series | always  |
| `champion`     | team code / null      | The winner of the series                                             | set exactly when `status` is `complete` |
| `curveTeam`    | team code             | The team of every win probability curve and deficit                  | always  |
| `games`        | `FinalsGame[]`        | The Finals games that are final, in number order (up to 7)           | always, empty before a game is final |
| `finalsMvp`    | `FinalsMvp` / null    | The Finals MVP                                                       | null when the playoffs feed has no `finals_mvp` award |
| `road`         | `RoadTeam[]`          | Exactly 2                                                            | always  |
| `headToHead`   | `HeadToHead`          | The records and the 8 bars                                           | always  |
| `averages`     | `RosterAverages[]` / null | Exactly 2                                                        | null on a past season (no read carries them, [ADR 0058](../adr/0058-bounded-past-competition-reads.md)) |
| `buildVersion` | integer / null        | The rules version of a kept season feed ([ADR 0053](../adr/0053-season-level-rules-for-past-seasons.md)) | null on a current feed and on a stored feed from before the field |

## Nested objects

| Object                      | Fields                                                                                                                                                                                         |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FinalsGame`                | `game`: `SeriesGame` as the playoffs feed stores it (always final); `leaders`: `Leaders` / null; `winProbability`: `FinalsWinProbability` / null; `largestDeficit`: `LargestDeficit` / null; `highlights`: `Highlight[]` / null (set when served) |
| `FinalsWinProbability`      | `points`: `TeamWinProbabilityPoint[]` (at least 1, not going back in time); `periods`: `WinProbabilityPeriods` as in the [game detail feed](game-detail.md)                                    |
| `TeamWinProbabilityPoint`   | `elapsedSeconds`; `winProbability`: the curve team's chance, from 0 to 1                                                                                                                         |
| `LargestDeficit`            | `points` (1 or more): the most points the curve team trailed by; `elapsedSeconds`: the game second of the first play at it                                                                      |
| `FinalsMvp`                 | `playerId`; `name`; `photoUrl` (null); `teamCode` (null); `seasonCode` (the team's abbreviation in that past season from the sides of the stored season playoffs feed on a past Finals (ADR 0058), null on a current feed; [ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)); `games`, `points`, `rebounds`, `assists`: the postseason averages of the season (null; on a past season, the postseason career row of the season label, else null); `bestGame`: `BestGame` / null                  |
| `BestGame`                  | `gameId`; `number` (1 to 7); `points`                                                                                                                                                            |
| `RoadTeam`                  | `team`: `PlayoffTeam`; `seed` (null); `regularSeason`: record such as `60-22` (null); `postseason`: record (null); `series`: `RoadSeries[]` (up to 4, rounds increasing)                          |
| `RoadSeries`                | `round` (1 to 4); `opponent`: `PlayoffTeam`; `opponentSeed` (null); `wins`, `losses` (0 to 4, null): the finalist's wins and the opponent's wins; `result`: `win`, `loss` or null while the series is not complete |
| `HeadToHead`                | `records`: `FinalistRecord[]` (exactly 2, each with `teamCode`, `record` and the `seasonCode` of a past season): the postseason record of each finalist, as in `road` (`postseason`), null when the record read failed; `bars`: `HeadToHeadBar[]` (exactly 8, in the order of `HeadToHeadStat`)                      |
| `HeadToHeadStat`            | `points`, `field_goal_pct`, `effective_fg_pct`, `assists`, `rebounds`, `blocks`, `steals`, `technical_fouls`                                                                                     |
| `HeadToHeadBar`             | `stat`; `values`: `BarValue[]` (exactly 2, `teamCode` and `value`, null when the read failed); `better`: team code / null                                                                       |
| `RosterAverages`            | `teamCode`; `seasonCode` (the team's abbreviation in that past season from the sides of the stored season playoffs feed on a past Finals (ADR 0058), null on a current feed; [ADR 0055](../adr/0055-past-season-reading-rules-and-versioned-stored-data.md)); `players`: `PlayerPostseasonAverages[]`                                                                                                                                              |
| `PlayerPostseasonAverages`  | `playerId`; `name`; `photoUrl` (null); `points`, `rebounds`, `assists`, `blocks` (null); `fieldGoalPct` (0 to 1, null)                                                                          |

## Rules that live in the code

1. **Games.** The Finals series games of the playoffs feed whose status is
   `final`, in number order, each with its `SeriesGame` as stored: score,
   `overtime`, `winner`, id and number. A live or scheduled game is not listed;
   games 5 to 7 that are not played are absent.
2. **Curve team.** The champion when the series is complete; else the side with
   more series wins; with tied wins, the top side of the Finals series.
3. **Curve.** The curve team's win probability at each point: the source's home
   value when the curve team is home, one minus it otherwise, rounded to 3
   decimals. The period boundaries are those of the game detail feed. Null when
   the game has no win probability or the read failed.
4. **Largest deficit.** The largest opponent score minus team score of the curve
   team over the plays that carry both scores, with the elapsed seconds of the
   first play that reached it. Null when the team never trailed, no play carries
   both scores or the read failed.
5. **Finals MVP.** The first winner of the playoffs feed's `finals_mvp` award. His
   `games`, `points`, `rebounds` and `assists` come from the row of the feed's
   season in the postseason player stats; all are null when there is no such row or
   the read failed. `bestGame` is his line with the most points in the box scores of
   the listed games, the earliest game on a tie; null when no box score has him.
6. **Road.** `seed` is the Finals side's seed. `regularSeason` is `wins-losses`
   from the finalist's row of the playoffs feed's picture, null without a row or a
   record. `postseason` is the overall postseason record, null when the read
   failed. `series` lists every bracket series, the Finals included, in which the
   finalist is a side and the other side has a team, in round order.
7. **Head to head.** Percentages are fractions (the source sends 0 to 100).
   `technical_fouls` is the postseason total as the source sends it, not an
   average. The higher value is better, except for `technical_fouls`, where the
   lower is. `better` is null when either value is null or they are equal. A failed
   statistics read leaves that team's values null.
8. **Averages.** The roster of each finalist is the stars job's roster of the team,
   without players whose latest roster is another team's, in jersey order. A
   player with no postseason row of the season, or a failed read, has null values
   and goes last.
9. **Serve time.** `highlights` is the stored highlight of the game as a list of
   one, else null, and `game.detailAvailable` is set from the games the games job
   holds. Neither is ever stored.

## The payload the finals feed reads

- **`GAME_DETAIL_URL`** (existing): besides the fields the game detail feed reads,
  the finals feed reads on each play `homeScore` and `awayScore` (integers). A play
  without both, or with a clock that cannot be placed, is skipped.
- **`PLAYER_STATS_URL`** (existing): read with the postseason query value, for the
  rows of the postseason.
- **`TEAM_POSTSEASON_STATS_URL`** and **`TEAM_POSTSEASON_RECORD_URL`**: as above;
  the finals feed is the reader of the statistics. `technicalFouls` is a total over
  the postseason.

## Edge cases

Valid feeds include: no game final yet (the route answers 404 only when the
Finals has no game at all), games 5 to 7 not played, an overtime game, no
highlights, no win probability curve, a team that never trailed, no Finals MVP,
a player without postseason stats, a failed statistics or record read, and a road
series without data.

## Refresh behavior

- The only id is `league`; the feed is stored at `feeds/playoffs-finals/league.json`.
- Nothing is built without a request.
- Built on request under rule G of [`docs/source-rules.md`](../source-rules.md):
  the playoffs feed is built first when missing or stale. It expires 1 hour after a
  postseason game that follows the build has a final time, when the playoffs feed
  is rebuilt after it, and 7 days after the build. Once the Finals series is
  complete it is kept while its season is the current one.
- Each final game's detail, curve, box score and plays are one cached response with
  the freshness of the game's final time when known, else 1 hour.
- A player's stats are read once per build with the source's 1 hour freshness; the
  bound of rule F holds through the feed's expiry.
- A cold build reads up to 7 game details, 2 postseason records, 2 postseason
  statistics and one player stats read per roster player (about 30).
- The build fails and keeps the stored feed when the season is unknown, no playoffs
  feed of the season is stored, the Finals has no game or a side with no team, or
  the feed is invalid. Any other failed read only nulls its part.
- A failed build is not retried for 10 minutes on request.
- The builder is `build_finals_feed` and the feed kind is `PlayoffsFinalsFeeds`,
  both in `api/app/jobs/playoffs_finals_feed.py`.

## Endpoint

- `GET /feeds/playoffs/finals.json` serves the feed through the on-demand cache
  with `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current `ETag`.
- It serves the playoffs feed first; it responds 503 with `{"detail": ...}` when
  that feed is unavailable, and when the request's 20 seconds end before the finals
  feed is built.
- It responds 404 with `{"detail": ...}` when the Finals has no game, with no
  source read.
- A stale stored feed is served at once and rebuilt in the background.
- Every feed request records presence.

## Season Finals feed

The Finals of a past season ([ADR 0046](../adr/0046-season-playoffs-feeds.md)),
served at `/feeds/seasons/{season}/playoffs/finals.json`, with the same schema and
models as the feed above. `{season}` is the end year of the season, from 1994 to
the current season.

- The current season serves the feed above: same stored file, body, ETag and
  expiry.
- A past season builds from the stored season playoffs feed, built first when
  missing, so a season whose playoffs feed cannot be built answers 503.
- The build is under a read budget of 12 source reads
  ([ADR 0058](../adr/0058-bounded-past-competition-reads.md)): the game details of
  the Finals games (their sections and plays share the request of the game), and
  the postseason record and statistics of each finalist, and the postseason career
  of the Finals MVP, read once with no season
  ([ADR 0061](../adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md)).
  It reads no roster. `averages` is null; the Finals MVP's `games`, `points`,
  `rebounds` and `assists` are his career row of the season label, else null.
  `bestGame` comes from the Finals box scores. The game details resolve the sides
  by provider id first, and the league sides take the names, season codes and
  historical flags of the stored season playoffs feed.
- A detail, sections, plays, team record or team statistics read that answers 404
  nulls its part: `leaders`, `winProbability`, `largestDeficit`, the postseason
  record and the bar values. Any other failed read fails the build.
- `highlights` is the stored highlight added when served, null without one;
  `detailAvailable` is false ([ADR 0048](../adr/0048-highlights-backfill-and-edition-video.md)).
- Refresh: built on request, stored at `feeds/season-playoffs-finals/{season}.json`,
  kept for good (rule G of [`docs/source-rules.md`](../source-rules.md)), rebuilt
  on its next request when its `buildVersion` is not the version of the past
  playoffs ([ADR 0061](../adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md)).
  A failed build with nothing stored is retried after 10 minutes.
- The kind is `SeasonPlayoffsFinalsFeeds` in
  `api/app/jobs/season_playoffs_finals_feed.py`.
- Endpoint: it serves with `Cache-Control: public, max-age=10` and an `ETag`, and
  responds 304 for a matching `If-None-Match`. It responds 404 with no source
  request for a season that is not four digits, is before 1994 or is after the
  current season. It responds 503 while the current season is not known, after a
  failed read with nothing stored, and when the request's 20 seconds end before a
  missing feed is built.
