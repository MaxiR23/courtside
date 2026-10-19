# 0064. Degrade one bad item instead of failing a feed

- Status: Accepted
- Date: 2026-10-19

## Context

Issue 295 and findings E1 to E7 and B7 of the audit of commit 2927a09. One bad
item failed a whole feed and kept the last valid one: a scoreboard event with
no venue or an unknown status failed the games feed for every day shown, a
failed live detail failed the run, a team missing from the standings failed the
game detail, a division stat that was missing failed the standings, team and
search feeds, a team with no alternate color or franchise venue failed its team
page, and a season without a team object was requested again on every build.

This replaces three rules in force. ADR 0038 says a league game keeps failing
the run when its event cannot be read or its live detail fails. ADR 0043 says a
names build whose current season could not be read fails and keeps the stored
list. Rule D of `docs/source-rules.md` says a final game's detail is built with
the ADR 0010 attempts and never again.

## Decision

One game or team that cannot be read is skipped, or has that block null, with a
log line naming its id or team code. It never fails the feed.

- The scoreboard's current-day read, `fetch_games`, skips any event that cannot
  be mapped, with a log line by event id, as the past-day read already does. A
  missing venue, or one with an empty name, is a null `venue`. The skip lives in
  `fetch_games` and not in the shared event mapping, so the postseason read,
  which counts each series from its final games (ADR 0060), still fails on a bad
  league event. An event that fails the provider model itself (no `date`, or no
  status name) still fails the payload, as it does for an All-Star event.
- `Game.venue`, `PlayoffGame.venue`, `GameDetailFeed.venue` and
  `SeriesGame.arena` are nullable.
- A live detail that fails keeps the game's previous detail. A live game with no
  detail held is left out of the feed with a log line, as an All-Star game
  already is.
- A game detail whose standings or injuries read fails is built with that block
  null. A league side the standings lack has a null standing and a null record.
  A series meeting with no arena has a null arena. A guest side keeps all of
  these null.
- A final game whose four attempts (ADR 0010) failed is built once, on the games
  job's last slot or on request, with the summary sections (venue, team stats,
  box score, win probability and season series) null. It is then known.
- The league standings read skips a team whose entry cannot be read, with a log
  line by team code. An unknown team code or conference still fails the read.
- The division standings read keeps wins and losses required and makes every
  other stat optional. A team without wins or losses is skipped with a log line
  by team code; the provider order of the others does not shift. `last_ten`,
  `vs_division` and `vs_conference` keep the default 0-0. Home, road, the
  averages, the totals and the differentials are null in the entry, in the team
  feed's record and in the standings feed's row.
- `TeamColors.secondary` is nullable. A team with no alternate color has a null
  secondary color, and a team with no franchise venue has a null arena. The
  current team feed no longer requires the arena.
- A season before the current one in which a team has no object (a 404) is
  recorded in the state database, table `season_team_absences` (migration 11),
  and not requested again for 30 days. The games job's daily step deletes the
  rows older than 30 days. A read of the current season records no absence and
  honors none (`record_absence=False`): a league team always exists in the
  current season, so a 404 there is read again after the retry window.
- A franchise names build whose current season could not be read keeps the runs
  of the stored list: its open run stands in for the current season and stays
  open. With no stored list, the latest season read stands in, else the team
  code, and the runs are built from the seasons read. The list is stored marked
  `complete = false`. Such a list is fresh for the retry window (10 minutes) and
  not for 7 days.

It supersedes ADR 0038 for league events and live details that cannot be read
only, ADR 0043 for a names build whose current season could not be read only, and
rule D of `docs/source-rules.md` for a final detail with no summary only.

## Consequences

- A feed carries less information when its source is incomplete, and the log says
  which item. The feed is still published.
- A playoffs scoreboard game with no venue no longer fails the playoffs feed:
  `PlayoffGame.venue` is nullable and the web draws the game's date alone.
- A team left out of the division standings fails its own team feed and the
  playoffs feed (`PlayoffsBuildError "team X has no standing"`), as the whole read
  failed before. The standings feed lists the teams it has.
- A game detail built while the standings were down carries no record, and is
  stored. A pre-game detail expires within 12 hours; a live one with the next
  refresh. A final one built without a summary is kept.
- A names build with the current season unread replaces a complete stored list by
  the same runs marked incomplete for the retry window. With no stored list the
  runs hold only the seasons read. A past feed built in that window may carry a
  code-only identity until it is rebuilt.
- Every stored feed from before this change still validates, because each change
  widens a type.
