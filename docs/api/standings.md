# Standings feed

The standings of the league, grouped by conference and by division, with
every value ready to draw.

## Schema

[`api/schemas/standings.schema.json`](../../api/schemas/standings.schema.json),
generated from the models in `api/app/feeds/standings.py`. When this page and
the models disagree, the models win. The route is decided in
[ADR 0023](../adr/0023-standings-feed.md); the feed is served at
`/feeds/standings.json`.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

| Field         | Type                 | Meaning                                                        | Present |
| ------------- | -------------------- | -------------------------------------------------------------- | ------- |
| `season`      | season label         | Such as `2025-26`; in the preseason it is the previous season  | always  |
| `state`       | `StandingsState`     | `final` or `regular`                                           | always  |
| `gamesPlayed` | integer              | The sum of the wins of every team                              | always  |
| `conferences` | `ConferenceGroup[]`  | East then West                                                 | always  |
| `divisions`   | `DivisionGroup[]`    | Every division, in the order the provider sends them           | always  |
| `buildVersion` | integer / null | The rules version of a kept season feed ([ADR 0053](../adr/0053-season-level-rules-for-past-seasons.md)) | null on a current feed and on a stored feed from before the field |

## Nested objects

| Object               | Fields                                                                                                                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ConferenceGroup`    | `key` (`east`, `west`), `name`, `teamCount` (equals the number of teams), `teams`: `StandingsRow[]` by seed                                                                              |
| `DivisionGroup`      | `name`, `conference` (`east`, `west`), `teams`: `StandingsRow[]` in the provider's order                                                                                                 |
| `StandingsRow`       | `code`, `city`, `name`, `colors`: `StandingsColors`; `seed` (1 to 15, null), `clinch` (null); `wins`, `losses`; `pct` (null), `gamesBehind` (null), `streak`: `Streak` / null; `home`, `away`, `lastTen`, `division`, `conference`: records such as `34-7`; `pointsFor`, `pointsAgainst`: one decimal; `differential`: `PerGameDifferential`; `total`: `TotalDifferential`; `seasonCode` (null), `historical` (false): on a past season the team's abbreviation that season and whether that season's name, city or code differs from today's ([ADR 0054](../adr/0054-historical-sides-and-past-pages.md)) |
| `StandingsColors`    | `primary`, `secondary`: hex values such as `#112233`, each null when the team information is not available                                                                              |
| `Clinch`             | `*` best record of the league, `z` conference, `y` division, `x` playoffs, `xp` play-in, `pb` play-in position, `e` eliminated                                                           |
| `Streak`             | `kind` (`win`, `loss`), `count`                                                                                                                                                         |
| `PerGameDifferential` | `value` (such as `+4.4`, `−4.4` or `0.0`), `nonNegative`                                                                                                                               |
| `TotalDifferential`  | `value` (such as `+631`, `−312` or `0`), `nonNegative`                                                                                                                                  |

## Rules that live in the code

- A conference is sorted by seed. A seed of 0 or none is no seed (`null`)
  and goes last. Equal seeds and teams with no seed keep the provider's
  conference order.
- A conference `name` is a fixed English name set by the backend (`Eastern
  Conference`, `Western Conference`), not provider data; a page that
  translates it uses `key`.
- Divisions and the teams of a division are listed in the order the provider
  sends them. A division row carries the conference seed.
- `gamesBehind` in a conference is computed against the leader: half of the
  wins the leader has over the team plus the losses the team has over the
  leader. The leader is the team with the best wins minus losses; a tie goes
  to the lower seed. The leader is `null`; a team tied with it is `0.0`.
- `gamesBehind` in a division is the provider's value with one decimal; a
  dash is `null`.
- `pct` is three decimals without the leading zero (`.659`), `1.000` for a
  perfect record. `gamesBehind`, `pointsFor` and `pointsAgainst` have one
  decimal.
- Both differentials are signed: `+` for positive and the minus sign U+2212
  for negative. Zero has no sign and is non-negative. The per game value is
  rounded to one decimal, the total to a whole number.
- A team with no game has `pct`, `streak` and `gamesBehind` null, and a
  `0-0` division, conference and last ten record when the source sends none.
- `colors` are null when the team information cannot be read; the rest of the
  feed is built.
- `gamesPlayed` is the sum of the wins. `state` is `final` when the
  standings fell back to the last regular season (rule L of
  [`docs/source-rules.md`](../source-rules.md)) or every team has 82 games,
  and `regular` otherwise.
- An unknown clinch code is `null` and is logged with the team code.

Edge cases: a team with no game, equal seeds, a seed above a team with more
wins, and missing colors are all valid.

## Refresh behavior

- The only id is `league`; the feed is stored at
  `feeds/standings/league.json`.
- Nothing is built without a request: no job and no startup builds the
  feed.
- Built on request under rule G of
  [`docs/source-rules.md`](../source-rules.md) and expiring as its table
  says: when any game of the league has a final time plus 1 hour after the
  build, and in any case 7 days after the build. The final games are the ones
  the games job holds.
- The sources read are the division standings and the team information of
  the 30 teams (1-hour freshness), through the source cache. The division
  standings add one request for the regular season when the configured one is
  not (rule L).
- A failed build keeps the stored feed and is listed under `feeds` in
  `/health`; it is not retried for 10 minutes on request.
- The feed is never deleted.
- The builder is `build_standings_feed` and the feed kind is
  `StandingsFeeds`, both in `api/app/jobs/standings_feed.py`.

## Endpoint

- `GET /feeds/standings.json` serves the feed through the on-demand cache
  with `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 503 with `{"detail": ...}` after a failed read with nothing
  stored, and when the request's 20 seconds end before a missing feed is
  built.
- A stale stored feed is served at once and rebuilt in the background.
- Every feed request records presence.

## Season feed

The standings of a past season ([ADR 0043](../adr/0043-season-feeds-and-franchise-names.md)),
served at `/feeds/seasons/{season}/standings.json`, with the same schema and
models as the feed above. `{season}` is the end year of the season, from 1994 to
the season before the current one.

- The season values: `state` is `final` whatever the games played, `clinch` is
  the source's own code, and `colors` are today's, from the cached team info
  (no request), null without it. The division standings are the one read of the
  build, in a budget of 1 ([ADR 0059](../adr/0059-bounded-past-page-reads.md)), with
  the season query value and no rule L fallback, and each team
  is resolved by its provider id first, so a past abbreviation still gives the
  team's standard code. A response that is not of the requested regular season
  fails the build. Each row's `city` and `name` are the standings payload's, with the season
  code of the stored franchise names ([ADR 0059](../adr/0059-bounded-past-page-reads.md)).
- Refresh: built on request, stored at `feeds/season-standings/{season}.json`,
  kept for good (rule G of [`docs/source-rules.md`](../source-rules.md)): never
  deleted, and rebuilt on its next request when its `buildVersion` is not the
  current one. A failed build with nothing stored is retried
  after 10 minutes.
- The kind is `SeasonStandingsFeeds` in
  `api/app/jobs/season_standings_feed.py`.
- Endpoint: it serves with `Cache-Control: public, max-age=10` and an `ETag`, and
  responds 304 for a matching `If-None-Match`. It responds 404 with no source
  request for a season that is not four digits, is before 1994, or is the current
  season or later. It responds 503 while the current season is not known, after a
  failed read with nothing stored, and when the request's 20 seconds end before a
  missing feed is built.

