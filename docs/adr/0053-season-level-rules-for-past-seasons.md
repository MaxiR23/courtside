# 0053. Season level rules for past seasons

- Status: Superseded by 0055 for the reuse of stored past game players only, and by 0056 for the concurrency of past game reads only, and by 0057 for the staleness of a stored past game detail only, and by 0058 for the past playoffs and Finals rosters only, and by 0059 for the past team and player rosters, the past player's number and the names of the past day, team, player and standings sides only
- Date: 2026-10-17

## Context

Issue 267. The audit of the past season feeds found rules that hold for a whole
season, not for one game. A franchise that has an object for a season but is not
active today (the SuperSonics, Seattle) was treated as absent. The roster of a
past team came from today's roster of the franchise, so players of that season
were missing and players of today were shown. The league sides of a past
schedule, game log, day and standings were named as today's franchise. The past
Cup placed its quarterfinals by today's seeds, which the 2023-24 and later
tables no longer give. A single-game All-Star edition had no champion. A stored
past feed could not be rebuilt when its rules changed.

## Decision

- A team exists in a season when the season team object answers. `isActive` is
  never read. A 404 still means no team that season. The franchise names list
  therefore has one run per identity from 1994 (Seattle to 2008, then Oklahoma
  City) and the season selector reaches every season.
- The roster of a past team is the players with a stat line in the box scores of
  the team's final regular-season and playoff games of that season. Name and
  photo come from the newest game of the player, jersey and position from the
  newest game that has a value, else they are null. Height, weight, age, birth
  date, birthplace, college and experience are null and the status is `active`.
  A game is read once and kept in the state database (`past_games`), shared by
  both teams of the game. A stored past game detail is reused with no read; its
  players carry no jersey or position. The same rosters name the leaders and
  award winners of the past playoffs and the Finals averages, and a failed
  roster read fails the build. A player on two rosters of a season (traded) has,
  in the leaders and awards, the team of his newest final game of that season. The number of a past player is the jersey of the
  box scores of the team of the newest game, never the athlete's.
- A team leader may have a null `position`: the box score's position may be
  absent. `PlayerFeed.position` stays required.
- The league sides of a past team schedule, player game log, day feed and
  standings are named by the season team object (name and city), with today's
  code from the fixed id map. The names timeline keeps the season team's own
  abbreviation. A guest side keeps its name.
- `detailAvailable` is true for every final game of a past team schedule and a
  past player game log. The date of each of those games is registered in
  `past_games`, and the past game detail kind (ADR 0041) knows a registered id
  as well as a final game of a stored day feed: it builds that day feed first.
  This supersedes the "which ids" rule of ADR 0041. The past Cup, Cup matchup,
  playoffs and Finals feeds keep `detailAvailable` false.
- The two quarterfinals of a conference in a past Cup are placed by start time,
  then id, with a seed label of no seed. A third quarterfinal in a conference
  fails the build. Semifinals and the championship are placed as before.
- The only game of an All-Star edition with one game is its championship,
  whatever its round, so its winner is the champion and its loser the
  runner-up, and its recap carries the MVP. Two distinct sides of an edition
  that share a name are drawn with their code and their name, "EAST All-Stars".
- The league side's identity in a past season is always read from that season's
  team object (the source cache serves a repeat read), never from a stored
  franchise-names list, so a list built under an older rule cannot name a
  season wrongly.
- The eight kept season kinds (standings, team, player, Cup, Cup matchup,
  playoffs, Finals, All-Star), the past day feed and the past game detail stamp `buildVersion` with `SEASON_BUILD_VERSION`.
  A stored feed of another or no version is stale: the next request serves it as
  stored and rebuilds it in the background, and a failed rebuild keeps it. A
  change to these rules bumps the constant. The current feeds carry a null
  version. A past day feed is rebuilt this way only when every game is final; a
  past game detail is built from a day feed of the current version, which the
  cache makes current first.

## Consequences

- Ten schemas (the eight kinds, days and game detail) gain a nullable `buildVersion` and the team schema a nullable
  leader `position`. The front end types are regenerated. The pages draw the new
  data in the web issue that follows; a null Cup seed label draws as seed 0 until
  then.
- A past team or player feed reads about 90 summaries when cold, and a past
  playoffs feed about 1,300, at most `MAX_GAME_READS` at once. Every summary stays
  in the source cache, which has no pruning, so the state database grows by those
  bodies once per season requested. A cold past playoffs build takes minutes and
  its requests answer 503 until it is stored.
- The first request after a deploy serves the old stored feed while the rebuild
  runs.
- A day feed or past game detail stored before the deploy is rebuilt on its next
  request, so no past side keeps today's name. The `team-names` lists are read
  only for the timeline of the team feeds; the season feeds never read them.
- A registered game that the day feed does not list as final answers 503 on its
  detail request.
- ADR 0043 is superseded for team existence, past rosters and the names of past
  sides, ADR 0045 for the past quarterfinal slots, ADR 0046 for the past rosters,
  ADR 0047 for single-game editions and ADR 0041 for the ids it knows.
