# 0070. Team logos in the player career rows

- Status: Accepted
- Date: 2026-10-23

## Context

Issue 322. ADR 0068 gives every league team object a logo when the feed is served, but
the season-by-season rows of a player feed carry only a list of team codes (`teams`,
with `seasonCodes` from ADR 0055), so they drew a code with no logo. ADR 0068 and
ADR 0055 are accepted and are not edited.

## Decision

`SeasonRow` of the player feeds (current and past) gains `logos`, a list parallel to
`teams`, validated to its length. It is put on by `with_identities` when the feed is
served, after the kind's own additions (so after the season codes), at no builder,
read budget or `SEASON_BUILD_VERSION` change.

Entry rule: entry `i` is the identity logo of `teams[i]` only when `seasonCodes[i]`
equals `teams[i]` (the season's code is today's code); it is null for a historical,
unknown or unidentified team. When the season codes are not applied, the list is
all nulls. The field is null when the identities are not applied.

The Career rows have no team and no logo. The stamp finds a `SeasonRow` by its type;
`logos` is not a `logo` field, so the guard rule of ADR 0068 is unchanged.

## Consequences

- The player schema (shared by the past player feed) and the web types change; a
  stored or kept feed needs no rebuild and reads `logos` as null until served.
- The web draws an inline mark (the logo, else the monogram of the code shown) before
  each code of a season row, hidden from assistive technology.

It extends ADR 0068 and supersedes nothing.
