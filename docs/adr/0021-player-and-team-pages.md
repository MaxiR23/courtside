# 0021. Player and team pages

- Status: Accepted
- Date: 2026-10-08

## Context
Players and teams have no page of their own. The pages are specified in
`docs/design-profiles.md`. They need routes, feeds and a few decisions about
what the source can and cannot provide, built under the rules of ADR 0020.

## Decision
Routes and feeds:

- The pages live at `/player/{id}` and `/team/{code}`, where `{code}` is the
  lowercase standard team code. Both are rendered in the browser from the
  fallback page, like `/game/{id}`.
- The feeds are `/feeds/players/{id}.json` and `/feeds/teams/{code}.json`.
  They are built on demand under rule G of `docs/source-rules.md`.
- The live block of a player feed comes from the live game detail of the
  player's team (rule C) at serve time.
- The live block is drawn by a live card that replaces the next game card.
  The player page polls every 30 seconds while `live` is not null and every
  60 seconds otherwise.
- A game row or card links to `/game/{id}` only where `detailAvailable` is
  true.

Content:

- FG% is the fourth hero stat, because the source ranks only points, rebounds,
  assists and FG%.
- Totals have no MIN column, because the source has no total minutes.
- Seasons are shown by their label, such as `2025-26`, never as "current".
- The arena photo is shown in color. With no photo there is no frame.
- With no next game, the page reads "Season over."

## Consequences
- A player or team nobody requests is never built or fetched.
- The static host must serve the fallback page for `/player/*` and `/team/*`.
- The feed models are defined in the backend and their types are generated, as
  for every feed.
- The hero stats cannot include other stats the source does not rank.
