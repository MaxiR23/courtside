# 0060. Playoffs series state from its games

- Status: Accepted
- Date: 2026-10-18

## Context

Issue 287. Past playoffs builds fail with "the 2005 postseason is not complete":
the postseason schedule of a team sends no series object, an empty note and a
`seasonType.type` on each event, so the state, the winner and the champion that
ADR 0032 took from the series object never exist. ADR 0032 took the wins,
summary, status and winner of a series, the complete state and the champion's
Finals result from the series object, never counted from the games.

## Decision

- **A series is counted from its games.** Its wins are the final games each team
  won; the source's series object is never required and never overrides.
  - Complete: a team has four wins. Summary `{code} wins series 4-{n}`, with `n`
    the loser's wins.
  - In progress: a game is final and no team has four wins. Summary
    `{code} leads series {a}-{b}` (`a` the leader's wins) or `Series tied {a}-{a}`.
  - Upcoming: otherwise, with null wins on both sides and a null summary.
  - `{code}` is the team code the feed already uses.
- **The winner of a final game** is the side whose source `winner` flag is the
  only true one, else the side with the higher final score. A game that is not
  final never counts. Both the scoreboard and the team schedule adapters read the
  flag.
- **A live-only series is upcoming**, by the literal rule. The playoffs state, the
  stage status and the current round keep using live or final games.
- **The Finals** line summary is the derived summary of the Finals, and the Finals
  winner is the Finals team with four counted wins, none otherwise.
- **Two teams with four counted wins** in one series fail the build.
- **`seasonType.type` of a past schedule event** gives the season type: 3 is
  postseason, 5 is play-in, a missing value is postseason, any other value skips
  the event.
- **The feed cache records a build or dependency error with its own `reason`**
  when it is a non-empty string, else with `unexpected error: <class>`.
  `SourceError` keeps its handling.

## Consequences

- The summary uses the feed's team code (for example `SAS wins series 4-3` where
  the source sent `SA ...`).
- `api/app/jobs/season_playoffs_feed.py`'s `series_winner` and the games feed's
  postseason mark still read the series object. A past champion's record, home
  and road stay null.
- No feed model or generated type changes.
- `SEASON_BUILD_VERSION` stays 3: a past playoffs feed is stored only when
  complete, and its wins, statuses, winners and champion are the same when
  derived. Only the summary text of a feed stored before can differ.
