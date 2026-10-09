# Search feed

The index the search overlay loads: the 30 teams and every player on a
roster, with the values the page needs to list and match them. Matching and
ranking belong to the page.

## Schema

[`api/schemas/search.schema.json`](../../api/schemas/search.schema.json),
generated from the models in `api/app/feeds/search.py`. When this page and
the models disagree, the models win. The route is decided in
[ADR 0024](../adr/0024-search-feed.md); the feed is served at
`/feeds/search.json`.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when absent.
- Times are UTC, as ISO 8601 with a timezone.

## Feed

| Field     | Type             | Meaning                                                          | Present |
| --------- | ---------------- | ---------------------------------------------------------------- | ------- |
| `teams`   | `SearchTeam[]`   | The 30 teams, in standard code order                             | always  |
| `players` | `SearchPlayer[]` | Every roster player, by team code and then roster order          | always  |

## Nested objects

| Object             | Fields                                                                                                                                                                                         |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SearchTeam`       | `code`, `city`, `name`, `colors`: `StandingsColors`; `record`: such as `64-18`; `division`: the division name; `divisionRank`: integer 1 to 5 or null, formatted by the page                     |
| `StandingsColors`  | `primary`, `secondary`: hex values such as `#112233`, each null when the team information is not available                                                                                     |
| `SearchPlayer`     | `id`, `name`: the display name, else first and last name; `shortName`: first initial, a period and the last name; `number` (null), `position` (null), `positionAbbr` (null), `photoUrl` (null); `injury`: `SearchInjury` / null; `team`: `SearchPlayerTeam` |
| `SearchInjury`     | `status`: the league injury status                                                                                                                                                             |
| `SearchPlayerTeam` | `code`, `primary`: the team's primary color as a hex value, null when the team information is not available                                                                                    |

## Rules that live in the code

- The teams come from the division standings, the colors from the team
  information, one read per team.
- The players come from the rosters the stars job keeps in memory. The build
  makes no roster request and no per-player request.
- A player on two rosters is listed once, under the roster fetched most
  recently.
- `injury` is the league injury status of the player, null when the league
  reports none.
- `divisionRank` is the team's position in its division. It is nullable in
  the contract; the current standings always set it.

Edge cases: null colors when a team information read fails (the players of
that team have a null `team.primary`); a `0-0` record before the first game;
a player with no jersey, position, display name or headshot has those fields
null (the name falls back to first and last name); a player with no injury
has `injury` null; a team missing from the standings fails the build.

## Refresh behavior

- The only id is `league`; the feed is stored at
  `feeds/search/league.json`.
- Nothing is built without a request: no job and no startup builds the
  feed.
- Built on request under rule G of
  [`docs/source-rules.md`](../source-rules.md) and expiring as its table
  says: when any game of the league has a final time plus 1 hour after the
  build, when the stars job fetches a roster after the build, and in any case
  7 days after the build.
- The sources read are the division standings, the league injuries and the
  team information of the 30 teams (1-hour freshness), through the source
  cache.
- Until the stars job has fetched every roster the feed answers 503, as the
  player feed does.
- A failed standings or injuries read fails the build: the stored feed is
  kept and the failure is listed under `feeds` in `/health`; it is not
  retried for 10 minutes on request.
- The feed is never deleted.
- The builder is `build_search_feed` and the feed kind is `SearchFeeds`,
  both in `api/app/jobs/search_feed.py`.

## Endpoint

- `GET /feeds/search.json` serves the feed through the on-demand cache with
  `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 503 with `{"detail": ...}` before every roster is fetched,
  after a failed read with nothing stored, and when the request's 20 seconds
  end before a missing feed is built.
- A stale stored feed is served at once and rebuilt in the background.
- Every feed request records presence.
