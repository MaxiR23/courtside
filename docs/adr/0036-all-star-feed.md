# 0036. All-Star feed

- Status: Accepted
- Date: 2026-10-14

## Context

Issue 229. The All-Star page needs the edition (date, venue, format, teams, their
placement and the games with box scores, team statistics, leaders and Top 5), the
MVP and the recap of the previous edition. The number of teams and rounds changes
every year (2, 3 or 4 teams). The games appear in no team schedule, so the
backend has to find the day itself. The All-Star section is seasonal: it must be
removable without touching the core feeds (principle 5). The playoffs finals feed
(ADR 0033) is the precedent of a seasonal feed with one id and per game reads.

## Decision

- **Kind, id and storage**: feed kind `all-star`, the only id `league`, stored as
  `all-star/league`, served at `/feeds/all-star.json` under rules G and H. The
  models are in `api/app/feeds/all_star.py`, the builder and kind in
  `api/app/jobs/all_star_feed.py`.
- **Discovery**: a job, `api/app/jobs/all_star_discovery.py`, because it runs daily
  with no request. It runs in the stars job's scheduler, after the stars job, so its
  reads never delay the live refresh (ADR 0014) and it has the season. For the
  current season, then the previous one, it reads the scoreboard days from February 1
  to March 7 of the season's end year in order, at the daily fetch time, and stops at
  the first day with All-Star games. A stored season is never scanned again; a season
  with none is scanned again the next day. A failure is retried after 5 minutes.
- **State table**: the edition (season, date, game ids as JSON) is kept in a new
  table `all_star_editions` of the state database, migration 5, and the time the
  feed first saw each All-Star game final in `all_star_finals`, migration 6, with
  four store methods in all, as every persisted job state lives there. The previous edition is
  therefore discovered once and kept across restarts.
- **State rule**: `before` while no game is live or final (including none
  discovered), `live` while a game is live or some, not all, are final, `after` once
  there is a game and every game is final. Canceled games are dropped. The issue's
  wording "no games of the edition" is read as "no game has begun", because an
  edition with discovered scheduled games is still before it starts and its date is
  only known from discovered games.
- **Two views, core adapters unchanged**: `api/app/sources/all_star_scoreboard.py`
  reads the same scoreboard day with the same freshness (one shared cached
  response) and keeps the All-Star games, their note and status text, and sides that
  need no city. `api/app/sources/all_star_detail.py` reads the same game summary and
  maps the format, attendance, broadcasts, jerseys and positions. Both import private
  names from the core adapters, as `postseason_scoreboard.py` and `finals_plays.py`
  do. The leaders, box score and team statistics use the core game detail adapter
  unchanged.
- **Reads and freshness**: per game, the leaders, the sections and the extras read
  one URL with one freshness: the live interval for a live game, 1 hour for a game
  not started, and for a final game the time the feed first saw it final. The core
  never stores a final time for an All-Star game (its scoreboard adapter requires a
  city), so the first build that sees a game final stores that time in
  `all_star_finals`, before the reads, and never overwrites it; a summary fetched
  before it (for example while the game was live) is read again. The previous
  edition is finished data: every rebuild reads its scoreboard day and its games'
  details with a 24-hour freshness, so they are requested about once a day and not
  every 30 seconds. Team infos (league teams in the box scores) and the season
  awards keep their own freshness.
- **Failures**: a failed current scoreboard day fails the build and keeps the stored
  feed. Anything else (a detail, sections, extras, a team info, the awards, or the
  previous edition) only nulls its part. The season unknown and an invalid feed fail
  the build.
- **Expiry**: rule G. Stale 30 seconds after the build while `live` or on the
  edition's date; a request that finds it stale waits for the rebuild
  (`wait_when_stale`), as the game detail does for live data under rule C. Before the
  edition, stale when the discovery runs after the build. Once every game is final,
  kept while its season is the current one, but only when it was built at least 1
  hour after the latest first-seen-final time of its games; before that it is stale
  30 seconds after the build, so the box scores are read again after the games end.
  Stale once the season changes.
- **Serve time**: the stored highlight of a game as a list of one, else null; never
  stored.
- **MVP**: the first winner of the award `all_star_mvp` of the season awards (the
  adapter matches awards by name, so no award id is read), with one line per final
  game in which he has a box row and the day totals. The feed carries parts (result,
  scores, opponent), not prose.
- **League team**: resolved by player id from the stars job's rosters, with the
  team's colors from the team info; null when the player is on no roster.
- **Seasonal isolation**: core touches are wiring only (`main.py`, the feeds router,
  the schema registry and the contract script), plus the state table and its two
  store methods (four with the finals table). The feed imports `AwardCode` from the playoffs models, as the season
  awards adapter does. Removing the section removes the methods and leaves the tables,
  because shipped migrations are never removed.

## Consequences

- While a season is not discovered (October to February) the discovery makes up to 36
  sequential scoreboard reads a day, and the same for a previous edition that the
  source does not have.
- An `after` feed built before the source publishes the MVP keeps a null MVP for the
  season, as ADR 0033 accepted for the Finals MVP.
- An edition whose Championship is created only after every earlier game is final is
  `after` and kept until the season changes.
- The core games feed's handling of All-Star sides (the scoreboard adapter requires a
  city on every side) is the concern of the marks issue.
- The provider keys for the format, attendance, broadcasts, jersey and position are
  documented in `docs/api/all-star.md`; a different key only nulls that field.
