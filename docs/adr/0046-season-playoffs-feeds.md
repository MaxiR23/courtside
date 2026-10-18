# 0046. Season playoffs feeds

- Status: Superseded by 0048 for the past Finals' highlights only, and by 0053 for the past rosters only, and by 0058 for the past reads, the names of leaders and award winners, the Finals averages and team colors only
- Date: 2026-10-15

## Context

Issue 257. `docs/design-seasons.md` draws the playoffs page of a past season.
ADR 0045 covers only the Cup. The current playoffs and playoffs finals feeds
(`/feeds/playoffs.json`, `/feeds/playoffs/finals.json`) serve the current season
only. The older seasons have no play-in before 2021, and the source's games of
the oldest seasons carry no round and no game number in their notes.

## Decision

- **Two paths.** `/feeds/seasons/{season}/playoffs.json` (kind
  `season-playoffs`, id `{season}`) and
  `/feeds/seasons/{season}/playoffs/finals.json` (kind
  `season-playoffs-finals`, id `{season}`). The schemas are the current
  `PlayoffsFeed` and `PlayoffsFinalsFeed`: no new model.
- **Range.** The end year from 1994 to the current season. The current season
  resolves before the cache to the current kinds (`playoffs`/`league` and
  `playoffs-finals`/`league`), so the current feeds, their expiry and their
  routes do not change. A season outside the range or an ill-formed one answers
  404 with no source request, and 503 while the current season is not known.
- **Past reads.** They send the season value and resolve the sides of games and
  game details by provider id first (ADR 0040, ADR 0043). The names of leaders
  and award winners come from that season's rosters, one read per team.
- **No play-in before 2021.** The play-in window is not requested for an earlier
  season and `playIn` is null (the contract changes: `PlayoffsFeed.play_in` is
  nullable). Seeds 1 to 8 are the standings seeds and every round 1 label is a
  seed.
- **Rounds derived.** A past postseason where no game has a known competition
  type gets its rounds from the series: a series is round k when it is the k-th
  series of both teams, the Finals is the only series across the conferences,
  and the rounds have 8, 4, 2 and 1 series. Anything else fails the build, and
  the season kind logs the reason.
- **Seeds optional.** When a round 1 team has no seed, round 1 is placed by the
  round 2 series it feeds, and the side seeds are null. Each round 1 label keeps the nominal seed of its slot (1/8, 4/5, 3/6,
  2/7), which the label model requires; a page does not draw the label when a team
  is placed.
- **Game numbers.** A past game whose note has no game number takes its position
  in its series in start order. Play-in and game notes are read in any letter
  case.
- **Complete or nothing.** A past playoffs feed must build as `complete`, or the
  build fails and nothing is stored, because the feed is kept for good.
- **Optional reads.** The leaders, the awards, the champion's record, and in the
  Finals the details, sections, plays, team records and statistics and the
  finalists' rosters, are null (or empty) only when the source answers 404. Any
  other failed read fails the build. A team info that fails only nulls the
  colors.
- **Past Finals.** It reads the stored season playoffs feed (built first), the
  finalists' season rosters and the Finals games' reads. There are no highlights
  and `detailAvailable` is false.
- **Kept.** Both are built once on request under rule G, kept, never refreshed
  and never deleted.

## Consequences

- `playIn` becomes `PlayIn[] | null` in the contract. The current feed never
  sends null.
- The series objects of the oldest seasons are assumed to give completion and
  wins, the past scoreboard games a venue, and the first round of 1994 to 2002 a
  best of five. If not, those builds fail with a reason in the log (503), never
  a wrong bracket.
- A feed of a season before 2021 has a `playin` stage entry that is `upcoming`
  with null dates. The page must not draw it.
- About 150 reads per season, once.
- No `/web` page yet: it comes in a later issue.
