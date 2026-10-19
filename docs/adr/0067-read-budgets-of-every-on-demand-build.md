# 0067. Read budgets of every on-demand build

- Status: Accepted
- Date: 2026-10-19

## Context

Issue 299, follow-up. The rule of the hardening plan is that every on-demand
build runs under a declared, enforced read budget. After ADR 0066, seven builds
declared none: the current game detail, team, player, Cup matchup, playoffs
finals and All-Star builds, and the calendar build. They were bounded only by the
shared client's cap of 8 requests in flight, the pause after a 429 or 503, the
limit on running builds and the 60-second build timeout (ADR 0062).

ADR 0066 is accepted and is not edited. This decision extends it and replaces
nothing in it.

## Decision

- **Budgets.** Each of the seven builds declares a `READ_BUDGET` equal to its
  worst-case read count and runs under `within_budget`:

  | Build | Budget | Reads |
  |---|---|---|
  | Game detail | 5 | 1 summary, 1 standings, 1 league injuries, 2 team schedules |
  | Team | 15 | 1 roster, 2 season averages, 1 team info, 2 division standings (rule L), 1 league injuries, 2 season schedules, 6 Cup group tables |
  | Player | 11 | 1 athlete, 1 roster, 2 division standings (rule L), 1 league injuries, 1 bio, 1 draft, 1 awards, 1 game log, 2 career statistics |
  | Cup matchup | 9 | 1 league injuries and, per side team, 1 roster, 1 season schedule, 1 season averages, 1 depth chart |
  | Playoffs finals | 48 | 7 games (detail, sections and plays share one URL), 2 records, 2 team statistics, 2 x 18 roster players, 1 Finals MVP |
  | All-Star | 122 | per edition (the current and the previous one) 1 calendar, 6 days, 8 games and 31 awards (the index and 30 documents), then 30 team infos |
  | Calendar | 1 | the season calendar |

- **Counting reads only.** The current builds set `stop_on_rate_limit` false: a
  rate-limited read fails as an ordinary one and nulls only its part, as before,
  and the client-wide pause protects the source. The pause (ADR 0062) fails
  only the reads after the limited one in the same build, so a build orders its
  optional reads last (the game detail reads its summary and team schedules
  before the standings and injuries). The calendar counts reads only
  for the current season and stops on a rate limit for a past one, as the past
  builds do (rule O).
- **A dependency built first keeps its own budget.** The feed cache builds the
  dependency of a kind (the franchise names of a team, the team feed of a
  player, the Cup feed of a matchup, the playoffs feed of the Finals) before it
  calls the kind's build, so its reads are charged to its own budget.
- **Finals roster cap.** The Finals build read one postseason player stats
  request per roster player of both finalists, with no cap. It now reads at most
  `FINALS_ROSTER_READS` (18) players per finalist, in jersey order, and always
  the Finals MVP. A further player is listed with no values, sorted last, and one
  warning is logged per finalist. An NBA roster holds up to 15 standard and 3
  two-way contracts.
- **All-Star bounds.** The All-Star budget assumes up to 8 games per edition and
  up to 30 award documents per season. The code does not enforce either bound.
  They leave headroom over today's editions (4 games) and awards index, so a
  format change does not fail the build. The past All-Star budget (60) keeps its
  own figures.

## Consequences

- Each of these builds has at most four reads in flight (ADR 0058), where before
  only the client's cap of 8 applied. A cold worst-case All-Star build is slower:
  about 122 reads at four in flight, inside the 60-second build timeout.
- An All-Star edition with more than 8 games, or an awards index with more than
  30 documents, fails that build over budget and keeps the stored feed.
- A finalist roster longer than 18 lists its extra players with no values.
- No feed model changes: no schema or TypeScript regeneration.
- ADR 0066 stays in force and is not superseded.
