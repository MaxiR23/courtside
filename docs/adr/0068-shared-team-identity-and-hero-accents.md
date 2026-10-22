# 0068. Shared team identity and hero accents

- Status: Accepted
- Date: 2026-10-22

## Context

Issue 308, with decisions 1 and 2 of [`design-team-identity.md`](../design-team-identity.md).
The web shows a team's logo and colors in many places, and the hero draws each
side of a game in an accent color. No feed carried a logo, and the colors came
from separate team info reads of each build, with a different shape in each feed.

ADR 0026 (the one side model) and ADR 0054 (historical sides) are accepted and
are not edited. This decision extends them and supersedes nothing.

## Decision

- **Logo in the adapter.** The team info adapter reads the team's `logos` list,
  each entry an address and its tags. The light logo is the first entry tagged
  `default` whose address is an http(s) URL, the dark logo the first tagged
  `dark` that is one. A team with no usable `default` logo has no logo, even with
  a dark one. A bad logo only drops the logo and never fails the read (ADR 0064).
- **Daily identity read.** The stars job reads each team's info in its daily run,
  inside the adapter's 24-hour freshness and the four reads in flight, and keeps
  one row per team in the `team_identities` table (migration 13), replaced on
  success and loaded into memory at start. A failed read logs one line and keeps
  the stored identity: it never fails a team, so star retries, the daily mark and
  the job's health are unchanged. With no team info URL nothing is read.
- **Shared shapes.** `TeamLogo` (`light`, `dark`) and `TeamColors` (`primary`,
  `secondary`) live in `app/feeds/opponent.py`; `GameAccent` (`away`, `home`) in
  `app/feeds/games.py`.
- **Put on when served.** The identity is put on a feed when it is served, in the
  feed cache after the kind's own additions, and at publish for the games feed,
  which the games job publishes again when the identities change. No builder
  changes, no read budget changes and no `SEASON_BUILD_VERSION` bump, and a kept
  past feed picks up a logo with no rebuild. The stored file never carries it.
- **Which objects.** A league team object is an `Opponent` (with `GameTeam`,
  `DetailTeam` and `PlayoffTeam`), or any feed model that declares a `logo` field,
  found by its fields so that core code imports no section's model. There are
  eight kinds:

  | Object | `logo` | `colors` |
  |---|---|---|
  | `Opponent` and its subclasses | identity | identity |
  | `PlayoffTeam` | identity | kept as built (`StandingsColors`) |
  | `StandingsRow` | identity | kept as built (`StandingsColors`) |
  | `SearchTeam` | identity | kept as built |
  | `LeagueTeam` (All-Star) | identity | kept as built |
  | `TeamFeed` root | identity | kept as built (`TeamColors` or null) |
  | `SearchPlayerTeam` | identity | identity (`primary` stays) |
  | `Team` (the player's team) | identity | identity |

  A model that already has `colors` gains `logo` only, with its colors unchanged.
- **Null cases.** `logo` is null, and so is `colors` where the stamp sets it,
  when the code has no identity, when the object is a guest or when `historical`
  is true. An object with a `season_code` and no `historical` field (the past
  player's `Team`, which cannot tell whether the team was renamed) is treated as
  historical. A non-historical side of a past feed carries today's identity.
- **Hero accent.** `Game.accent` carries `away` and `home`. The backend does not
  know which games are in the hero (ADR 0012 keeps that in the web), so every game
  of the games feed carries it and the day feed's game leaves it null. A side's
  color is its primary, or its secondary when the primary's OKLab lightness is
  below 0.36 and a secondary exists. Home is resolved first; the away color then
  takes its secondary when its OKLab distance to the home color is below 0.12 and
  it has one. A side with no colors has a null accent, and the web draws the
  neutral one.
- **Guard rule.** A model with a `logo` field is a league team object. A future
  model that adds `logo` for another purpose must not use that name.

## Consequences

- 12 schemas change (every feed but the calendar) and the web types are
  regenerated. The web reads none of the new fields yet; only its test literals
  gain them.
- Stored feeds need no rebuild: the new fields default to null.
- Every on-demand response is parsed, walked and written again, as the 15 kinds
  with serve-time additions already are.
- Until a daily run has read a team's info, its identity is unknown and its logo
  and colors are null.
- The logo entries are read as an address and tags (`href`, `rel`). The recorded
  payloads of the repository hold none, so the tag key is the one thing to
  confirm against a real payload: if it differs, no team has a logo and nothing
  fails.
- It extends ADR 0026 and ADR 0054 and supersedes nothing.
