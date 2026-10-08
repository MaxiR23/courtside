# 0019. Game detail route and feed

- Status: Superseded by 0020
- Date: 2026-10-07

## Context
The site shows a game's details by expanding it in the schedule. A page of its
own per game needs a route and a feed to draw it. Game ids are not known at
build time, and the site stays a static build.

## Decision
Route:

- The page lives at `/game/{id}`.
- The site stays a static build. This route is rendered in the browser from a
  fallback page, because game ids are not known at build time.

Detail feed:

- One detail feed per game, for every game in the days shown, served at
  `/feeds/games/{id}.json`.
- Live games refresh with the games job, every 30 seconds.
- Final games are built once at the final time, with the same retries as the
  stats: 2, 4 and 6 hours after it (ADR 0010).
- Scheduled, delayed, postponed and canceled games refresh every hour.
- League-wide data (standings and injuries) is fetched once per run and shared
  by every game.
- Detail feeds of games that leave the days shown are deleted.

## Consequences
- A visitor to `/game/{id}` reads one small feed and never reaches a data
  source.
- Source calls per run do not grow with the number of games for league-wide
  data.
- The static host must serve the fallback page for `/game/{id}`.
- The detail feed's model is defined in the backend and its types are
  generated, as for every feed.
- The page is specified in `docs/design-game-detail.md`.
