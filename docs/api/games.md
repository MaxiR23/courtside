# Games feed

The games for the days shown on the site, with scores, status and game
details.

## Schema

[`api/schemas/games.schema.json`](../../api/schemas/games.schema.json),
generated from the models in `api/app/feeds/games.py`. When this page and
the models disagree, the models win.

Conventions:

- Keys are camelCase.
- No unknown fields are accepted.
- Nullable fields are always present and `null` when unknown.
- Times are UTC, as ISO 8601 with a timezone.
- `Day.date` is the US Eastern date (ADR 0007, "Day boundary").

## Feed

| Field         | Type    | Meaning                               | Present |
| ------------- | ------- | ------------------------------------- | ------- |
| `generatedAt` | time    | When the feed was generated           | always  |
| `days`        | `Day[]` | The days shown; the list may be empty | always  |

## Day

| Field   | Type     | Meaning                                 | Present |
| ------- | -------- | --------------------------------------- | ------- |
| `date`  | date     | US Eastern date of the day              | always  |
| `games` | `Game[]` | Games of the day; the list may be empty | always  |

## Game

| Field                 | Type                   | Meaning                                                          | Present                         |
| --------------------- | ---------------------- | ---------------------------------------------------------------- | ------------------------------- |
| `id`                  | string                 | Game identifier                                                  | always                          |
| `away`, `home`        | `GameTeam`             | The two teams                                                    | always                          |
| `status`              | `GameStatus`           | `scheduled`, `live`, `final`, `delayed`, `postponed`, `canceled` | always                          |
| `startTime`           | time                   | Scheduled start, UTC                                             | always                          |
| `venue`               | string                 | Arena name                                                       | always                          |
| `stars`               | `Stars`                | The star of each team                                            | always                          |
| `highlights`          | `Highlight[]`          | Matched highlight videos, may be empty                           | always                          |
| `broadcast`           | string / null          | Broadcaster                                                      | null when unknown               |
| `period`              | integer / null         | Current period, 5 and up are overtimes                           | required when `live`            |
| `clock`               | string / null          | Game clock                                                       | required when `live`            |
| `lineScore`           | `LineScore` / null     | Points per period for each team                                  | required when `live` or `final`, except a `final` All-Star game, which may have none ([ADR 0051](../adr/0051-all-star-notes-and-untimed-games.md)) |
| `score`               | `Score` / null         | Current or final points                                          | required when `live` or `final` |
| `winner`              | `away` / `home` / null | The side with more points; a side, not a code, so a guest without a code can win | required when `final`, null otherwise |
| `leaders`             | `Leaders` / null       | Top scorer of each team                                          | required when `live`; when `final`, set when `statsAvailability` is `available`, null otherwise |
| `teamStats`           | `GameTeamStats` / null | Team statistics                                                  | required when `live`; when `final`, set when `statsAvailability` is `available`, null otherwise |
| `statsAvailability`   | `StatsAvailability` / null | `available`, `pending`, `unavailable`                        | required when `final`, null otherwise |
| `highlightsSearchUrl` | URL / null             | Link to search for highlights                                    | required when `final`           |
| `cup`                 | `GameCup` / null       | The Cup mark: the round the game belongs to                      | null when the game is not a Cup game |
| `postseason`          | `GamePostseason` / null | The play-in or playoff mark                                     | null for a game that is neither a play-in nor a playoff game, and for a play-in game whose note cannot be read; a playoff game always has a mark ([ADR 0050](../adr/0050-postseason-mark-of-every-series-game.md)) |
| `allStar`             | `GameAllStar` / null   | The All-Star mark                                                | null for a game that is not an All-Star game |

A `live` game requires `period`, `clock`, `lineScore`, `score`, `leaders`
and `teamStats`. A `final` game requires `lineScore` (not a final All-Star game, which has a score and may have no line score), `score`, `winner`, `statsAvailability`
and `highlightsSearchUrl`; any other status has `winner` and
`statsAvailability` null. A final game has `leaders` and `teamStats` only when
`statsAvailability` is `available`. The other statuses add nothing.

## Nested objects

| Object      | Fields                                                                                                      |
| ----------- | ----------------------------------------------------------------------------------------------------------- |
| `GameCup`   | `stage` (`group`, `quarterfinals`, `semifinals`, `championship`), taken from the game's note |
| `GamePostseason` | `stage` (`playin`, `playoffs`, `finals`); `round` (1 to 4: 1 to 3 are `playoffs`, 4 is `finals`; null for `playin` and for a `playoffs` game whose round cannot be read); `conference` (`east`, `west`; null for `finals`, for `playin` it is set, and for a `playoffs` game it is null exactly when `round` is); `number` (game number 1 to 7; null for `playin` and when the note gives none); `summary` (the series summary; null when the source has none, always null for `playin`); `playIn` (`seven_eight`, `nine_ten`, `eighth_seed`; set exactly for `playin`); `stakes` (`game_7`, `elimination`, `can_clinch`, `clinched`; null for none) |
| `GameAllStar` | `roundLabel` (the round as the source writes it: "Round Robin", "Semifinals", "Championship"; the format suffix is not part of it; "All-Star Game" for the notes "ALL STAR GAME" and "NBA All-Star Game"); `championship` (true for the round `Championship`) |
| `Team`      | `code` (three capital letters), `name`, `city`                                                              |
| `Opponent`  | `code` (null for a guest without one), `name`, `city` (null when the source sends none), `guest`; a league code is three capital letters, a guest code any non-empty string, and a guest has a code or a name |
| `GameTeam`  | `Opponent` with a required `name`; `city` required for a league team, null for a guest the source sends without one and for an All-Star team |
| `Player`    | `playerId`, `firstName`, `lastName`, `teamCode`, `photoUrl`                                                 |
| `Leader`    | `playerId`, `displayName` (as the source gives it), `teamCode` (null for a guest without a code), `photoUrl`, `points`, `rebounds`, `assists`; `photoUrl` is null only for a guest player without a headshot |
| `Star`      | `Player` fields plus `shortName`                                                                            |
| `TeamStats` | `fieldGoalPct`, `threePointPct` (0 to 1; null when the source sends none), `rebounds`, `assists`, `turnovers` |
| `Highlight` | `title`, `channel`, `thumbnailUrl`, `embedUrl`                                                              |
| `LineScore` | `away`, `home`: points per period, at least one, overtimes appended                                         |
| `Score`     | `away`, `home`: points                                                                                      |
| `Leaders`   | `away`, `home`: `Leader`                                                                                    |
| `Stars`     | `away`, `home`: `Star`, null for a guest side                                                               |

Rules that live in the code:

- The `postseason` mark ([ADR 0035](../adr/0035-playoffs-marks-in-core-feeds.md),
  [ADR 0050](../adr/0050-postseason-mark-of-every-series-game.md))
  is read from the scoreboard. The stage comes from the season type (5 is
  `playin`, 3 is a series game, any other value no mark). A series game always
  has a mark and what cannot be read is null inside it. The round and
  conference come first from the note, in any letter case: `NBA Finals - Game N`
  is round 4 and `<East|West> <1st Round|Semifinals|Finals> - Game N` is rounds 1
  to 3. Otherwise the round comes from the competition type (the 4 round codes,
  1 to 4) and the conference of rounds 1 to 3 from the note's first word; a round
  1 to 3 without a conference is no round. A mark with no round is stage
  `playoffs` with a null `round` and `conference`. The play-in conference and
  kind come from the play-in note, the game number from the note's ` - Game N`
  ending (null when absent), and the summary and wins from the series object. The
  stakes are those the game had at tip-off, from the
  series wins entering it (for a final game the winner's win in the series object
  is subtracted); they are null without a game number. The first rule that
  matches applies: `game_7` for game number 7;
  `clinched` for a final game whose winner has 4 wins; `can_clinch` when one side
  has 3 entering wins and the other fewer; `elimination` when a side has 3
  entering wins on a game that is not the seventh; otherwise null. In the play-in,
  `nine_ten` and `eighth_seed` are `elimination` and `seven_eight` has none.
  The mark never fails the feed: an unreadable series object or an unknown
  competitor id only nulls the summary and the stakes, and a play-in note that
  cannot be read makes the mark null, logged by event id only.
- An All-Star game ([ADR 0038](../adr/0038-all-star-marks-in-core-feeds.md)) is
  a regular season game (type 2) whose competition type is `ALLSTAR`. Its sides
  are guests with a null city, read by code or name like any side
  ([ADR 0039](../adr/0039-all-star-sides-by-code-or-name.md)): a game with a
  side that has neither is skipped. The `allStar` mark is read from the note
  `NBA All-Star - <round>` with an optional format suffix, or is the whole note
  "ALL STAR GAME" or "NBA All-Star Game" in any case, which is the round
  "All-Star Game" ([ADR 0051](../adr/0051-all-star-notes-and-untimed-games.md));
  `championship` is true for the round `Championship`. A final All-Star game with
  a score and no line score is kept with a null `lineScore`. An All-Star event that cannot be mapped (an
  unreadable note, an unknown status, a side code the league owns, or a required
  field missing for its status, such as a final without a score or a live game
  without clock) is skipped with a log line by event id, and so is an All-Star
  game whose live detail cannot be fetched or that fails the game rules. Neither
  fails the day or the feed. Any other game that fails still fails the day, as
  before.
- A guest side is a team outside the 30 ([ADR 0025](../adr/0025-guest-teams.md)):
  `guest` is true and its code is the source's own, null when the source sends
  none ([ADR 0026](../adr/0026-one-guest-team-rule.md)). A side with neither a
  code nor a name is not a team: the adapter skips its game and the feed
  publishes the others. It has no star, so
  `stars` is null exactly on a guest side, and its leader may have no photo.
  Its names are not links on the front end, and a game with a guest side is
  never in the hero.
- The leader is the team's top scorer by points. A tie on points goes to
  the tied player with the most rebounds plus assists, and a tie on both
  to the first of them in the provider's order
  ([ADR 0009](../adr/0009-game-leader-selection.md)).
- `TeamStats.turnovers` is the team's `totalTurnovers` when the source sends it,
  which includes turnovers charged to the team, else its `turnovers`
  ([ADR 0052](../adr/0052-box-score-reading.md)).
- Stars: the order is the current season's leaders, then the current
  roster players' individual averages for the current season, then the
  previous season's leaders, then the individual averages for the previous
  season. The first step that picks a roster player wins. A 404 from the
  averages source means that season has no statistics yet. A failed
  individual request moves on to the next step. A team that no step picks
  keeps its last known star
  ([ADR 0014](../adr/0014-star-guarantees.md)).
- `winner` is set by the games job from the final score: the side with more
  points, `away` or `home`. A final game whose score is tied has no winner, so the feed is
  invalid and the previous one stays published.
- `statsAvailability` is set by the games job for a final game: `available`
  when it holds the game's detail, `unavailable` when no detail is held and
  all four attempts failed, `pending` otherwise
  ([ADR 0010](../adr/0010-final-game-attempts.md)).

## Refresh behavior

The cadences of [`docs/source-rules.md`](../source-rules.md)
([ADR 0020](../adr/0020-source-rules.md)): the schedule and stars refreshed
once a day in the morning US Eastern time; the day change of
[ADR 0013](../adr/0013-day-change.md); every minute from a game's scheduled
start until it is live; while it is live, every 30 seconds with someone
present (a feed request in the last 5 minutes) and every 2 minutes with
nobody, with each live game's detail; highlights one attempt 1, 2 and 3 hours
after the final time; a final game's detail when it becomes final and, after
a failure, 2, 4 and 6 hours after the final time.

- A games feed request that finds a live day refreshed 30 seconds ago or more
  triggers one immediate refresh, shared by concurrent requests, and waits for
  it up to 20 seconds.
- With no live game the live refresh stops, and resumes at the start time of
  the next game.
- The games job also starts the build of a final game's detail feed at the
  same attempt times (see [game detail](game-detail.md)), without waiting for
  it.

- The stars of all teams are fetched concurrently in their own task and never
  delay the live refresh. After a start, no games feed is published until
  every team has a star ([ADR 0014](../adr/0014-star-guarantees.md)).
  The stars job records a success only on the run that stores the star of
  the last team still pending that day; a run that leaves a team waiting for
  its retry records none, so the health report does not show the stars as
  done. Each team's roster and season leaders are reused for 24 hours
  ([source rules](../source-rules.md), rule A). A roster player's individual
  averages are requested only when no roster player is among the leaders,
  and are reused until the team has a final game whose final time is after
  the fetch, so such a team costs at most one request per player per game
  played, never per day ([source rules](../source-rules.md), rule F).

- The morning fetch runs at `DAILY_FETCH_TIME` (US Eastern, `HH:MM`, default
  06:00).
- The middle day of the feed changes at US Eastern midnight. While any game
  of the previous day is live, the previous day stays the middle day; the
  first run after none is live moves the window to the new day, fetching the
  days not held yet. The morning fetch refreshes the 7 days shown and never
  moves the window.
- A game's final time is stored when the job sees it become final. A game
  already final the first time the job sees it takes that moment as its final
  time, and its highlight attempts run right away, 1 and 2 hours later. A
  stored final time is never overwritten.
- Each highlights run lists the channel's uploads once, paged back until
  every due game is matched or a video is older than the oldest due game, and
  matches every due game against that list
  ([source rules](../source-rules.md), rule E). A game matched on a page read
  before an invalid page keeps its match. A highlight attempt is used up
  whenever the lookup ends other than in a failed request: with a match, with no match, on a body that is not JSON
  or an invalid payload, on a missing highlights source setting (no request is sent), on a missing
  embed setting (found only after the uploads were paged and the thumbnails
  checked, so requests were sent), or with
  a matched video whose thumbnails the image host does not serve. A failed
  request is a timeout or a transport failure on any request, or an error
  status from the uploads listing. It uses up no attempt: it is logged and
  recorded in the job's health, and the same attempt is retried no sooner
  than 10 minutes later; a failed request on the listing does this for every
  due game of the run, and one on a thumbnail check only for that game
  ([ADR 0018](../adr/0018-highlight-request-failures.md)). An error status
  on a thumbnail check means the thumbnail is not served, not a failed
  request.
- Highlights backfill: once a day at `DAILY_FETCH_TIME`, in its own task, a
  job pages the channel's uploads back from the newest for the final games
  whose highlight attempts are over and that have no highlight, at most
  `HIGHLIGHTS_BACKFILL_PAGES` pages a day. The next day it continues from the
  stored page token and never reads a page again for the same games. A match
  is stored like the live ones, so this feed and the game detail serve it; the
  first match in channel order is kept and never replaced (a re-upload does not
  change it). A failed page read stops the day's step, is recorded in the job's
  health and keeps every match and the resume point
  ([source rules](../source-rules.md), rule E, and [ADR 0048](../adr/0048-highlights-backfill-and-edition-video.md)).
- An All-Star game has empty `highlights` in this feed and in the game detail.
- The stats attempts of a final game are at its final time and 2, 4 and 6
  hours after it. Failed attempts are stored, so they survive a restart. After
  the fourth failure the game is `unavailable` and never fetched again.
- With the morning fetch (and on the first run after a start), the stored
  final time and stats attempts of every game dated more than 30 days before
  the current US Eastern date are deleted
  ([ADR 0011](../adr/0011-state-retention.md)). Highlights are kept.

## Endpoint

- `GET /feeds/games.json` serves the last published feed with
  `Cache-Control: public, max-age=10` and an `ETag`.
- It responds 304 with no body when `If-None-Match` matches the current
  `ETag`.
- It responds 503 with `{"detail": ...}` before the first publication.
- An invalid feed is never published: the previous valid one stays served.
