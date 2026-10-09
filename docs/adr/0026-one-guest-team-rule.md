# 0026. One guest team rule

- Status: Accepted
- Date: 2026-10-09

## Context

Issue 195. ADR 0025 made a game side outside the 30 a guest team, and its
Consequences name a known gap: the player feed's live block and game log with a
guest opponent were not covered, and a guest code that is not three letters made
that feed's build fail. The same gap was open in the game detail and team
schedule adapters, which read a guest by its abbreviation. A guest the source
sends without an abbreviation had no code to carry, and every feed still named
a game side by its code. ADR 0025 is not edited.

## Decision

- A guest code is optional in every feed contract. `Opponent`
  (`api/app/feeds/opponent.py`) is the one model of a game side or an opponent:
  `code` (null for a guest without one), `name`, `city` and `guest`. A league
  team has a code of three capital letters. A guest has a code or a name.
  `GameTeam` extends it with a required name and city.
- A provider team is resolved in this order: by its abbreviation (a guest code
  equal to a league code is rejected, as in ADR 0025), else by its team id
  through the league id table, else it is a guest without a code. A side with
  neither a code nor a name is not a team: the adapter skips its game, and the
  feed publishes the other games.
- A reference to a side in a feed is a side, not a code: `winner`, the team stat
  leaders and the win probability leader are `away` or `home`. A leader of the
  games feed has `teamCode` null for a guest without a code.
- The game log keeps preseason games: a `preseason` kind with no tag, listed in
  "All" and under a Preseason tab. The last five games leave them out, as they
  leave out the All-Star game. Averages and milestones come from the season
  stats, not from the log, and do not change.
- An adapter validates only the source events it uses. The player game log
  validates the events its matched season types reference, and the team schedule
  validates the completed events. The scoreboard and the season schedule use
  every event.
- Reuse: `api/app/feeds/opponent.py` and `web/src/lib/components/TeamMark.svelte`
  are the one guest rule, and future features (a full calendar, brackets) reuse
  them. `TeamMark` draws a side as a tile, a label or a name and never links a
  guest.
- A guest tile without a code shows the initials of the guest's display name,
  the city and the name joined by a space or the name alone, by the rule of
  player photos: the first and the last word's initial, uppercased.

## Consequences

- Refines ADR 0025 and closes its known gap. ADR 0025 is not edited.
- The feed contract changes in `games`, `game-detail`, `player` and `team`:
  `GameTeam.code`, `Leader.teamCode` and the opponent fields are nullable or
  `Opponent`; `winner` and the stat and win probability leaders are sides; the
  game kind gains `preseason`. The standings and search feeds do not change.
- Stored on-demand feeds in the old shape fail validation on read and are
  rebuilt. The games feed is rewritten by its job.
- The resolution by team id is not proven against a recorded response: the
  recorded fixtures carry only abbreviations.
