# 0051. All-Star notes and untimed games

- Status: Accepted
- Date: 2026-10-16

## Context

Issue 265. ADR 0038 skips an All-Star game it cannot map and leaves it out of
the core feed. The 2005 All-Star day failed that way: its notes are "ALL STAR
GAME" or "NBA All-Star Game" and its final game has a score but no line score.
The day listed no All-Star game.

## Decision

- A note equal to "ALL STAR GAME" or "NBA All-Star Game", in any case, reads as
  the round "All-Star Game" in `parse_note`, the one reader the mark and the
  All-Star feed share. The game is not the Championship.
- A final All-Star game with a score and no line score is kept with `lineScore`
  null in the scoreboard adapter and in the games, day and game detail models.
  A final All-Star game without a score is still skipped, and so is a live one
  without a clock.
- On the web, a final game without a line score has a card without expanded
  details.
- It supersedes ADR 0038's consequence "On an All-Star day whose live or final
  games come without line scores or clocks, those games are left out of the core
  feed" for final games only.

## Consequences

- The All-Star exception is written once, in `required_fields` of
  `app/feeds/games.py`, and read by the three status validators.
- A current-season untimed All-Star final enters the games feed. It is never a
  hero game (ADR 0025).
- The 2005-style edition gets `roundLabel` "All-Star Game" where it was null.
  Placement and champion logic compare against "Championship" only.
