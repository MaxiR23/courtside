# 0045. Season competition feeds

- Status: Accepted
- Date: 2026-10-15

## Context

Issue 255. `docs/design-seasons.md` draws the Cup page of a past season. The
past-season feeds of ADR 0043 cover the standings, the team and the player, and
none covers a competition. The current Cup and Cup matchup feeds
(`/feeds/cup.json`, `/feeds/cup/matchups/{id}.json`) serve the current season only.

## Decision

- **Two paths.** `/feeds/seasons/{season}/cup.json` (kind `season-cup`, id
  `{season}`) and `/feeds/seasons/{season}/cup/matchups/{id}.json` (kind
  `season-cup-matchups`, id `{season}-{slot}`). The schemas are the current
  `CupFeed` and `CupMatchupFeed`: no new model, schema or generated type.
- **Range.** The end year from 2024 (the first Cup season) to the current
  season. The current season resolves before the cache to the current kinds
  (`cup`/`league`, `cup-matchups`/`{slot}`), as `current` does for the calendar
  (ADR 0042), so the current feeds, their expiry and their routes do not change.
  A season outside the range, an ill-formed one or a slot outside the 7 answers
  404 with no source request. While the current season is not known the answer
  is 503.
- **Past reads.** They send the season value and resolve the schedule teams by
  provider id first (ADR 0043).
- **Complete or nothing.** A past Cup must build as `complete`, or the build
  fails and nothing is stored, because the feed is kept for good.
- **Past matchup.** It reads only the stored season Cup and the two teams'
  season schedules, and builds the path as the current matchup does.
  `injuries` and `roster` are empty lists, because rosters, depth charts and
  injuries are current-season only.
- **Kept.** Both are built once on request under rule G, kept, never refreshed
  and never deleted.

## Consequences

- The notes and group ids of the 2023-24 season (season 2024) are assumed to be
  the ones the adapter maps. If not, every 2024 build fails with a reason in
  `/health` (503), never a wrong Cup.
- A past matchup cannot tell an empty roster from a hidden one; the page writes
  the "current season only" line (`docs/design-seasons.md`).
- No `/web` change yet: the page comes in a later issue.
