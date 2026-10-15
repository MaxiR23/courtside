# 0043. Season feeds and franchise names

- Status: Accepted
- Date: 2026-10-15

## Context

Issue 249. The calendar, the day and the past game detail feeds (ADR 0040, 0041
and 0042) let a visitor reach any day since 1994. The standings, team and player
pages have no feed for a past season. The team page also needs the identities a
franchise had (its names), and the player feed has no answer for a retired
player or for a player known only from a past roster or box score.

## Decision

- **Paths, ids and kinds.** Three feeds, each its own kind of the on-demand
  cache:
  - `/feeds/seasons/{season}/standings.json`, kind `season-standings`, id
    `{season}`.
  - `/feeds/seasons/{season}/teams/{code}.json`, kind `season-teams`, id
    `{season}-{code}` with the lowercase standard code.
  - `/feeds/seasons/{season}/players/{player_id}.json`, kind `season-players`,
    id `{season}-{player id}`.

  A valid season is four digits from 1994 to the season before the current one.
  Any other season answers 404 with no source request, and every season path
  answers 503 while the stars job does not know the current season. Each feed is
  built once and kept (rule G): it is never refreshed and never deleted.
- **Adapter reads.** A past read sends the season as the season query value:
  the division standings, the player game log, the player stats (with the
  `seasontype` of the playoffs when it applies) and the team schedule, which
  already sent it. Team resolution on a past read is by provider id first (the
  abbreviation of a past season may not be one of the 30). The past division
  standings are read once and have no rule L fallback: a response that is not of
  the requested regular season fails the build.
- **Standings.** `state` is `final` whatever the games played, the clinchers are
  the source's, and the colors are today's.
- **Team, values of the season.** `city` and `name` come from the season team
  object, the colors are today's. `record` is that season's standing, with
  `playoff` null before the 2020-21 season (the play-in did not exist, so the
  seed ranges of `PlayoffPosition` do not describe it); `conferenceRank` still
  shows the place. `divisionRank` is now 1 to 8: until 2003-04 a division held up
  to 8 teams. The leaders are that season's averages with no previous-season
  fallback.
- **Team, roster and schedule.** The roster is the season roster, every status
  `active`, with ages on February 1 of the end year (the calendar's anchor day).
  The schedule has the regular season and the playoffs with `detailAvailable`
  false, because no game of a past season is in the days shown.
- **Team, null blocks and 404.** `arena`, `coach`, `injuries`, `nextGame`, `cup`
  and `titles` are null. `PastTeamFeed` replaces only the current-season block
  rule of `TeamFeed`, as `PastGame` and `PastGameDetailFeed` do (ADR 0040, 0041);
  its schema is the team schema. A franchise with no team object, or an inactive
  one, that season answers 404 after that one read, remembered in memory: the
  cache answers unknown after a build that learns the id is unknown.
- **Player, values of the season.** The game log, the last games and the All-Star
  year come from that season's game log. The bio takes no season, so the summary
  is that season's per game stats row, with every `rank` null. The averages and
  the milestones are that season's rows and the career's. `seasons` and `awards`
  are the career. Ages are on February 1 of the end year. `team` is the team of
  the log's newest game that is neither an All-Star nor a preseason game, found
  by provider id, with the name and city of that season; it is null for a season
  with no game log. `injury`, `nextGame` and `live` are null and `seasonLabel` is
  set. `PastPlayerFeed` replaces only the current-season rule.
- **Known player ids.** An id is known from a current roster, from the roster of
  a stored past team feed or from the box score of a stored past game detail,
  read once per stored file. The current player feed serves such an id with no
  roster: `team` is null and so are `nextGame`, `live` and `injury`, and `active`
  is the state of the athlete object, true or false. A free agent known from a
  past roster or box score is therefore served, not 503. Its feed expires 7 days
  after its build. An unknown id still answers 404 with no source request.
- **`active`** is a new field of the player feed, read from the athlete object
  (the player draft response); a stored feed from before it reads as true.
  `seasonLabel` is null on the current feed.
- **Names.** The franchise names are a list of runs (`from`, `to`, `name`,
  `location`, `code`), read from the season team object for every season from
  1994 to the current one. Consecutive seasons with the same identity are one
  run, a skipped season does not split a run, and `to` is null on the run that
  holds the current season. A season whose read fails, or that has no active team,
  is skipped with a log line that carries the code and the season. The list is a
  stored, non-public kind (`team-names/{code}`), read once per team and kept 7
  days. Both team kinds depend on it, so a missing or stale list is built first
  inside the request's budget. A build whose current season could not be read
  (the read failed, or it has no active team) fails and keeps the stored list, so
  the current run is never closed by a failed read. The names are written into the stored team feed and set again at
  serve time, so a team feed kept for good shows newer runs.

## Consequences

- The provider keys are assumed, not recorded, as `header.season.year` was in
  ADR 0041: the season team object's keys (`id`, `abbreviation`, `displayName`,
  `name`, `location`, `isActive`), the shape of the season roster (the athletes of
  the current roster, with no season or team keys read), and the athlete object's
  `active` and identity keys (only `draft` is recorded in a fixture). A wrong
  guess fails every build of that feed with an invalid payload (503, logged,
  retried after 10 minutes). It never publishes a bad feed.
- A past team season reads one extra source per team and season, and the first
  current team feed of a team makes up to 33 season team reads inside its budget.
  A slow source can turn that first request into a 503; the shielded build still
  finishes and is stored.
- A retired player's current feed is deleted after each stars run (rule J) and
  rebuilt on its next request.
- Old seasons may lack stats the division standings adapter requires; the
  standings and team builds of such a season fail with a reason in `/health`.
- No page uses these feeds yet. The front end reads null `arena`, `injuries` and
  `team` with the smallest change of its props layer; the pages come with issue 6.
