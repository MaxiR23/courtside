# Cup matchup feed

The data of the matchup panel and the player card of the NBA Cup: for a
bracket slot, its game and, for each side, the team's path in the Cup, its
injuries and its roster with per game averages, starters and stat leaders.

## Schema

[`api/schemas/cup-matchup.schema.json`](../../api/schemas/cup-matchup.schema.json),
generated from the models in `api/app/feeds/cup_matchup.py`. When this page and
the models disagree, the models win. The route is decided in
[ADR 0029](../adr/0029-cup-matchup-feed.md); the feed is served at
`/feeds/cup/matchups/{id}.json`, one per slot id of the [Cup feed](cup.md).

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone; dates are US Eastern dates.
- Labels are keys and parts, never prose: the page writes the words.
- Every team is an `Opponent`, as in the [games feed](games.md).

## Feed

| Field        | Type                | Meaning                                              | Present |
| ------------ | ------------------- | ---------------------------------------------------- | ------- |
| `season`     | season label        | Such as `2026-27`, the Cup feed's season             | always  |
| `id`         | `SlotId`            | The slot id                                          | always  |
| `round`      | `CupRound`          | The round of the slot                                | always  |
| `conference` | `east` / `west` / null | The conference of the slot                        | null for the final only |
| `game`       | `CupGame` / null    | The slot's game, as the Cup feed stores it           | null when no game is scheduled |
| `top`        | `MatchupSide`       | The top side of the slot                             | always  |
| `bottom`     | `MatchupSide`       | The bottom side of the slot                          | always  |

## Nested objects

| Object           | Fields                                                                                                                                                                  |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CupGame`        | As in the [Cup feed](cup.md): `id`, `stage`, `date`, `startTime`, `away`, `home`, `status`, `score`, `winner`, `period`, `broadcast`, `venue`, `city`, `neutralSite`, `countsInStandings`, `detailAvailable` |
| `SlotLabel`      | As in the [Cup feed](cup.md): `key`, `conference`, `seed`, `quarterfinal`                                                                                                |
| `SlotRule`       | As in the [Cup feed](cup.md)                                                                                                                                             |
| `MatchupSide`    | `label`: `SlotLabel`; `rule`: `SlotRule`; `known`; `projected` (true when `team` is the projected team); `team`: `Opponent` / null; `details`: `MatchupTeam` / null (set exactly when `team` is set) |
| `MatchupTeam`    | `path`: `PathGame[]` by start time; `injuries`: `TeamInjury[]`; `roster`: `MatchupPlayer[]` (at most 5 starters)                                                         |
| `PathGame`       | `gameId`; `stage`: `CupRound`; `startTime`; `opponent`: `Opponent`; `isHome`; `status`: `GameStatus`; `result`: `win` / `loss` / null; `teamScore`, `opponentScore` (null); `detailAvailable`. `result` and both scores are set exactly when `status` is `final` |
| `TeamInjury`     | As in the [team feed](team.md): `playerId`, `name`, `number`, `position`, `status`, `comment`, `updatedAt`                                                               |
| `MatchupPlayer`  | The `RosterPlayer` of the [team feed](team.md) (`id`, `name`, `number`, `position`, `height`, `weight`, `age`, `birthDate`, `birthplace`, `college`, `experience`, `photoUrl`, `status`), plus `averages`: `PerGameAverages` / null; `starter`; `leader`: `StatLeaders`. A player with null `averages` leads nothing |
| `PerGameAverages`| `points`, `rebounds`, `assists`: per game, to one decimal                                                                                                                |
| `StatLeaders`    | `points`, `rebounds`, `assists`: true when the player leads the roster in the stat                                                                                       |

`Opponent` is as in the [games feed](games.md).

## Rules that live in the code

1. **Side team and projection.** A side's team is the Cup feed side's `team`,
   else its `projected` team, else none. A scheduled slot's sides already carry
   the game's teams. `projected` is true only for a projected team. A side with
   no team has only `label`, `rule` and `known`, and nothing is read for it.
2. **Header.** `game` is the slot's game as the Cup feed stored it. `round`,
   `conference` and `id` are the slot's. `detailAvailable` is set when the feed
   is served, from the games of the days shown, and is false in the stored file.
3. **Path.** The Cup games of the team's season schedule (a note that names a
   Cup round), by start time then game id. `status` follows the Cup feed's
   mapping. `result`, `teamScore` and `opponentScore` are set only when final.
   `detailAvailable` is set when served, as for the header.
4. **Injuries.** The team's entries of the league injuries, drawn as in the team
   feed.
5. **Roster.** Ordered by jersey number, unnumbered last, as in the team feed. A
   jersey that is not a number fails the build. The fields are the team feed's:
   the hometown is `birthplace` and the age is on the US Eastern date of the
   build. A player with no photo has a null `photoUrl`. The player page link id
   is the player's `id`.
6. **Averages.** Matched to the roster by player id, each stat rounded to one
   decimal. A player not in the averages, or a team whose averages are missing,
   are empty or failed to read, has null `averages`.
7. **Starters.** For each of the five positions (pg, sg, sf, pf, c) the first
   athlete of the depth chart, if that athlete is on the roster. An athlete
   first at two positions is marked once, a missing position marks no one, and
   an id off the roster marks no one. No chart marks no starter.
8. **Leaders.** For each stat, the highest rounded average among the players with
   averages; every player at that value leads. With no player with averages no
   one leads.

The `DEPTH_CHART_URL` setting (with `{season}` and `{team_id}`, the provider's
team id from the fixed team id table) must return this payload: an object with
`items`. The first item's `positions` is an object keyed `pg`, `sg`, `sf`, `pf`
and `c`, each with `athletes`, a list in rank order of
`{"athlete": {"$ref": ...}}` whose path has the athlete id after `athletes`.
Links are never followed and other keys are ignored. A missing position is
valid and an empty `items` is an empty chart.

Edge cases: a side with no team, a slot with no game, a projected side, a team
with no averages, a missing position, an empty depth chart, a team with no
injuries and a player with no photo are all valid.

## Refresh behavior

- The ids are the 7 slot ids; a feed is stored at `feeds/cup-matchups/{id}.json`.
- Nothing is built without a request. The season is the end year of the latest
  roster the stars job fetched. When none was fetched and nothing is stored, the
  endpoint answers 503.
- The Cup feed is built first when it is missing or stale (one Cup build at a
  time). Its season must be the current one.
- Per team the roster (24 hours), the season schedule (1 hour), the season
  averages and the depth chart (24 hours) are read, and the league injuries
  (1 hour) once, through the source cache.
- Built on request under rule G of [`docs/source-rules.md`](../source-rules.md)
  and expiring as its table says: 1 hour after a final game of either team or of
  its path that follows the build, when the Cup feed is rebuilt after the build,
  and in any case 7 days after the build.
- A failed Cup feed, roster, schedule or injuries read fails the build. A failed
  averages read builds with null averages and no leader; a failed depth chart
  read builds with no starter.
- A failed build keeps the stored feed and is listed under `feeds` in `/health`;
  it is not retried for 10 minutes on request.
- The feed is never deleted.
- The builder is `build_matchup_feed` and the feed kind is `CupMatchupFeeds`,
  both in `api/app/jobs/cup_matchup_feed.py`.

## Endpoint

- `GET /feeds/cup/matchups/{id}.json` serves the feed through the on-demand
  cache with `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current `ETag`.
- It responds 404 with `{"detail": ...}` for an id outside the 7 slot ids, with
  no source request.
- It responds 503 with `{"detail": ...}` after a failed read with nothing
  stored, before the season is known, and when the request's 20 seconds end
  before a missing feed is built.
- A stale stored feed is served at once and rebuilt in the background.
- Every feed request records presence.
