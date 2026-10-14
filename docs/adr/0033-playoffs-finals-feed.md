# 0033. Playoffs finals feed

- Status: Accepted
- Date: 2026-10-14

## Context

Issue 219. The Finals page needs the Finals games with their leaders, the win
probability curve and the largest deficit, the Finals MVP with his averages, the
road of each finalist, the head to head and the postseason averages of both
rosters. The playoffs feed (ADR 0032) holds the series, the games, the picture
tables and the awards, and says "The Finals MVP averages ship with the finals
feed". The Finals is a seasonal section: it must be removable without touching
the core feeds (principle 5). The Cup matchup feed (ADR 0029) is the precedent of
a feed built from another stored feed.

## Decision

- **Kind, id and storage**: feed kind `playoffs-finals`, the only id `league`,
  stored as `playoffs-finals/league`, served at `/feeds/playoffs/finals.json`
  under rules G and H. The models are in `api/app/feeds/playoffs_finals.py`, the
  builder and kind in `api/app/jobs/playoffs_finals_feed.py`.
- **404 and 503**: the on-demand check is synchronous and reads no source, so it
  cannot tell "no Finals game" from "no playoffs feed stored". The route serves the
  playoffs feed first (as the game detail and player routes do work before the
  cache) and answers 503 when it is unavailable; then it serves the finals kind
  with the budget left. The check answers unknown for an id other than `league`,
  for a stored playoffs feed of another season and for a Finals with no game (404),
  and not ready when no playoffs feed is stored. The kind depends on the playoffs
  feed, so a stale one is rebuilt first.
- **Games**: the final Finals games of the stored playoffs feed in number order,
  each with its series game as the playoffs feed stores it (the Cup matchup feed
  does the same with the slot's game). A live or scheduled game is not listed.
- **Curve team**: the champion when the series is complete, else the side with more
  wins, else the top side (the East team). Its win probability is the source home
  value when it is home and one minus that value otherwise, to 3 decimals, with the
  period boundaries of the game detail feed.
- **Largest deficit**: the most points the curve team trailed by over the plays
  with both scores, with the game second of the first play at it; null when it
  never trailed, no play has both scores or the read failed.
- **Game detail reads**: leaders (`fetch_game_detail`), curve, periods and box
  score (`fetch_game_detail_sections`) and the play scores (`fetch_play_scores`, in
  its own seasonal adapter, `api/app/sources/finals_plays.py`) read one URL with one
  freshness, so they cost one request per game: the game's final time when known,
  else 1 hour. The core game detail adapter does not change.
- **Finals MVP**: the first winner of the playoffs feed's `finals_mvp` award; games,
  points, rebounds and assists from the season row of his postseason player stats;
  the best game is his line with the most points in the box scores of the listed
  games, the earliest game on a tie. Null when the playoffs feed has no such award.
- **Player stats freshness**: `fetch_player_stats` is used unchanged, with its fixed
  1 hour freshness; it has no freshness parameter and adding one would change a core
  adapter. The bound of rule F still holds: a build reads each player id once, the
  feed is rebuilt only when it expires (a postseason final game plus 1 hour, a
  playoffs rebuild, or 7 days), and it is kept once the series is complete.
- **Road**: per finalist the seed, the regular season record from the playoffs
  feed's picture, the postseason record, and every bracket series against a team in
  round order with the opponent, its seed, the wins and losses and the result.
- **Head to head**: 8 bars in a fixed order from the postseason team statistics,
  percentages as fractions. The higher value is better, except technical fouls,
  where the lower is; a total as the source sends it. No better with an equal or a
  null value. The records are the postseason record of each
  finalist, as in `road`.
- **Averages**: the roster of each finalist from the stars job, without players
  whose team changed, in jersey order, with the postseason averages of the season; a
  player with no values last.
- **Expiry**: rule G. Fresh when the series is complete and the season is the
  current one (or unknown). Otherwise stale when the playoffs feed was rebuilt after
  the build, 1 hour after a postseason final game that follows the build, and 7 days
  after the build.
- **Serve time**: the stored highlight of a game as a list of one (null without
  one) and `detailAvailable` from the loaded games; neither is stored.
- **Failures**: the build fails and keeps the stored feed when the season is
  unknown, no playoffs feed of the season is stored, the Finals has no game or a side
  without a team, or the feed is invalid. Every other read only nulls its part.
- **Seasonal isolation**: only wiring changes in core modules (`main.py`, the feeds
  router, the schema registry and the contract script). The seasonal adapter imports
  private names from the game detail adapter, as `postseason_scoreboard.py` does
  from the scoreboard adapter. Nothing imports the Cup section.

## Consequences

- A cold build costs up to 7 game details (one request each), 2 postseason records,
  2 postseason statistics and one player stats read per roster player (about 30).
- The cost of player stats is bounded by rule F through the feed's expiry, not by a
  per player freshness.
- A missing playoffs feed answers 503 before any finals read, and a finals request
  can start a playoffs rebuild.
- If the source publishes the Finals MVP after the deciding game's feed is built,
  both feeds keep the season without it, a consequence of keeping a complete feed.
- Removing the section removes `api/app/sources/finals_plays.py`, the finals models,
  module and route, and touches no core adapter. The play score field names are
  documented in `docs/api/playoffs.md`; a different name only nulls the deficit.
