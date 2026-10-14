# 0039. All-Star sides by code or name

- Status: Accepted
- Date: 2026-10-14

## Context

Issue 235. ADR 0038 reads an All-Star side as a team only when the source flags
it as an All-Star team. The scoreboard's team object of an All-Star game carries
abbreviation, id, name, location, displayName, shortDisplayName, isActive
(false), logo, links and uid and no such flag; the flag exists only in a teams
endpoint these adapters do not read. Every All-Star side was read as a
placeholder: the core skipped every All-Star game and the All-Star scoreboard
view failed on every final game, which failed the discovery job. The location of
an All-Star team repeats its name, so it is not a city.

## Decision

- **A side is a team when it has a code or a name**: the test of ADR 0026
  (`to_opponent`). No All-Star flag is read anywhere.
- **A side with neither is undecided**: it is null in the All-Star scoreboard
  view (a live or final game with one still fails that read), and its game is
  skipped in the core feeds, as ADR 0026 skips a game with a side that is not a
  team.
- **An All-Star side has a null city** in both adapters, whatever its location.
- **Partial supersede of ADR 0038**: its bullet "A placeholder side skips its
  game: a game with a side that is not an All-Star team is skipped until its
  teams are known, as ADR 0026 skips a game with a side that is not a team" no
  longer holds. The rest of ADR 0038 stays in force.

## Consequences

- All-Star games reach the games feed and the discovery job finds a played
  edition.
- The shape of an undecided All-Star game has not been observed: a source that
  sends a code or a name for it (for example `TBD`) would have it read as a team.
  It is to be verified when the next edition is scheduled.
- The detection function is renamed `is_an_all_star_game`.
- Removing the All-Star section no longer removes the All-Star flag field or a
  placeholder skip; it removes the null city of an All-Star side in
  `scoreboard.py`.
