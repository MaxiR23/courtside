# 0025. Guest teams

- Status: Accepted
- Date: 2026-10-09

## Context

Issue 193: a game against a club outside the 30 (a preseason guest) made the
games job fail with `unknown team code`, so the whole feed stopped
publishing. ADR 0012 sets the hero rotation and filters it in `toHomeView`.
ADR 0014 sets that every published game has both stars. Neither is edited.

## Decision

- A game side is a league team or a guest team. A guest side carries the
  source's own code, name and city, with `guest: true`. A provider code that
  is not one of the 30 provider keys but equals a league standard code is
  rejected, so a guest is never confused with a league team.
- A guest has no colors, star, record, standing, injuries or last games. The
  games and game detail feeds hold those per side as null for a guest side,
  and a validator requires each to be null exactly when the side is a guest.
- A guest game has no season series, and the schedule of a guest side is never
  fetched.
- Stars and players to watch come only from league sides. ADR 0014's "every
  published game has both stars" now reads "every league side has its star".
- The hero never shows a game with a guest side. This adds to ADR 0012's
  filter, which stays in `toHomeView`.
- Guest teams and guest players are never links. A guest player's photo is the
  box score headshot, or initials without one.
- A guest code is the provider's own code: any non-empty string, so an
  unexpected code never fails the whole games day. A league code is still
  three capital letters.

## Consequences

- Refines ADR 0012 and ADR 0014 without superseding them. Neither is edited.
- The feed contract changes: `Team` on game sides becomes `GameTeam` with
  `guest`, per-side sections become nullable, and a leader's or box score
  player's `photoUrl` can be null. The player contract's live line photo
  becomes nullable.
- The player feed's live block and game log with a guest opponent are not
  covered: a guest code that is not three letters makes that feed's build
  fail while the game is live or listed. This is a known gap.
