# 0032. Playoffs feed

- Status: Superseded by 0035 for its scoreboard function only, and by 0060 for the series values, the complete state and the champion's Finals result only
- Date: 2026-10-14

## Context

Issue 217. The `/playoffs` page (`docs/design-playoffs.md`) needs the picture
tables, the play-in, the bracket of 15 series, the champion, the postseason
leaders and the season awards. No feed has this data, and the design marks the
postseason as a seasonal section: it must be removable without touching the core
feeds (principle 5). The scoreboard shows each postseason game with a season type,
a competition type, a note with its game number and a series object that holds the
wins, the summary and whether the series is complete. The stars job holds the
season of the latest roster and the rosters themselves.

## Decision

- **Route and rules**: `/feeds/playoffs.json` is built on demand under rule G and
  served under rule H, with the fixed id `league`, stored as `playoffs/league`. It
  is the fourth singleton kind, after the standings, search and Cup feeds, and the
  second seasonal one.
- **Reads**: the play-in and postseason windows (season types 5 and 3), the
  division standings, the 30 team infos (null colors on failure), the postseason
  leaders, the season awards and, only from the first US Eastern day of the
  play-in window, every scoreboard day of both windows. Before that day no day is
  read: the state is `picture` and no postseason game can exist. The champion's
  postseason record is read only once the Finals series is complete. The regular
  season window can be read by the adapter, but the feed never reads it.
- **Season**: the end year of the latest roster the stars job fetched. Until a
  roster is fetched, or until every roster is, the feed answers 503 when nothing is
  stored.
- **Settings**: `SEASON_TYPE_URL` (`{season}`, `{type}`), `POSTSEASON_LEADERS_URL`
  (`{season}`), `TEAM_POSTSEASON_RECORD_URL` and `TEAM_POSTSEASON_STATS_URL`
  (`{season}`, `{team_id}`) and `SEASON_AWARDS_URL` (`{season}`). The statistics
  adapter ships here for the finals feed, its first reader.
- **Scoreboard function**: `fetch_postseason_games` in its own seasonal adapter,
  `api/app/sources/postseason_scoreboard.py`, reads the same URL, and so the same
  cache entry, as `fetch_games`, and adds the season type, the competition type, the
  first note, the period of a game in play or final and the series object. The
  scoreboard adapter does not change, and `ScoreboardGame` does not change either,
  because the games feed dumps it into a model that forbids extra fields.
- **State**: `complete` when the series object of a Finals game says completed;
  else `finals` when any Finals game was read; else `playoffs` when any round 1
  game is live or final; else `playin` on or after the first day of the play-in
  window; else `picture`.
- **Stages**: a stage is complete when all its games are final (play-in) or all its
  series are complete (8, 4, 2 and 1), in progress when started and not complete,
  next when it is the first stage after the last one complete or in progress, and
  upcoming otherwise. The current round is set only in `playoffs`.
- **Bracket**: 15 series in a fixed order. Round 1 is placed by the seed pair
  (1v8, 4v5, 3v6, 2v7); the seeds 7 and 8 are the winners of the 7th vs 8th game
  and of the 8th seed game, so the bracket does not depend on the source updating
  the seeds after the play-in. Later rounds are placed by the series their teams
  came from. Wins, summary, status and winner come from the series object, never
  counted from the games. A game or team that cannot be placed fails the build, as
  in the Cup.
- **Play-in**: the three games of each conference are placed by their note. The
  higher place hosts. The 8th seed game takes the loser of the 7th vs 8th game and
  the winner of the 9th vs 10th game. In `picture` the place slots carry the
  standings team as `currently`.
- **Preseason**: when the standings are of another season (rule L) or every team has
  0 games, the picture rows keep the conference order and carry no seed, record or
  clinch, and no side carries `currently`.
- **Champion**: the Finals result from the series object, the Finals dates, the
  postseason record, home and road, and the point differential over the champion's
  final postseason games only. There is no drawing flag: nothing in the backend can
  decide it. The Finals MVP averages ship with the finals feed.
- **Leaders and awards**: names and photos come from the rosters the stars job keeps
  (the way the search feed names players), never from following a link. A leader or
  winner on no current roster is left out; a leader keeps the rank of its position
  in the source list; an award with no winner is dropped. Award names are matched
  ignoring case against a fixed table; an unknown name with winners is logged by
  name and skipped.
- **Expiry**: rule G. 1 hour after a final postseason game that follows the build (a
  game of the feed, or a final game of the games job dated inside the postseason
  dates); 7 days after the build; at US Eastern midnight of the play-in start when
  the build precedes it, so a feed built in `picture` does not stay `picture`
  through the first play-in day. While the state is `picture` the feed also
  expires 1 hour after any final game of the league that follows the build, as the
  standings feed does, so the picture tables never trail the standings. Once the
  Finals series is complete the feed is kept while its season is the current one,
  as the Cup is.
- **Failures**: a failed season type, standings or scoreboard day read fails the
  build and the stored feed is kept; so does a postseason game that cannot be
  placed. A game not yet live or final with an undecided side is ignored, and a live
  or final game with a team outside the league fails the build. A failed leaders read gives `leaders: null`, a failed awards read
  `awards: null`, a failed team info read null colors and a failed record read null
  record, home and road.
- **Seasonal isolation**: the feed has its own `PlayoffStageStatus`, with the same
  four values as the Cup's `StageStatus`, by owner decision. Under the convention
  rule an enum with the same values is normally a second shape; it was chosen so
  that neither seasonal section imports the other. The playoffs files import
  nothing from the Cup section.

## Consequences

- A cold build costs 2 season type reads, 1 standings read, 30 team infos, 1 leaders
  read, 1 awards read, about 70 scoreboard days from the play-in start, and 1
  record read when complete. The scoreboard days share the 30-second source cache
  entry with the games job; the other reads share the 1-hour cache with the
  standings and search feeds.
- The feed answers 503 until the stars job knows the season and has fetched every
  roster when nothing is stored.
- Removing the section removes `api/app/sources/postseason_scoreboard.py`
  (`fetch_postseason_games`, `PostseasonGame` and `SeriesState`). It touches nothing
  of the scoreboard adapter or of the Cup section, and removing the Cup touches nothing of this one. The playoffs feed has
  its own `PlayoffStageStatus`, an owner decision that accepts an enum with the same
  values as the Cup's `StageStatus`.
- While the state is `picture`, the feed also expires 1 hour after any final game of
  the league that follows the build, as the standings feed does. So the picture
  tables never trail the standings, at the cost of up to one rebuild per final
  regular season game: 2 season type reads, 1 standings read, 30 team info reads, 1
  leaders read and 1 awards read, all through the 1 hour source cache. No scoreboard
  day is read in `picture`.
- The payload shape of each configured URL is part of the contract of the settings
  and is documented in `docs/api/playoffs.md`.
- An award name outside the table is dropped and logged by name.
- Links in the source's payloads are never followed.
- The leaders and awards are as current as the 1-hour source cache and the feed
  expiry.
