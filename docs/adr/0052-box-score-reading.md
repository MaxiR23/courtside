# 0052. Box score reading

- Status: Superseded by 0055 for missing count stats only
- Date: 2026-10-16

## Context

Issue 265. ADR 0041 serves the box score and team stats of a past game and says
the blocks the summary lacks are null. It has no rule for a value inside them.
Past summaries come without `fieldGoalPct` (the 2005 game failed with "has no
fieldGoalPct stat"), with every plus-minus at 0, and with team turnovers in
`totalTurnovers`.

## Decision

- Team turnovers are `totalTurnovers` when the provider sends it, else
  `turnovers`. This holds in the games feed `teamStats`, the detail `teamStats`,
  its stat leader and `boxScore.totals`.
- A game whose players all have a plus-minus of 0, on both teams, has
  `plusMinus` null on every row. The game page hides the column. One non-zero
  value keeps every value as sent.
- A team percentage the provider does not send is null in `teamStats` and
  `boxScore.totals`, and the stat leader of its row is null. The page shows "—".
  A missing count stat still fails the build.
- The All-Star feed's `teamStats` block is null when a field goal percentage is
  null.
- It supersedes the turnovers rule of `docs/api/games.md` ("`TeamStats.turnovers`
  counts the players' turnovers") and, in ADR 0041, adds to "Null when the source
  lacks them" the values inside the box score and team stats.

## Consequences

- Four feed fields become nullable: the `TeamStats` percentages,
  `DetailTeamStats.freeThrowPct`, the `BoxScoreTotals` percentages and
  `BoxScorePlayer.plusMinus`. Five schemas change: games, days, game detail,
  All-Star and player. Stored feeds stay valid.
- A live game's box score hides the plus-minus column until the first score,
  because every live player starts at 0.
- The box totals' turnovers can exceed the sum of the players' turnovers.
