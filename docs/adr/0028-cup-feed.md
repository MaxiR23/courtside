# 0028. Cup feed

- Status: Accepted
- Date: 2026-10-13

## Context

Issue 203. The `/cup` page (`docs/design-cup.md`) needs the draw, the six group
tables, the wild card standings, the knockout bracket and every Cup game. No
feed has this data, and the design marks the Cup as a seasonal section: it must
be removable without touching the core feeds (principle 5). The groups and the
Cup tables are read from the source by fixed group ids; the team schedules show
each Cup game with a note that names its round. The stars job already holds the
season of the latest roster, which the team and stars builders use as the
current season.

## Decision

- **Route and rules**: `/feeds/cup.json` is built on demand under rule G and
  served under rule H, with the fixed id `league`, stored as `cup/league`. It is
  the third singleton kind, after the standings and search feeds.
- **Reads**: the teams of each of the 6 groups, the table of each group, the
  table of each conference (the seeding order) and the 30 season schedules, all
  through the source cache with 1 hour freshness. A cold build costs 14 group
  reads plus 30 schedule reads. No team information and no roster is read.
- **Season**: the end year of the latest roster the stars job fetched
  (`StarsJob.current_season()`). Until a roster is fetched the feed answers 503
  when nothing is stored.
- **Settings**: `CUP_GROUP_URL` (the teams collection of a group) and
  `CUP_GROUP_STANDINGS_URL` (the Cup table of a group or conference), each a
  template with `{season}` and `{group}`. The group ids are a fixed table in the
  adapter: the East groups A to C are 22 to 24, the West groups are 25 to 27,
  and the conferences are 28 (East) and 29 (West). The ids are stable across
  seasons; the teams in a group change each season.
- **Rounds**: a game belongs to a Cup round by its note: "NBA Cup - Group Play",
  "NBA Cup - Quarterfinals", "NBA Cup - Semifinals" and "NBA Cup Championship"
  map to `group`, `quarterfinals`, `semifinals` and `championship`. The
  semifinals and the championship are on a neutral court and the championship
  does not count in the standings.
- **Stage**: `draw` with no table rows; `group` while the group round is not
  final or no quarterfinal is scheduled; then the earliest knockout round that
  is not final; `complete` once the championship is final. A round is final when
  it has all its games (60, 4, 2 and 1) and every one is final, so a round with
  fewer games than its full count is never final.
- **Bracket**: 7 slots in a fixed order. Seeds 1 to 3 and the wild card are the
  first four rows of each conference table. Labels and rules are keys and parts,
  never prose. An unscheduled quarterfinal side shows the team that leads today
  with its record; a scheduled game replaces it.
- **Expiry**: rule G as for the other league feeds: 1 hour after a final Cup
  game that follows the build and 7 days after the build. Once the championship
  is final the feed is kept while its season equals the current one, and then
  expires under the normal rules, so the next season's Cup shows. Read literally,
  "kept forever" would freeze the feed on the first season.
- **Failures**: a failed group or conference read fails the build and the stored
  feed is kept. A failed schedule read is skipped only when every drawn team
  still has its 4 group games among the schedules that were read and no
  knockout game can exist yet; otherwise the build fails. A knockout game can
  exist once any group row has a `won_group` or `wild_card` tag, or the group
  round is final among the schedules read. The team feed never fails because of the Cup.
- **Marks on the core feeds**: the games feed, the game detail feed and the team
  feed gain a nullable `cup` object. A game carries `{stage}`, a team carries its
  group and Cup record. Stored feeds written before this change read as `cup:
  null`.
- **Team names**: every team is an `Opponent`; its name and city come from the
  30 schedules, where every league team appears as an opponent, and are null for
  a team no schedule shows.

## Consequences

- A cold build costs 14 group reads and 30 schedule reads, shared through the
  source cache for an hour with the team feeds, which read the 6 group tables to
  set their `cup` mark.
- The feed answers 503 until the stars job has fetched a roster when nothing is
  stored.
- Removing the Cup section touches the `cup` fields of the three core feeds,
  which is the cost of marking games and teams. It also touches
  `api/app/sources/scoreboard.py`, which imports `cup_round` for the games and
  game detail mark, and `api/app/jobs/team_feed.py`, which imports `GROUP_IDS`,
  `CupTable` and `fetch_group_table` for the team mark. This qualifies
  principle 5 (small core, removable extras); the Cup feed itself has its own
  module, kind, route, adapter and settings.
- If the quarterfinals appear in the schedules after the rebuild that follows
  the last group game, the feed keeps stage `group` and null quarterfinal dates
  until a Cup game goes final or 7 days pass (the stage rule and the expiry
  rule).
- The payload shape of each configured URL is part of the contract of the
  settings and is documented in `docs/api/cup.md`.
- This rules out reading team information for the Cup and following the links in
  the source's payloads.
