# 0075. Power ranking feed

- Status: Accepted
- Date: 2026-10-26

## Context

The standings page can show a power ranking: a rating per team with its offense and
defense, a projected record and the chances to make the playoffs and win the title. The
provider publishes it paged, recalculates it several times a day and ignores date
parameters, so there are no old snapshots. Observed behavior: during the regular season
the current season returns 30 items, all of the regular season, each with a rating, and
`rank` equal to the rating rank. After a season ends, the list holds three runs of 30
(regular season, play-in and postseason), `rank` turns meaningless (tied values such as
"T61") and the last regular-season run is broken (empty rating, every rating rank "1st").

## Decision

A new on-demand feed kind `power-ranking`, id `league`, served at
`/feeds/power-ranking.json`, under rules G and H of `source-rules.md`. The contract is in
`docs/api/power-ranking.md`.

- **Regular season only.** The feed is `available` only when today (US Eastern) is
  between the regular season start and end, which the season types give. Outside it the
  state is `unavailable` with no teams and the index is not read.
- **One run only.** Only the items of the regular-season run are kept. The provider
  `rank` is never used (it breaks after the season); the order is the rating rank. No
  other run is shown.
- **Guards.** The state is `available` only when the run has 30 teams and every one has a
  non-empty rating. Anything else gives `unavailable`.
- **Ties.** A negative rating rank is a tie: the feed carries the absolute rank and a
  `tied` flag.
- **Ready values.** Records, ratings (signed, minus sign U+2212), projections, chances
  and `titleShare` (the team's title chance over the top team's, 0 to 1, for the bar) are
  computed by the backend. The probability display values are kept as the provider sends
  them (`>99.9%`, `<0.1%`).
- **Teams.** The numeric team id of the provider link maps to a team code through the
  teams module; no team read is made.
- **Freshness.** Rebuilt at the first US Eastern day change after the build.
- **Read budget.** 2 reads (pages of 25), declared in the module and in `source-rules.md`.
  The URL is a Settings template with exactly the placeholders `{season}` and `{page}`,
  built with `.format`.

## Consequences

- The power ranking is never shown after the regular season ends. Showing the postseason
  run is a follow-up, to decide after verifying the data live in April 2027.
- A broken or partial payload hides the section; the standings page never breaks.
- The page shows the ranking on the current season only (past seasons have no snapshot).
