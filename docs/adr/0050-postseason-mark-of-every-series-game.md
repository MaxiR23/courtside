# 0050. The postseason mark of every series game

- Status: Accepted
- Date: 2026-10-16

## Context

Issue 265. ADR 0035 gives a playoff game a mark only when its note, competition
type and series can be read completely. Past seasons break that: the 2005 notes
are "FINALS" or empty, the competition type may be unknown, and the series
object may be missing. Those games lost their mark, and the page showed them as
regular season games.

## Decision

- A game of season type 3 always carries a mark. What cannot be read is null
  inside the mark, never the whole mark.
- The round and the game number come from the note, in any letter case.
  `NBA Finals - Game N` is round 4. `<East|West> <1st Round|Semifinals|Finals> -
  Game N` is rounds 1 to 3, with the conference from its first word.
- Without a round in the note, the round comes from the competition type, and a
  round 1 to 3 takes its conference from the note's first word. A round 1 to 3
  without a conference is no round.
- No game number gives `number` null and `stakes` null, because a 3-3 series
  would read as `elimination` when the game is the seventh.
- No round gives `stage` `playoffs` with `round` and `conference` null. The web
  draws the "Playoffs" tag with no context line.
- An unreadable series object, or a competitor that is not a league team,
  nulls only `summary` and `stakes`.
- The play-in does not change: a play-in note that cannot be read still gives no
  mark.
- It supersedes, in ADR 0035, "`number` (1 to 7, null for the play-in)", "A mark
  that cannot be read completely is null" and, in "Lenient reading", "a missing
  note or an unknown competition type makes only that game's `postseason` null",
  for season type 3.

## Consequences

- `GamePostseason` keeps its fields. Only the model validator changes, so the
  schema does not change.
- `postseason_mark.py` holds a case-insensitive copy of the note shapes the team
  feed reads. A future note change touches both.
- A current game with an odd note now shows a "Playoffs" tag where it showed
  none.
