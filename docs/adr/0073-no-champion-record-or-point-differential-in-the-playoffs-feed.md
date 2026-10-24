# 0073. No champion record or point differential in the playoffs feed

- Status: Accepted
- Date: 2026-10-24

## Context

Issue 354. The redesigned champion hero (ADR 0068, ADR 0072) draws the champion's
team, Finals result, dates and color. It draws none of `record`, `home`, `road` or
`pointDifferential`, and nothing else in `/web` or `/api` reads them. Producing them
costs:

- one postseason record read in the current build;
- two finalist record reads in the past build;
- the sum over the champion's final games.

Stored current and kept past playoffs feeds carry the four keys, and a feed model
rejects unknown fields. Rebuilding every kept past season would cost about 140 reads
each (see the consequences of ADR 0066).

## Decision

- `Champion` has no `record`, `home`, `road` or `pointDifferential`.
- The current playoffs build reads no postseason record: `OTHER_READS` is 59.
- The past playoffs build reads no finalist record: `READ_BUDGET` is 140 (61 reads,
  27 leader identities, at most 52 award winner identities).
- A stored playoffs feed, current or past, whose champion still has these keys is read
  with them dropped (`RETIRED_CHAMPION_FIELDS` in `api/app/feeds/playoffs.py`), as ADR
  0027 did for `videos`. Any other unknown key still fails.
- It is not rebuilt: `BUILD_VERSION` and `SEASON_BUILD_VERSION` are unchanged. A served
  feed never carries the keys.
- The playoffs Finals feeds keep their finalist record reads and the `team_postseason`
  adapter.

## Consequences

- The playoffs schema and its generated types change.
- A complete current build sends one read fewer, and a past build two fewer.
- Stored files keep the keys on disk until rebuilt for another reason. Removing the
  `RETIRED_CHAMPION_FIELDS` entry is a separate change.
- ADR 0032, 0046, 0058, 0061 and 0066 are superseded for these parts only.
