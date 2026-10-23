# 0072. Resolved team colors in the playoffs and Cup feeds

- Status: Accepted
- Date: 2026-10-23

## Context

Issue 334. The redesign of the playoffs and Cup pages draws the team color of the
champions, the Finals MVPs and each side of a bracket slot, and `/web` computes
nothing. ADR 0068 gives the games feed a resolved color per side (`GameAccent`) and
keeps the rule in `api/app/jobs/team_identity.py`. The playoffs, Finals and Cup
feeds carry no resolved color. ADR 0068 and ADR 0070 are accepted and are not
edited.

## Decision

The feeds gain resolved colors, computed by the rule of ADR 0068 (a side shows its
primary color unless it is too dark, then its secondary; the second side of a pair
takes its secondary when too close to the first, measured in OKLab). The rule stays
in `team_identity.py`: `pair_colors` is the pair rule that `game_accent` already used,
and `team_colors`, `code_colors` and `resolved_color` find and resolve the colors.

| Object | Field | Rule |
| --- | --- | --- |
| `Series` (playoffs) | `accent: {top, bottom}` | pair rule, higher seed first |
| `Champion` (playoffs) | `accent` | single color of the champion team |
| `AwardWinner` (playoffs) | `accent` | single color, only on `finals_mvp`, `east_finals_mvp` and `west_finals_mvp` winners |
| `FinalsMvp` (Finals) | `accent` | single color of the plain team code |
| `BracketSlot` (Cup) | `accent: {top, bottom}` | pair rule, smaller seed first |
| `CupFeed` | `championAccent`, `defendingChampionAccent` | single color of the champion |

The colors are the team identity's (`TeamIdentity.colors`), found by code, not the
`colors` a `PlayoffTeam` was built with. A side gets null when it has no team (a
`currently` or `projected` side included), is a guest, has no code, is historical, or
its code has no identity. A plain team code (an award winner, the Finals MVP) takes
today's identity when its season code is null or equals the code (as in ADR 0070), else
null.

Order of a pair: in the playoffs, the smaller seed first, else `top`. In the Cup, the
smaller seed first, else the away side of the slot's game second, else `top` first.

The fields are added when the feed is served, by the `serve_with` of each kind
(current and past playoffs, Finals and Cup), from the team identities. They are never
stored, so a kept feed needs no rebuild and no `SEASON_BUILD_VERSION` change; the
past playoffs and Cup kinds gain a `serve_with`.

## Consequences

- The playoffs, Finals and Cup schemas change and the web types are regenerated. A
  stored feed reads the new fields as null and gets them when served.
- `/web` draws a null color with the neutral accent.
- `team_colors`, `code_colors` and `resolved_color` are public functions in the core
  `team_identity` module, used only by the playoffs, Finals and Cup sections. They are
  listed under principle 5 of `docs/architecture.md`. `pair_colors` is shared with the
  core `game_accent`.
- It amends the table of carriers of ADR 0068 and supersedes nothing.
