# 0041. Past game detail

- Status: Superseded by 0048 for the past game's highlights only, and by 0052 for the values inside the box score and team stats only, and by 0053 for the ids it knows only, and by 0057 for the past game detail's leaders only
- Date: 2026-10-15

## Context

Issue 245. The page for past dates links to the detail of a game of a past day.
The game detail feed serves only the games of the days shown (rule I), and its
model requires a record on every league side and describes today: injuries,
last games, standings, the season series with arenas from the current schedules.
A past game has none of that. A stored day feed (ADR 0040) already holds the
final games of a past day with their score, winner, marks and sides.

## Decision

- **Which ids.** A past game id is a final game of a stored day feed that the
  games job has not loaded. A game of a day feed that is not final (scheduled,
  postponed, canceled), and an id in neither, answer 404 with no source request.
- **The route stays** `/feeds/games/{id}.json`. A past game is its own feed kind,
  stored as `past-games/{id}`. It is built once on request under rule G and
  served under rule H, kept (rule D), never refreshed by the games job, the live
  refresh, the highlights job or the attempts of ADR 0010, and never cleaned up
  (rule J). A failed build answers 503 while nothing is stored and is not
  retried for 10 minutes. A game the games job has loaded always takes the games
  path.
- **The build reads** the stored day feed's game (status, time, scores, winner,
  marks, sides by team id first with the event's name and city, and the search
  URL) and one game detail summary (venue, box score, team stats, win
  probability and the season), with sides by team id first and no injuries or
  season series read.
- **Null on every past game:** `stars`, `injuries`, `lastGames`, `standings`,
  `seasonSeries`, `highlights` and both `record`s. The source reads no record,
  and the season series arenas would come from today's schedules. **Null when
  the source lacks them:** `boxScore`, `teamStats`, `winProbability`,
  `winProbabilityLeader` and `winProbabilityPeriods`. This is the choice for the
  blocks the design does not name.
- **A new nullable `seasonLabel`** (`2004-05`), set from the summary's event
  season on a past game and null on a game of the games feed days. A summary
  without a readable season fails the build.
- **`PastGameDetailFeed`** replaces only the league-side rule of
  `GameDetailFeed`, as `PastGame` did for `Game`. Its schema is the game detail
  schema.

## Consequences

- The first request after a restart reads every stored day feed once to rebuild
  the index of past ids; a day with every game final is read once.
- The stored search URL is not rebuilt when `HIGHLIGHTS_SEARCH_URL` changes.
- The season is read from the summary's `header.season.year`, which no recorded
  response confirms. If the provider puts it elsewhere, every past build fails
  with no season and answers 503.
- No web change until the page for past dates uses the feed.
