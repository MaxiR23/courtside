# Architecture

How Courtside is built and why. This document records decisions that are in force. Anything not decided yet is listed under [Open decisions](#open-decisions) and must not be assumed by any change.

## Principles

1. **The source is asked at most once per URL per freshness window, whatever the number of visitors; live data is refreshed on a schedule that slows down when nobody is present; everything else is built only when requested.**
2. **The front end only draws.** It reads published feeds and renders them. It holds no business rules about games, standings or players.
3. **One contract, defined once.** The shape of every feed is defined in backend code and generated for the front end. Nothing is redefined by hand on either side.
4. **Every input is validated.** Data coming from a source is validated before it is used. A feed is validated before it is published.
5. **Small core, removable extras.** The core is the scoreboard. Seasonal sections are self-contained and can be added or removed without touching the core, except for a nullable mark on core feeds (ADR 0028), the front end touches of ADR 0030 and the drawing of those marks (ADR 0031), the shared bracket camera of the Cup (ADR 0034; the playoffs bracket does not use it, ADR 0071), the playoffs marks and team titles (ADR 0035), the All-Star tables in the state database (ADR 0036), the shared count-up (ADR 0037) and the All-Star marks (ADR 0038, ADR 0039) and the seasonal-only additions to core adapters of ADR 0058 (`SeasonSchedule.teams`, `season_schedule_url`, `DivisionEntry.abbreviation`, `cached_team_info`, `SeasonTeamName`, `ReadBudget`, `cached_json`), those of ADR 0061 (`wide_reads`, the `player_identities` state table and the version argument of `with_build_version` and `is_current_build`) the past player ids readers of ADR 0059 (the core index is given the playoffs section's readers through `main.py`) and the Cup mark provider of ADR 0066 (the team feed is given the Cup section's `CupTeamMarks` through `main.py`; `ReadBudget.extend` is retired) and the seasonal-only color helpers of ADR 0072 (`team_colors`, `code_colors` and `resolved_color` in `team_identity.py`; `pair_colors` is shared with the core `game_accent`).

## Stack

| Part | Technology |
|---|---|
| Front end | SvelteKit with Svelte 5, built as static files |
| Back end | Python 3.14 with FastAPI, with scheduled jobs running in the same process |
| Data contract | Pydantic models, exported as JSON Schema, with TypeScript types generated from it |
| Testing | Vitest with Testing Library for `/web`, pytest for `/api`. Conventions in [`testing.md`](testing.md) |
| Package managers | pnpm for `/web`, pip in a virtual environment for `/api`. Every dependency pinned to an exact version |
| API tooling | ruff for lint and format, mypy in strict mode, pydantic-settings for configuration |
| Web tooling | TypeScript in strict mode, svelte-check, ESLint and Prettier with their Svelte plugins, Vitest with Testing Library in jsdom, adapter-static, Node 24 |

Exact versions of every dependency are pinned when the project is scaffolded.
Runtime versions are recorded in [`adr/0017-runtime-versions.md`](adr/0017-runtime-versions.md).

## Data flow

```
data sources  ->  source adapters  ->  jobs  ->  feeds (JSON)  ->  front end
```

Feeds are produced either by scheduled jobs (live data and fixed-time work, rules C to F) or by builds triggered by a feed request (rules G and H), as set in [`source-rules.md`](source-rules.md).

### Source adapters

- One adapter per data source. Each adapter is the only code that knows that source's URLs, formats and quirks.
- Every adapter returns validated Pydantic models. Raw source data never leaves the adapter.
- When a primary source fails or returns invalid data, the job falls back to a secondary source if one exists for that data.

### Jobs

- Jobs run on a schedule inside the backend process. Each job owns one kind of data. Refresh cadences, the shared source cache, presence and on-demand builds follow the rules in [`source-rules.md`](source-rules.md), adopted by [`adr/0020-source-rules.md`](adr/0020-source-rules.md), which supersede the cadences of [`adr/0007-backend-runtime-and-data-pipeline.md`](adr/0007-backend-runtime-and-data-pipeline.md) and [`adr/0014-star-guarantees.md`](adr/0014-star-guarantees.md). The feed's today changes at US Eastern midnight once no game of the previous day is live, as set in [`adr/0013-day-change.md`](adr/0013-day-change.md). The attempts for a final game's detail and highlights follow [`adr/0010-final-game-attempts.md`](adr/0010-final-game-attempts.md). A failed request does not use up a highlight attempt; the same attempt is retried no sooner than 10 minutes later, as set in [`adr/0018-highlight-request-failures.md`](adr/0018-highlight-request-failures.md). The highlights lookup reads the channel's uploads through the official video API, as set in [`adr/0015-highlights-source.md`](adr/0015-highlights-source.md). The stars job runs in its own task, as set in [`adr/0014-star-guarantees.md`](adr/0014-star-guarantees.md). A guest side has no star and a guest game is never in the hero, as set in [`adr/0025-guest-teams.md`](adr/0025-guest-teams.md). Standings have no job: the standings feed is built on demand under rule G, as set in [`adr/0023-standings-feed.md`](adr/0023-standings-feed.md). The search feed is built on demand under rule G from the rosters the stars job keeps, as set in [`adr/0024-search-feed.md`](adr/0024-search-feed.md). The Cup feed is built on demand under rule G, with the season of the stars job's latest roster, as set in [`adr/0028-cup-feed.md`](adr/0028-cup-feed.md). The Cup matchup feeds, one per bracket slot, are built on demand under rule G after the Cup feed they read, as set in [`adr/0029-cup-matchup-feed.md`](adr/0029-cup-matchup-feed.md). The playoffs feed is built on demand under rule G, with the season of the stars job's latest roster, as set in [`adr/0032-playoffs-feed.md`](adr/0032-playoffs-feed.md). The playoffs finals feed is built on demand under rule G after the playoffs feed it reads, as set in [`adr/0033-playoffs-finals-feed.md`](adr/0033-playoffs-finals-feed.md). The team feed carries the titles of the current season, read from the stored playoffs and Cup feeds, and also expires when either was rebuilt after it, as set in [`adr/0035-playoffs-marks-in-core-feeds.md`](adr/0035-playoffs-marks-in-core-feeds.md). The All-Star feed is built on demand under rule G and finds its edition from the season calendar, as set in [`adr/0036-all-star-feed.md`](adr/0036-all-star-feed.md) and [`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md). The calendar feed and the day feed are built on demand under rule G, outside the games job, as set in [`adr/0040-calendar-and-day-feeds.md`](adr/0040-calendar-and-day-feeds.md). The detail of a final game of a stored day feed is built once on request under rule G, kept, and outside the games job, the live refresh, the highlights job and the cleanup, as set in [`adr/0041-past-game-detail.md`](adr/0041-past-game-detail.md); the daily step deletes it when not served in 90 days, as set in [`adr/0063-bounded-state-and-kept-feeds.md`](adr/0063-bounded-state-and-kept-feeds.md). The calendar feed lists the seasons and answers `current`, and the day feed carries its season, as set in [`adr/0042-calendar-seasons-and-day-season.md`](adr/0042-calendar-seasons-and-day-season.md). The standings, team and player feeds of a past season are built once on request under rule G and kept, and the franchise names are built once per team and kept while `SEASON_BUILD_VERSION` holds, their current season read again after 24 hours ([`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md)), as set in [`adr/0043-season-feeds-and-franchise-names.md`](adr/0043-season-feeds-and-franchise-names.md) and [`adr/0055-past-season-reading-rules-and-versioned-stored-data.md`](adr/0055-past-season-reading-rules-and-versioned-stored-data.md). The Cup and Cup matchup feeds of a past season (2024 to the season before the current one) are built once on request under rule G and kept, and the season path of the current season serves the current Cup feeds, as set in [`adr/0045-season-competition-feeds.md`](adr/0045-season-competition-feeds.md). The playoffs and playoffs finals feeds of a past season (1994 to the season before the current one) are built once on request under rule G and kept, and the season path of the current season serves the current playoffs feeds, as set in [`adr/0046-season-playoffs-feeds.md`](adr/0046-season-playoffs-feeds.md). The All-Star feed of a past season (1994 to the season before the current one) is built once on request under rule G and kept, its edition found through the February days of that season's calendar, and the season path of the current season serves the current All-Star feed, as set in [`adr/0047-season-all-star-feed.md`](adr/0047-season-all-star-feed.md). Past highlights and the All-Star edition video are found by one on-demand search started when a feed is served without one, at most `HIGHLIGHTS_SEARCH_DAILY_CAP` searches a day, and added to the feeds when served, as set in [`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md). The eight kept season kinds, the past day feed and the past game detail carry a `buildVersion` and are rebuilt on their next request when it is not the current one, as set in [`adr/0053-season-level-rules-for-past-seasons.md`](adr/0053-season-level-rules-for-past-seasons.md). The league sides of every past feed carry `seasonCode` and `historical`, and the past team sides are named by the season team object, as set in [`adr/0054-historical-sides-and-past-pages.md`](adr/0054-historical-sides-and-past-pages.md). A missing team or player stat is null, a box score row with no player id is skipped, a historical identity keeps the source's own abbreviation as its season code, the past feeds carry the season code on every plain-code field, and the franchise names, the past calendars and the stored past game players carry the build version too, as set in [`adr/0055-past-season-reading-rules-and-versioned-stored-data.md`](adr/0055-past-season-reading-rules-and-versioned-stored-data.md). One reader and one function give a finished All-Star edition's MVP to the season feed and to the current feed's previous edition, as set in [`adr/0056-paced-past-builds-and-one-edition-mvp-path.md`](adr/0056-paced-past-builds-and-one-edition-mvp-path.md). The past game detail carries the leader of each side, chosen by the rule of ADR 0009, and a stored one from before the field is rebuilt on its next request, as set in [`adr/0057-past-game-detail-leaders.md`](adr/0057-past-game-detail-leaders.md). The past playoffs, Finals, Cup, Cup matchup and All-Star builds declare a read budget, read at most four requests at once with no pause, name their league sides from their own payloads, and the past All-Star takes its previous edition from the stored feed, as set in [`adr/0058-bounded-past-competition-reads.md`](adr/0058-bounded-past-competition-reads.md). The past team, player, day, game detail and standings builds declare a read budget, read at most four requests at once with no pause and name their sides from their own payloads; the past team carries no roster or leaders, and the past player no number, draft or awards, as set in [`adr/0059-bounded-past-page-reads.md`](adr/0059-bounded-past-page-reads.md). The playoffs feed counts each series from its final games, a past schedule game takes its season type from the event, and the feed cache records a build error's own reason, as set in [`adr/0060-playoffs-series-state-from-its-games.md`](adr/0060-playoffs-series-state-from-its-games.md). The past playoffs names its leaders and award winners from the shared player identities, as set in [`adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md`](adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md). The shared client keeps at most eight requests in flight and pauses every request after a 429 or 503 until its `Retry-After` (60 seconds by default, at most 15 minutes), and the feed cache starts at most 16 builds and stops a build after 60 seconds, as set in [`adr/0062-bounded-upstream-reads-and-on-demand-builds.md`](adr/0062-bounded-upstream-reads-and-on-demand-builds.md). With the games job's daily fetch, the source cache, the games rows, the past games and player identities rows and the kept past feeds not served in 90 days are deleted, the state database runs in WAL mode and `/health` lists at most 50 failed builds, as set in [`adr/0063-bounded-state-and-kept-feeds.md`](adr/0063-bounded-state-and-kept-feeds.md). A scoreboard event or a division standings team that cannot be read is skipped, a live detail that fails keeps the game's previous one, a final game whose four attempts failed is built once with its summary sections null, a season before the current one in which a team has no object is not requested again for 30 days (the current season is never recorded; the daily step deletes the record after 30 days), and a names build whose current season could not be read keeps the stored list's runs, is stored incomplete and fresh for 10 minutes, as set in [`adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md`](adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md). A game still scheduled past its start is checked every 2 minutes with nobody present; the highlights job keeps each game's final time, first-seen flag and attempts in memory; the stars job's daily mark is its own last success, so a restart on a day already fetched does not run again and takes the rosters from the source cache, with at most 4 source reads in flight and one failed team retried per run; a final game's detail is built on its first request; the player feed starts no franchise names build, as set in [`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md). The current playoffs reads a scoreboard day before today fresh for 7 days (from the latest postseason final of that day when later), the Cup reads a team schedule fresh for 24 hours (1 hour for a team with a game today), team info is fresh for 24 hours, the current playoffs, Cup, standings and search builds declare a read budget (all four counting reads only), the season playoffs reads three leaders per category and at most 52 award winners under one budget of 140 since [`adr/0073-no-champion-record-or-point-differential-in-the-playoffs-feed.md`](adr/0073-no-champion-record-or-point-differential-in-the-playoffs-feed.md), the team feed reads the Cup group tables only inside the Cup window, an unknown season player id is remembered, and the day feed check and the past game detail index read no file per request, as set in [`adr/0066-cut-read-amplification-of-on-demand-builds.md`](adr/0066-cut-read-amplification-of-on-demand-builds.md). The current game detail, team, player, Cup matchup, playoffs finals and All-Star builds and the calendar build declare a read budget (the current ones counting reads only), and the current Finals reads at most 18 roster players per finalist, as set in [`adr/0067-read-budgets-of-every-on-demand-build.md`](adr/0067-read-budgets-of-every-on-demand-build.md). The stars job also reads each team's info once in its daily run and keeps the 30 team identities in the state store; every league team object of every feed carries its identity's logo (and colors where it had none), added when the feed is served (at publish for the games feed), and every game of the games feed carries the hero accents, as set in [`adr/0068-shared-team-identity-and-hero-accents.md`](adr/0068-shared-team-identity-and-hero-accents.md). A standings or team feed built with the rule L fallback also expires at the first `DAILY_FETCH_TIME` (US Eastern) after its build, the fallback recorded with the build in the state store, as set in [`adr/0069-daily-expiry-of-fallback-standings-and-team-feeds.md`](adr/0069-daily-expiry-of-fallback-standings-and-team-feeds.md). Each season row of the player feeds also carries one logo per team, today's identity only when the season's code is today's code, added when the feed is served, as set in [`adr/0070-team-logos-in-the-player-career-rows.md`](adr/0070-team-logos-in-the-player-career-rows.md). The playoffs, Finals and Cup feeds also carry the resolved team color of their champions, Finals MVPs and bracket sides, by the rule of ADR 0068, added when the feed is served, as set in [`adr/0072-resolved-team-colors-in-the-playoffs-and-cup-feeds.md`](adr/0072-resolved-team-colors-in-the-playoffs-and-cup-feeds.md). The playoffs feed's champion carries no postseason record or point differential, no playoffs build reads a postseason record for it, and a stored playoffs feed that still carries them is read with them dropped, as set in [`adr/0073-no-champion-record-or-point-differential-in-the-playoffs-feed.md`](adr/0073-no-champion-record-or-point-differential-in-the-playoffs-feed.md).
- A job that fails keeps the last valid feed published. A partial or invalid feed is never written. One game or team that cannot be read is skipped or has that block null, with a log line naming it, and never fails the feed, as set in [`adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md`](adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md).
- Each job records its last successful run, so the backend can report its own health.

### Feeds

- One feed per domain, each a JSON file:
  - `games.json`: games for the days shown on the site, with scores, status and game details.
  - `standings.json`: the standings by conference and by division, built on demand and drawn by `/standings`, as set in [`adr/0023-standings-feed.md`](adr/0023-standings-feed.md).
  - `search.json`: the index of the 30 teams and every roster player, built on demand and loaded by the search overlay, as set in [`adr/0024-search-feed.md`](adr/0024-search-feed.md).
  - `cup.json`: the NBA Cup (draw, group tables, wild card, bracket and games), built on demand and drawn by `/cup`, as set in [`adr/0028-cup-feed.md`](adr/0028-cup-feed.md).
  - `cup/matchups/{id}.json`: one feed per bracket slot of the Cup (7), built on demand, the data of the matchup panel and the player card, as set in [`adr/0029-cup-matchup-feed.md`](adr/0029-cup-matchup-feed.md).
  - `playoffs.json`: the postseason (picture, play-in, bracket, champion, leaders and awards), built on demand and drawn by `/playoffs`, as set in [`adr/0032-playoffs-feed.md`](adr/0032-playoffs-feed.md).
  - `playoffs/finals.json`: the Finals games, the Finals MVP, the road to the title, the head to head and the finalists' postseason averages, built on demand, as set in [`adr/0033-playoffs-finals-feed.md`](adr/0033-playoffs-finals-feed.md).
  - `all-star.json`: the current All-Star edition, its MVP, the previous edition's recap and the previous edition as its after view, built on demand and drawn by `/all-star` and `/all-star/previous`, as set in [`adr/0036-all-star-feed.md`](adr/0036-all-star-feed.md).
  - `seasons/{season}/calendar.json`: the days with games of a season and the list of seasons (`current` answers the current season), built on demand, as set in [`adr/0040-calendar-and-day-feeds.md`](adr/0040-calendar-and-day-feeds.md) and [`adr/0042-calendar-seasons-and-day-season.md`](adr/0042-calendar-seasons-and-day-season.md).
  - `days/{date}.json`: the games of a past day and its season, built on demand, as set in [`adr/0040-calendar-and-day-feeds.md`](adr/0040-calendar-and-day-feeds.md) and [`adr/0042-calendar-seasons-and-day-season.md`](adr/0042-calendar-seasons-and-day-season.md).
  - `seasons/{season}/standings.json`, `seasons/{season}/teams/{code}.json` and `seasons/{season}/players/{id}.json`: the standings, one team and one player of a past season (1994 to the season before the current one), built once on request, as set in [`adr/0043-season-feeds-and-franchise-names.md`](adr/0043-season-feeds-and-franchise-names.md).
  - `seasons/{season}/cup.json` and `seasons/{season}/cup/matchups/{id}.json`: the Cup and one Cup matchup of a season from 2024 (the current season serves the current Cup feeds), a past season built once on request, as set in [`adr/0045-season-competition-feeds.md`](adr/0045-season-competition-feeds.md).
  - `seasons/{season}/playoffs.json` and `seasons/{season}/playoffs/finals.json`: the playoffs and the playoffs finals feed of a season from 1994 (the current season serves the current playoffs feeds), a past season built once on request, as set in [`adr/0046-season-playoffs-feeds.md`](adr/0046-season-playoffs-feeds.md).
  - `seasons/{season}/all-star.json`: the All-Star edition of a season from 1994 in its after state (the current season serves the current All-Star feed), a past season built once on request, as set in [`adr/0047-season-all-star-feed.md`](adr/0047-season-all-star-feed.md).
  - `games/{id}.json`: one detail feed per game in the days shown, built on request (a final game's once, at its final time), drawn by the front end's `/game/{id}` route. Its route is set in [`adr/0020-source-rules.md`](adr/0020-source-rules.md), first set by ADR 0019; its refresh, retries and deletion follow [`adr/0020-source-rules.md`](adr/0020-source-rules.md). The same route also serves one per final game of a stored day feed, built once on request and kept, as set in [`adr/0041-past-game-detail.md`](adr/0041-past-game-detail.md).
  - `players/{id}.json` and `teams/{code}.json`: one feed per player and per team, built on demand and drawn by `/player/{id}` and `/team/{code}`, as set in [`adr/0021-player-and-team-pages.md`](adr/0021-player-and-team-pages.md).
  - Seasonal feeds, such as playoffs or All-Star, added only while their section exists.
- Each feed is validated against its model before publishing and written atomically, so a reader never sees a half-written file.
- Feeds are served by the backend with cache headers. A CDN in front of the API caches feed responses only as the origin's Cache-Control allows, per rule K of [`source-rules.md`](source-rules.md) ([`adr/0020-source-rules.md`](adr/0020-source-rules.md)); see [`deploy.md`](deploy.md).

### State database

The job state's schema version is SQLite's `PRAGMA user_version`. `MIGRATIONS`
in `api/app/storage/state.py` is the ordered list of migrations, and migration
N sets the version to N. Migration 1 is the schema as it stood before
versioning, so an unversioned database is brought up to it with its rows kept.

On startup, every migration above the stored version runs in order, all in one
transaction. A failure rolls the whole transaction back, leaving the database
as it was, and stops startup with `StateMigrationError` naming the migration.
`migrate()` sets WAL mode, and every connection waits up to 5 seconds on a lock
(ADR 0063).

To add a migration, append a tuple of SQL statements to `MIGRATIONS`. Never
edit, reorder or remove one that has shipped. Statements must not commit (no
`COMMIT`, no `executescript`). Add a test in `api/tests/storage/test_state.py`
that migrates a database at the previous version with rows in it.

## Data contract

- The Pydantic models in the backend are the single source of truth for every feed.
- A JSON Schema is exported from those models, and the front end's TypeScript types are generated from that schema.
- Generated types are never edited by hand. A contract change starts in the models and is regenerated.
- The exported schema of each feed is committed at `api/schemas/<feed>.schema.json`.
- The generated types are committed at `web/src/lib/contract/<feed>.ts`.
- `scripts/contract.sh` regenerates both.
- A new feed is registered in `FEEDS` in `api/app/feeds/schema.py` and in the `feeds` array of `web/scripts/contract-types.js` before `scripts/contract.sh` generates its schema and types.
- The api gate fails when the committed schema differs from the models; the web gate fails when the committed types differ from what the committed schema generates.
- Recorded in [`adr/0008-contract-generation.md`](adr/0008-contract-generation.md).

## Front end

- A static SvelteKit build. No server-side rendering is required to view the site.
- The game detail page lives at `/game/{id}` and is rendered in the browser from a fallback page, because game ids are not known at build time. Recorded in [`adr/0020-source-rules.md`](adr/0020-source-rules.md), first set by ADR 0019.
- `/day/{date}` is rendered in the browser from the fallback page; the day page and the calendar sheet load their feeds once and are not polled (ADR 0042).
- `/standings`, `/team/{code}` and `/player/{id}` read `?season=YYYY`; a past season reads its season feed once and is not polled; the selector's seasons come from the current calendar feed, as set in [`adr/0044-season-selector-sources.md`](adr/0044-season-selector-sources.md).
- `/cup`, `/playoffs` and `/all-star` read `?season=YYYY` the same way; the Cup lists the seasons from 2024 and the season on show (ADR 0054); a past season reads its season feeds once and is not polled, as set in [`adr/0049-competition-season-selectors.md`](adr/0049-competition-season-selectors.md).
- Svelte 5 runes only. Syntax from earlier Svelte versions is not used.
- Every game side or opponent that can be a guest is drawn by `TeamMark`, as a tile, a label or a name, and a guest is never a link. Recorded in [`adr/0026-one-guest-team-rule.md`](adr/0026-one-guest-team-rule.md).
- The front end fetches feeds and polls them while the page is open. Polling pauses while the tab is hidden. A page loads once or stops polling in these cases: a game detail whose game is final (past seasons included), the previous All-Star edition, the day page (ADR 0042) and every past season page. A feed request with no answer within 15 seconds counts as a failed request (`docs/design.md`). Each page's cadence is in its design document.
- Motion uses Svelte's built-in transitions, the Web Animations API and, for simple looping opacity effects such as the live win probability marker pulse, scoped CSS animations whose values come from tokens. No animation library.
- Every user-facing string lives in the translation messages (`web/messages/en.json`, `web/messages/es.json`), compiled by Paraglide JS. English is the base; Spanish is shown when the browser prefers it. The language never appears in the URL. Dates and numbers are formatted with the browser's `Intl` for the active language.
- On-demand feeds such as the search feed are revalidated through the browser HTTP cache with `fetch(..., { cache: 'no-cache' })`, and the browser sends `If-None-Match` itself. The front end never sets `If-None-Match` or any other non-safelisted header by hand, because the API's CORS setup allows only `GET`, allows no extra request headers and exposes no `ETag`, so a hand-set header would fail its preflight.
- State shared across routes lives in a module-level runes class in a `.svelte.ts` file (the first one is `web/src/lib/search/overlay.svelte.ts`). The search overlay and its index store are mounted once in the root layout, so they outlive client navigations, and the overlay closes on every navigation.
- Recorded in [`adr/0004-web-tooling.md`](adr/0004-web-tooling.md) and [`adr/0006-translations.md`](adr/0006-translations.md).

## Performance

The site has to load and respond fast on a phone. These rules apply to every change:

- The front end's static files are served from a CDN.
- Feeds stay small and contain only what the page draws.
- Images are served at the size they are displayed and load only when they are about to be shown.
- Fonts load only the weights in use.
- No dependency is added to the front end without a reason recorded in its pull request.

## Seasonal sections

Sections such as All-Star or the Finals are temporary. Each one is self-contained: its own route or component, its own feed and its own job. Removing a section removes those pieces and touches nothing in the core, with one qualification: a seasonal section may mark core feeds with a nullable field, as recorded in ADR 0028. Removing it then also touches those fields and the adapters that set them. A second qualification: a seasonal section may add its nav link inside `NavRow`, which resolves the route itself, size variants to a shared component and entries in the shared feed modules, as recorded in ADR 0030. Removing it then also touches only those pieces, and no other core component or route, except as below. A third qualification: the marks on core feeds are drawn by the section's own components, rendered by the core card or header behind one condition, from one nullable view field the core props layer fills through the section's mapping module, as recorded in [`adr/0031-cup-marks-in-core-components.md`](adr/0031-cup-marks-in-core-components.md). Removing it then also touches those fields and lines. A fourth qualification: the Cup keeps the bracket camera view math, geometry and layer in `web/src/lib/bracket/` (desktop only), as recorded in [`adr/0034-shared-bracket-camera.md`](adr/0034-shared-bracket-camera.md); the playoffs bracket is a plain grid at 1:1 that imports none of it, as recorded in [`adr/0071-playoffs-bracket-without-a-camera.md`](adr/0071-playoffs-bracket-without-a-camera.md), and neither section imports the other. Removing the Cup removes the module. A fifth qualification: the playoffs marks follow the shape of ADR 0031. The team feed receives its titles from one injected provider per section, wired in `main.py`, and imports neither section. The scoreboard adapter parses the season type, competition type and series object leniently and imports the mark function from `api/app/sources/postseason_mark.py`, as recorded in [`adr/0035-playoffs-marks-in-core-feeds.md`](adr/0035-playoffs-marks-in-core-feeds.md). A sixth qualification: the All-Star section keeps the editions its feed and its season feed find in one table of the state database, `all_star_editions`, and the time each of its games was first seen final in another, `all_star_finals`, and the video of each edition in a third, `all_star_edition_highlights`, with seven store methods in all, as recorded in [`adr/0036-all-star-feed.md`](adr/0036-all-star-feed.md), [`adr/0047-season-all-star-feed.md`](adr/0047-season-all-star-feed.md) and [`adr/0048-highlights-backfill-and-edition-video.md`](adr/0048-highlights-backfill-and-edition-video.md). Removing the section removes the methods and leaves the tables, because shipped migrations are never removed. A seventh qualification: the playoffs and All-Star heroes share the count-up controller and its text function in `web/src/lib/count/`, and neither section imports the other, as recorded in [`adr/0037-shared-count-up.md`](adr/0037-shared-count-up.md). The All-Star frames also use a corner mark size variant of `BlueprintFrame`, as allowed by ADR 0030. Removing one section leaves the module to the other, and removing both removes it. An eighth qualification: the All-Star marks follow the shape of ADR 0031 and ADR 0035. The scoreboard adapter reads an All-Star game's sides as guests with a null city, by code or name with no All-Star flag, skips a game with a side that has neither, as recorded in [`adr/0039-all-star-sides-by-code-or-name.md`](adr/0039-all-star-sides-by-code-or-name.md), skips with a log line an All-Star event it cannot map, and the games job skips with a log line an All-Star game that fails validation or its live detail fetch, and imports the mark function from `api/app/sources/all_star_mark.py`, which also holds the note parsing the All-Star feed reads; the player feed carries the year of the All-Star game in its game log, as recorded in [`adr/0038-all-star-marks-in-core-feeds.md`](adr/0038-all-star-marks-in-core-feeds.md). A final All-Star game with a score and no line score is kept with a null line score, as recorded in [`adr/0051-all-star-notes-and-untimed-games.md`](adr/0051-all-star-notes-and-untimed-games.md). Removing the section then also touches those fields and lines. A ninth qualification: the All-Star section starts the core on-demand highlights search for its edition video through a collaborator wired in `main.py`, and the core search imports no section, as recorded in [`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md). Removing the section then also removes that collaborator and its line in `main.py`. A tenth qualification: the playoffs section gives the core past player ids index the readers of its stored past playoffs and Finals feeds through `main.py`, the index imports no section, and removing the section removes the readers and their line in `main.py`, as recorded in [`adr/0059-bounded-past-page-reads.md`](adr/0059-bounded-past-page-reads.md). An eleventh qualification: the Cup section gives the team feed its Cup mark through an injected provider (`CupTeamMarks`) wired in `main.py`, as it gives the titles, and the team feed imports no section; removing the section removes the provider and its line in `main.py`, and the team feed's `cup` is then null, as recorded in [`adr/0066-cut-read-amplification-of-on-demand-builds.md`](adr/0066-cut-read-amplification-of-on-demand-builds.md).

## Configuration

- Configuration is read only through `Settings` in `api/app/settings.py`, from the environment and from `api/.env`.
- `.env` is never committed. `api/.env.example` lists every variable `Settings` reads.
- Data source URLs and keys live only in configuration, never in code or documentation.
- Recorded in [`adr/0003-api-tooling-and-configuration.md`](adr/0003-api-tooling-and-configuration.md).
- The front end's build-time settings are declared in `web/src/env.ts` and listed in `web/.env.example`: the games feed URL, the standings feed URL, `STANDINGS_FEED_URL`, the search feed URL, `SEARCH_FEED_URL`, the Cup feed URL, `CUP_FEED_URL`, the Cup matchup feed URL, `CUP_MATCHUP_FEED_URL` (with an `{id}` placeholder), the playoffs feed URL, `PLAYOFFS_FEED_URL`, the playoffs finals feed URL, `PLAYOFFS_FINALS_FEED_URL`, the All-Star feed URL, `ALL_STAR_FEED_URL`, the game detail feed URL (with an `{id}` placeholder), the team feed URL, `TEAM_FEED_URL` (with a `{code}` placeholder), the player feed URL, `PLAYER_FEED_URL` (with an `{id}` placeholder), the calendar feed URL, `CALENDAR_FEED_URL` (with a `{season}` placeholder), the day feed URL, `DAY_FEED_URL` (with a `{date}` placeholder), the season standings feed URL, `SEASON_STANDINGS_FEED_URL` (with a `{season}` placeholder), the season team feed URL, `SEASON_TEAM_FEED_URL` (with `{season}` and `{code}` placeholders), the season player feed URL, `SEASON_PLAYER_FEED_URL` (with `{season}` and `{id}` placeholders), the season Cup feed URL, `SEASON_CUP_FEED_URL` (with a `{season}` placeholder), the season Cup matchup feed URL, `SEASON_CUP_MATCHUP_FEED_URL` (with `{season}` and `{slot}` placeholders), the season playoffs feed URL, `SEASON_PLAYOFFS_FEED_URL` (with a `{season}` placeholder), the season playoffs finals feed URL, `SEASON_PLAYOFFS_FINALS_FEED_URL` (with a `{season}` placeholder), the season All-Star feed URL, `SEASON_ALL_STAR_FEED_URL` (with a `{season}` placeholder), and the video platform's name.
- `HIGHLIGHTS_SEARCH_API_URL` (the search source's URL, never written in the docs) and `HIGHLIGHTS_SEARCH_DAILY_CAP` (searches per US Eastern day, default 80) are the two settings of the on-demand highlights search; `HIGHLIGHTS_BACKFILL_PAGES` is retired: a `.env` that still sets it starts, and the value is ignored. Recorded in [`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md).
- The deployment's domain, `API_DOMAIN`, is read by Docker Compose from the root `.env` and listed in the root `.env.example`; it is not a `Settings` variable, because `api/.env` holds only those.

## Repository layout

```
/web    SvelteKit app
/api    FastAPI app, source adapters, jobs and feed models
/docs   Architecture, workflow and data documentation
compose.yaml   Production services: the API and the reverse proxy
Caddyfile      Reverse proxy configuration
.env.example   Every variable compose.yaml reads
```

Structure of `/api`:

```
api/app/main.py            FastAPI app factory, lifespan, CORS and routers
api/app/settings.py        Settings class and get_settings()
api/app/log.py             Logging, configured once at startup
api/app/storage/           Job state (SQLite, with its migrations) and feed publication
api/app/routers/           One APIRouter per module
api/app/feeds/             One module per feed model, plus schema.py (exports the schemas), base.py (the base model and shared field types) and opponent.py (the shared side and opponent model)
api/app/sources/           One module per data source adapter, plus http.py (shared client and SourceError), teams.py (team codes) and postseason_mark.py (the postseason mark of a scoreboard game), and all_star_mark.py (the All-Star mark of a scoreboard game)
api/app/jobs/              One module per job, plus scheduler.py (the in-process scheduler), on_demand.py (the on-demand feed cache), presence.py (rule B), game_detail_feed.py (the game detail feed kind), team_feed.py (the team feed builder and kind), player_feed.py (the player feed builder and kind), standings_feed.py (the standings feed builder and kind), search_feed.py (the search feed builder and kind), cup_feed.py (the Cup feed builder and kind), cup_matchup_feed.py (the Cup matchup feed builder and kind), playoffs_feed.py (the playoffs feed builder and kind), playoffs_finals_feed.py (the playoffs finals feed builder and kind), all_star_feed.py (the All-Star feed builder and kind), calendar_feed.py (the calendar feed builder and kind), day_feed.py (the day feed builder and kind), past_game_detail_feed.py (the past game detail feed builder and kind), team_names.py (the franchise names kind), team_identity.py (the team identities of every league team object and the hero accent rule), season_standings_feed.py, season_team_feed.py and season_player_feed.py (the feed builders and kinds of a past season), season_cup_feed.py and season_cup_matchup_feed.py (the Cup and Cup matchup feed kinds of a past season), season_playoffs_feed.py and season_playoffs_finals_feed.py (the playoffs and playoffs finals feed kinds of a past season), past_player_ids.py (the player ids of the stored past feeds), player_identities.py (the shared player identity cache), highlights_search.py (the on-demand highlights search), all_star_edition_videos.py (the All-Star edition video search), cup_titles.py (the Cup title provider of the team feed) and playoffs_titles.py (the playoffs titles provider of the team feed)
api/data/                  Data directory (default), never committed
api/schemas/               Exported JSON Schemas, generated
api/tests/                 Tests, mirroring app/
api/pyproject.toml         Tool configuration only (ruff, mypy, pytest)
api/requirements.txt       Runtime dependencies, pinned
api/requirements-dev.txt   Development dependencies, pinned
api/.env.example           Every variable Settings reads
api/Dockerfile             Production image
api/.dockerignore          Keeps .env, local data and tests out of the image
```

Structure of `/web`:

```
web/src/routes/            Routes; +layout.ts prerenders everything
web/src/lib/               Shared code, imported as #lib
web/src/lib/contract/      Generated feed types, never edited
web/src/lib/feed/          Feed loading, polling and the props layer
web/src/env.ts             Build-time settings
web/.env.example           Every variable web/src/env.ts reads
web/scripts/               Contract type generation
web/src/app.html           HTML shell
web/static/                Static assets
web/tests/                 Tests, mirroring src/
web/package.json           Dependencies pinned, Node 24, the scripts the gate runs
web/pnpm-lock.yaml         Lockfile
web/vite.config.ts         SvelteKit, adapter-static and Vitest
web/eslint.config.js       ESLint
web/prettier.config.js     Prettier
web/tsconfig.json          TypeScript, strict
```

## Continuous integration

- CI runs on every pull request to `main` and every push to `main`, with
  one job per app, `api` and `web`, each running `scripts/gate.sh` for
  its app. Those two jobs are the checks `scripts/merge.sh` requires.
- Every action is pinned to a full commit SHA, and the workflow can only
  read the repository contents.
- Local git hooks in `.githooks/` run the fast gate (lint and format
  check) before a commit and the full gate before a push, only for the
  apps that changed.
- Recorded in [`adr/0005-ci-and-git-hooks.md`](adr/0005-ci-and-git-hooks.md).

## Open decisions

These are not decided. A change that depends on one of them stops and asks.
When one is closed, it gets an ADR in [`adr/`](adr/README.md) and this
document is updated in the same change.

- **Missing data**: what the page shows when a feed has no data for a day. Sample data is not an option in production.

## Closed decisions

Recorded in [`adr/0007-backend-runtime-and-data-pipeline.md`](adr/0007-backend-runtime-and-data-pipeline.md):

- **Hosting**: one always-free virtual machine running Docker Compose, with a reverse proxy for HTTPS.
- **Storage**: job state in one SQLite file on the data volume; feeds as JSON files.
- **Refresh cadences**: superseded by ADR 0020.
- **Star player selection**: the highest points plus rebounds plus assists per game on the current roster.
- **Highlight matching**: the league's official video channel, matched by both teams, the highlights label and the date.

Recorded in [`adr/0009-game-leader-selection.md`](adr/0009-game-leader-selection.md):

- **Game leader**: each team's top scorer by points; a tie on points goes to the most rebounds plus assists, and a tie on both to the first in the provider's order.

Recorded in [`adr/0010-final-game-attempts.md`](adr/0010-final-game-attempts.md):

- **Final game attempts**: detail at the final time and 2, 4 and 6 hours after it, then `unavailable`; a game first seen final takes that moment as its final time, never overwritten, with highlight attempts right away, 1 and 2 hours later.

Recorded in [`adr/0011-state-retention.md`](adr/0011-state-retention.md):

- **State retention**: superseded by ADR 0063.

Recorded in [`adr/0012-hero-rotation.md`](adr/0012-hero-rotation.md):

- **Hero rotation**: the hero rotates through the games of the day that are not postponed or canceled and have no guest side ([ADR 0025](adr/0025-guest-teams.md)); with none, it shows no game. Delayed games stay in the rotation.

Recorded in [`adr/0013-day-change.md`](adr/0013-day-change.md):

- **Day change**: the feed's today changes at US Eastern midnight; while any game of the previous day is live, the previous day stays today. The morning run refreshes the 7 days shown and never moves the window.

Recorded in [`adr/0014-star-guarantees.md`](adr/0014-star-guarantees.md):

- **Star guarantees**: every league side shows its star, a guest side has none ([ADR 0025](adr/0025-guest-teams.md)). The stars job runs in its own task and fetches all teams concurrently; the first games feed waits until every team has a star; a team with no roster player among its season leaders gets its star from individual averages; a failed team keeps its last known star.

Recorded in [`adr/0015-highlights-source.md`](adr/0015-highlights-source.md):

- **Highlights source**: the official channel's uploads, listed through the official video API 50 per request, once per highlights run, paged back to the oldest due game, and every due game is matched against that one list (rule E of [`source-rules.md`](source-rules.md), [`adr/0020-source-rules.md`](adr/0020-source-rules.md)); the key comes from `Settings` and is never logged.

Recorded in [`adr/0016-production-hosting.md`](adr/0016-production-hosting.md):

- **Production hosting**: Docker Compose runs the API image, non-root with one process and a health check, behind Caddy, which serves HTTPS for `API_DOMAIN`; state and feeds live on the named volume `data`; both services restart unless stopped. The front end is uploaded as static files to a CDN. Steps in [`deploy.md`](deploy.md).

Recorded in [`adr/0018-highlight-request-failures.md`](adr/0018-highlight-request-failures.md):

- **Highlight request failures**: a timeout, transport failure or error status uses up no highlight attempt; it is logged and recorded in the job's health, and the same attempt is retried no sooner than 10 minutes later. Any other outcome uses up the attempt.

Recorded in [`adr/0019-game-detail-route-and-feed.md`](adr/0019-game-detail-route-and-feed.md), superseded by ADR 0020, which keeps the route:

- **Game detail route and feed**: `/game/{id}` is rendered in the browser from a fallback page, and its detail feed is served at `/feeds/games/{id}.json`. This route stays in force under ADR 0020; the feed's cadences, shared data and deletion are superseded by it.

Recorded in [`adr/0020-source-rules.md`](adr/0020-source-rules.md):

- **Source rules**: [`source-rules.md`](source-rules.md), rules A to K, are in force for every job and feed build. It supersedes ADR 0019 (restating its route: `/game/{id}` is rendered in the browser from the fallback page and its feed is served at `/feeds/games/{id}.json`) and the refresh cadences of ADR 0007 and ADR 0014: the source is asked at most once per URL per freshness window, live data is refreshed every 30 seconds with someone present and every 2 minutes with nobody present, and everything else is built only when requested.

Recorded in [`adr/0021-player-and-team-pages.md`](adr/0021-player-and-team-pages.md):

- **Player and team pages**: `/player/{id}` and `/team/{code}` (lowercase standard code) are rendered in the browser from the fallback page; their feeds, `/feeds/players/{id}.json` and `/feeds/teams/{code}.json`, are built on demand under rule G. Game links only where `detailAvailable` is true; FG% is the fourth hero stat; Totals have no MIN; seasons use labels; the arena photo is in color, with no frame without a photo; "Season over." when there is no next game. The live block is drawn by a live card that replaces the next game card; the player page polls every 30 seconds while `live` is not null and every 60 seconds otherwise.

Recorded in [`adr/0022-standings-season-fallback.md`](adr/0022-standings-season-fallback.md):

- **Standings season fallback**: rule L of [`source-rules.md`](source-rules.md) is in force. When the division standings are not of the regular season, the adapter makes one extra request: a preseason year Y reads `season=Y-1`, a postseason year Y reads `season=Y`; a fallback that is not of the regular season fails. The team feed labels its record with `record.season`, and its streak, games behind and seed may be null. Rule L is adopted by this ADR; rules A to K stay with ADR 0020.

Recorded in [`adr/0023-standings-feed.md`](adr/0023-standings-feed.md):

- **Standings feed**: `/feeds/standings.json` is built on demand under rule G and served under rule H, stored as `standings/league`, and expires 1 hour after a final game of the league that follows the build and 7 days after the build; colors come from team info and are null on failure, and `state` is `final` on the rule L fallback or when every team has 82 games.

Recorded in [`adr/0024-search-feed.md`](adr/0024-search-feed.md):

- **Search feed**: `/feeds/search.json` is built on demand under rule G and served under rule H, stored as `search/league`. It lists the 30 teams and every roster player from the rosters the stars job keeps in memory, with no roster or per-player request, and answers 503 until every roster is fetched. It expires 1 hour after a final game of the league that follows the build, when the stars job fetches a roster after the build, and 7 days after the build. A failed standings or injuries read fails the build; colors are null on a failed team info read; `divisionRank` is an integer the page formats.

Recorded in [`adr/0025-guest-teams.md`](adr/0025-guest-teams.md):

- **Guest teams**: a game side outside the 30 is a guest team with the source's code when it sends one ([ADR 0026](adr/0026-one-guest-team-rule.md)), its name and city and `guest: true`. It has no star, record, standing, injuries or last games, its game has no season series, and its names are never links. Stars come only from league sides, and the hero never shows a game with a guest side.

Recorded in [`adr/0026-one-guest-team-rule.md`](adr/0026-one-guest-team-rule.md):

- **One guest team rule**: a guest code is optional in every feed contract, and `Opponent` is the one model of a game side or an opponent. A provider team is resolved by abbreviation, then by team id, then as a guest without a code; a side with neither a code nor a name is skipped with its game. A side reference (`winner`, stat leaders, the win probability leader) is `away` or `home`. The game log keeps preseason games, with a Preseason tab, and the last five games leave them out; averages and milestones do not change. Adapters validate only the events they use. `TeamMark` draws every side or opponent that can be a guest, and a guest tile without a code shows the initials of its display name.

Recorded in [`adr/0027-no-game-videos-section.md`](adr/0027-no-game-videos-section.md):

- **No game videos section**: the game page shows no videos other than the highlights and never links out to watch one. The game detail feed has no `videos` field; a stored feed that still has it is read with the field dropped, never rebuilt for it.

Recorded in [`adr/0028-cup-feed.md`](adr/0028-cup-feed.md):

- **Cup feed**: `/feeds/cup.json` is built on demand under rule G and served under rule H, stored as `cup/league`. It reads the 6 Cup groups, their tables, the 2 conference tables and the 30 season schedules, with the season of the stars job's latest roster, and answers 503 until a roster is fetched when nothing is stored. It expires 1 hour after a final Cup game that follows the build and 7 days after the build; once the championship is final it is kept while its season is the current one. Game rounds come from the game note and travel as a nullable `cup` mark on the games, game detail and team feeds.

Recorded in [`adr/0029-cup-matchup-feed.md`](adr/0029-cup-matchup-feed.md):

- **Cup matchup feed**: `/feeds/cup/matchups/{id}.json` has one feed per bracket slot (the 7 slot ids), built on demand under rule G and served under rule H, stored as `cup-matchups/{id}`. It reads the slot from the stored Cup feed, which it builds first when missing or stale, and per team the roster, the season schedule, the league injuries, the season averages and the depth chart (`DEPTH_CHART_URL`, kept 24 hours). It carries the slot's game as the Cup feed stores it and, per side, the label, the rule, the team (known or projected) and its path in the Cup, injuries and roster with per game averages, starters and stat leaders. It expires 1 hour after a final game of either team, when the Cup feed it read is rebuilt and 7 days after the build; a failed Cup feed, roster, schedule or injuries read fails the build, and a failed averages or depth chart read only removes the leaders or the starters. An id outside the 7 slots answers 404 with no read.

Recorded in [`adr/0032-playoffs-feed.md`](adr/0032-playoffs-feed.md):

- **Playoffs feed**: `/feeds/playoffs.json` is built on demand under rule G and served under rule H, stored as `playoffs/league`. It reads the play-in and postseason windows, the division standings, the 30 team infos, the postseason leaders, the season awards and, from the first day of the play-in window, the scoreboard of every day of both windows. It answers 503 until the stars job knows the season and has fetched every roster when nothing is stored. State, stages, the 15 series, the play-in and the champion come from the games: the wins, summary, status and winner of a series are counted from its final games, never read from the source's series object ([`adr/0060-playoffs-series-state-from-its-games.md`](adr/0060-playoffs-series-state-from-its-games.md)). It expires 1 hour after a final postseason game that follows the build, while its state is picture also 1 hour after any final game of the league, at the start of the play-in window when the build precedes it and 7 days after the build; once the Finals series is complete it is kept while its season is the current one. A season type, standings or scoreboard day that fails fails the build; leaders, awards and team info only null their part (no record read since `adr/0073`). The feed has its own stage status and imports nothing from the Cup section.

Recorded in [`adr/0033-playoffs-finals-feed.md`](adr/0033-playoffs-finals-feed.md):

- **Playoffs finals feed**: `/feeds/playoffs/finals.json` is built on demand under rule G and served under rule H, stored as `playoffs-finals/league`. It reads the stored playoffs feed, which it builds first when missing or stale, and per final Finals game one cached game detail response, per finalist the postseason record and statistics, and per roster player (and the Finals MVP) the postseason player stats. It carries the Finals games as the playoffs feed stores them with the leaders, the win probability and the largest deficit of the curve team, the Finals MVP, the road to the title, the head to head bars and the postseason averages of the rosters. The route serves the playoffs feed first, so a missing one answers 503; a Finals with no game answers 404 with no read. It expires 1 hour after a postseason final game that follows the build, when the playoffs feed it read is rebuilt and 7 days after the build; once the Finals series is complete it is kept while its season is the current one. A failed detail, plays, stats or record read only nulls its part. The feed imports nothing from the Cup section.

Recorded in [`adr/0035-playoffs-marks-in-core-feeds.md`](adr/0035-playoffs-marks-in-core-feeds.md):

- **Playoffs marks**: the games, game detail and games feeds carry a nullable `postseason` mark (stage, round, conference, game number, series summary, play-in kind and stakes), read from the season type, competition type, note and series object of the scoreboard. The stakes are those the game had at tip-off, from the series wins entering it. The core games feed never fails because of postseason data: an unreadable or inconsistent value only leaves that game's mark null, except that a series game's mark is always set and read as set in [`adr/0050-postseason-mark-of-every-series-game.md`](adr/0050-postseason-mark-of-every-series-game.md). The team feed carries up to three `titles` of the current season (NBA champions, NBA Cup champions, conference champions) read from the stored playoffs and Cup feeds, and also expires when either was rebuilt after it.

Recorded in [`adr/0036-all-star-feed.md`](adr/0036-all-star-feed.md):

- **All-Star feed**: `/feeds/all-star.json` is built on demand under rule G and served under rule H, stored as `all-star/league`. With no stored edition, the build reads the season calendar, tries at most 6 days with games from February 1 to March 7 of the end year (next to the longest run of days without games first, Sundays first) and stores the first with All-Star games; the previous edition is found the same way, and a candidate day equal to today is read with the 30-second scoreboard freshness, the others with 24 hours, as set in [`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md). The feed has the edition (date, venue, format as parts, counts, default game, teams with their placement and results, games with box scores, team statistics, leaders and Top 5), the MVP, the previous edition's recap and the previous edition as its after view. The state is before, live or after by game status. It expires 30 seconds after the build while live or on the edition's date, before the edition 24 hours after the build, and once every game is final it is kept while its season is the current one, but only when it was built at least 1 hour after the latest time its games were first seen final. The previous edition is read with a 24-hour freshness. A failed current scoreboard day fails the build; any other failed read only nulls its part, except an input of the previous edition's MVP, handled as in ADR 0056. The stored per-game highlights this feed added when served are replaced by the edition video, as set in [`adr/0048-highlights-backfill-and-edition-video.md`](adr/0048-highlights-backfill-and-edition-video.md).

Recorded in [`adr/0040-calendar-and-day-feeds.md`](adr/0040-calendar-and-day-feeds.md):

- **Calendar and day feeds**: `/feeds/seasons/{season}/calendar.json` (season by end year from 1994) and `/feeds/days/{date}.json` are built on demand under rule G and served under rule H, stored as `calendars/{season}` and `days/{date}`. The calendar is read from the scoreboard day of February 1 of the end year: its days are the US Eastern dates of the entries, `firstDay` and `lastDay` the first and last, `windowDays` the stored games feed's days; it answers 404 outside 1994 to the current season and 503 while the season is unknown, expires 24 hours after the build for the current season and is kept for a past season built after its last day (superseded by ADR 0063: deleted when not served in 90 days and built again on the next request). The day feed answers 404 for a non-date, a day before 1993-10-01, a future day and a day of the games feed. Its games are `PastGame`s: null stars, empty highlights as built (the stored highlight is added when served, as set in [`adr/0048-highlights-backfill-and-edition-video.md`](adr/0048-highlights-backfill-and-edition-video.md)), `available` stats on a final game, with null leaders and team stats, as set in [`adr/0054-historical-sides-and-past-pages.md`](adr/0054-historical-sides-and-past-pages.md), sides by team id first, marks read case-insensitively, a game that cannot be mapped skipped with a log line. A day with every game final or no game is kept (bounded by ADR 0063 in the same way); otherwise it expires 6 hours after the build. The day feed stays outside the games job, the hero, the highlights job and the live refresh; the cleanup deletes it when not served in 90 days (ADR 0063).

Recorded in [`adr/0041-past-game-detail.md`](adr/0041-past-game-detail.md):

- **Past game detail**: `/feeds/games/{id}.json` also serves a final game of a stored day feed that the games job has not loaded, stored as `past-games/{id}`, built once on request under rule G, served under rule H and kept (rule D; deleted when not served in 90 days and built again on the next request, ADR 0063); it is never refreshed by the games job, the live refresh or the highlights job. A game of a day feed that is not final, and an id in neither nor registered by a past team or player feed (ADR 0053), answer 404 with no source request. It is built from the day feed's game (status, time, scores, winner, marks, sides, search link) and one summary (venue, box score, team stats, win probability, season), sides by team id first, no injuries or season series read. `stars`, `injuries`, `lastGames`, `standings`, `seasonSeries` and both records are null, and `highlights` is null as built (the stored highlight is added when served, as set in [`adr/0048-highlights-backfill-and-edition-video.md`](adr/0048-highlights-backfill-and-edition-video.md)); the blocks the summary lacks are null (a missing team percentage or plus-minus is null inside them, as set in [`adr/0052-box-score-reading.md`](adr/0052-box-score-reading.md)). A new nullable `seasonLabel` is set on a past game and null on the games feed days. `PastGameDetailFeed` replaces only the league-side rule of `GameDetailFeed`, and its schema is the game detail schema.

Recorded in [`adr/0042-calendar-seasons-and-day-season.md`](adr/0042-calendar-seasons-and-day-season.md):

- **Calendar seasons and the day's season**: `/feeds/seasons/current/calendar.json` resolves to the current season's end year before the cache and serves the same stored file, body, ETag and expiry (503 while the season is unknown). The calendar's `seasons` run from the current season down to 1994, newest first, and are set again at serve time. The day feed's `season` is read from `leagues[0].season.year` of the day's scoreboard response and a day without a readable season fails the build. `/day/{date}` is rendered in the browser, and the day page and the calendar sheet load their feeds once.

Recorded in [`adr/0043-season-feeds-and-franchise-names.md`](adr/0043-season-feeds-and-franchise-names.md):

- **Season feeds and franchise names**: `/feeds/seasons/{season}/standings.json`, `/feeds/seasons/{season}/teams/{code}.json` and `/feeds/seasons/{season}/players/{id}.json` (kinds `season-standings`, `season-teams`, `season-players`, ids `{season}`, `{season}-{code}` and `{season}-{id}`) serve a season from 1994 to the season before the current one (404 otherwise with no source request, 503 while the season is unknown), are built once on request and kept. Past reads send the season query value and resolve teams by provider id first; the past division standings have no rule L fallback. The standings are `final` with the source's clinchers. The team feed has that season's name, city, record (`playoff` null before 2020-21), leaders, roster (the box-score players of that season, as set in ADR 0053) and schedule, and null `arena`, `coach`, `injuries`, `nextGame`, `cup` and `titles`; `divisionRank` is 1 to 8; a franchise with no team object that season answers 404 after one read (an inactive team object answers). The player feed has that season's game log, summary (null ranks), averages and milestones, the career `seasons` and `awards`, the team of the newest game, null `injury`, `nextGame` and `live`, and `seasonLabel`. `TeamFeed.names` lists the franchise identities (runs read from the season team object, kept 7 days as the internal kind `team-names`). A player on no roster known from a stored past roster or box score is served by the current player feed with `team` null and `active` from the athlete object.

Recorded in [`adr/0044-season-selector-sources.md`](adr/0044-season-selector-sources.md):

- **Season selector**: the selector's seasons and labels are the `seasons` of the current calendar feed, whose first entry is the current season. `/standings` lists every season, `/team/{code}` the seasons inside one of the feed's `names` runs, `/player/{id}` the seasons whose label matches a regular-season row plus the current one. `?season=YYYY` carries the end year; the current season has no parameter, and an absent, malformed, unknown or current value shows the current season with the existing feeds. A past season reads its season feed once and is not polled. With the calendar unavailable the selector is hidden. A past team 404 shows "No team this season."; a past team page hides Overview and Injuries; a past standings page draws no seed separator lines, because no feed says whether that season had a play-in.

Recorded in [`adr/0045-season-competition-feeds.md`](adr/0045-season-competition-feeds.md):

- **Season competition feeds**: `/feeds/seasons/{season}/cup.json` and `/feeds/seasons/{season}/cup/matchups/{id}.json` (kinds `season-cup`, id `{season}`, and `season-cup-matchups`, id `{season}-{slot}`) serve the Cup and a Cup matchup of a season from 2024 to the current one, with the models of the current feeds and no new schema. The current season resolves before the cache to the current kinds, so their feeds, expiry and routes do not change; any other season outside 2024 to the current one, an ill-formed one or a slot outside the 7 answers 404 with no source request, and 503 while the current season is not known. A past Cup reads the same sources with the season value and the schedules by provider id first, and must build as `complete`, or the build fails and nothing is stored. A past matchup reads the stored season Cup and the two teams' season schedules only: `injuries` and `roster` are empty lists. Both are built once on request under rule G and kept.

Recorded in [`adr/0046-season-playoffs-feeds.md`](adr/0046-season-playoffs-feeds.md):

- **Season playoffs feeds**: `/feeds/seasons/{season}/playoffs.json` and `/feeds/seasons/{season}/playoffs/finals.json` (kinds `season-playoffs` and `season-playoffs-finals`, id `{season}`) serve the playoffs and the playoffs finals feed of a season from 1994 to the current one, with the models of the current feeds. The current season resolves before the cache to the current kinds; any other season outside the range or ill-formed answers 404 with no source request, and 503 while the current season is not known. `playIn` is nullable: a season before 2021 sends no play-in read and has a null play-in, seeds 1 to 8 from the standings and seed labels. A past postseason with no competition type gets its rounds from the series (the k-th series of both teams, the Finals the only series across the conferences, 8-4-2-1 series), or the build fails with a logged reason. A round 1 team with no seed is placed by the round 2 series it feeds, with null side seeds. A game with no game number takes its position in its series. Leaders, awards and the records are null only on a 404, any other failed read fails the build, and a past feed must build as `complete` or nothing is stored. The past Finals reads the finalists' season rosters and has no detail; its stored highlights are added when served, as set in [`adr/0048-highlights-backfill-and-edition-video.md`](adr/0048-highlights-backfill-and-edition-video.md). Both are built once on request under rule G and kept.

Recorded in [`adr/0047-season-all-star-feed.md`](adr/0047-season-all-star-feed.md):

- **Season All-Star feed**: `/feeds/seasons/{season}/all-star.json` (kind `season-all-star`, id `{season}`) serves the All-Star feed of a season from 1994 to the current one, with the model of the current feed. The current season resolves before the cache to the current kind; any other season outside the range or ill-formed answers 404 with no source request, and 503 while the current season is not known. The edition is the stored one or the first February day of the season's calendar with All-Star games, which is then stored; a season with none answers 404 and is remembered in memory. The previous edition is found the same way, null before 1994 or when not found. A 404 on a game read or the awards only nulls its part, any other failed read fails the build, and a past feed must build as `after` or nothing is stored. `leagueTeam` is null and no per-game highlight is set; the edition video is added when served as `editionHighlight`, as set in [`adr/0048-highlights-backfill-and-edition-video.md`](adr/0048-highlights-backfill-and-edition-video.md). Built once on request under rule G and kept.

Recorded in [`adr/0048-highlights-backfill-and-edition-video.md`](adr/0048-highlights-backfill-and-edition-video.md):

- **On-demand highlights search and the All-Star edition video** (ADR 0065, which replaces the daily backfill of ADR 0048): a final game served with no highlight once its live attempts are over, a past game detail served with none and an All-Star edition served past its video window with none start one search of the channel by query, in the background, so the response is never delayed. At most `HIGHLIGHTS_SEARCH_DAILY_CAP` (default 80) searches are sent per US Eastern day, counted in the state database, one per target at a time, and none without `HIGHLIGHTS_SEARCH_API_URL`. The first result in the provider's order whose title matches and whose thumbnail is served is stored; a search with no match stores a mark and the target is not searched again. The day feed, the past game detail and the season Finals add the stored highlight when served; an All-Star game gets no per-game highlight on any feed; `editionHighlight` (nullable, default null) is added when served on the edition, the previous edition and the recap of both All-Star kinds. The All-Star section reaches the core search through a collaborator wired in `main.py`.

Recorded in [`adr/0049-competition-season-selectors.md`](adr/0049-competition-season-selectors.md):

- **Competition season selectors**: `/cup`, `/playoffs` and `/all-star` follow ADR 0044: the calendar gives the selector's seasons, `?season=YYYY` picks a past season, which reads its season feeds once and is not polled, and the selector is hidden when the calendar is unavailable. The Cup lists the calendar's seasons from 2024 (`FIRST_CUP_SEASON`, a web constant that mirrors the api's) and the season on show, as set in ADR 0054; the playoffs and the All-Star list every season. A 404 on a season feed shows the unavailable state. A past Cup matchup sheet shows a "current season only" line in place of the injuries and the roster. On a past playoffs season only, the head to head is drawn when at least one bar value is not null and a null seed draws no seed number; the `playin` stage is not drawn when `playIn` is null. The All-Star edition video replaces the selected game's media frame wherever it is present, and the "Last time" champion card links to the previous edition's video in a new tab.

Recorded in [`adr/0050-postseason-mark-of-every-series-game.md`](adr/0050-postseason-mark-of-every-series-game.md):

- **Postseason mark of every series game**: a game of season type 3 always carries a `postseason` mark. The round and the game number come from the note in any letter case, else the round from the competition type with the conference from the note's first word; what cannot be read is null inside the mark. No game number gives null `number` and `stakes`, no round gives `stage` `playoffs` with null `round` and `conference`, drawn as the "Playoffs" tag alone, and an unreadable series object nulls only `summary` and `stakes`. The play-in does not change.

Recorded in [`adr/0051-all-star-notes-and-untimed-games.md`](adr/0051-all-star-notes-and-untimed-games.md):

- **All-Star notes and untimed games**: the notes "ALL STAR GAME" and "NBA All-Star Game", in any case, read as the round "All-Star Game". A final All-Star game with a score and no line score is kept with a null `lineScore` in the games, day and game detail feeds, and its card has no expanded details. A final game without a score and a live game without a clock are still skipped.

Recorded in [`adr/0052-box-score-reading.md`](adr/0052-box-score-reading.md):

- **Box score reading**: team turnovers are `totalTurnovers` when the provider sends it, else `turnovers`. A game whose players all have a plus-minus of 0 has a null `plusMinus` on every row and the page hides the column. A team percentage the provider does not send is null in `teamStats` and `boxScore.totals`, its stat leader is null and the page shows "—"; a missing count stat is null too (superseded by [`adr/0055-past-season-reading-rules-and-versioned-stored-data.md`](adr/0055-past-season-reading-rules-and-versioned-stored-data.md), which replaced the failure). The All-Star feed's `teamStats` is null when a field goal percentage or any other value is null.

Recorded in [`adr/0054-historical-sides-and-past-pages.md`](adr/0054-historical-sides-and-past-pages.md):

- **Historical sides and past pages**: every league side of a past feed carries `seasonCode` (that season's abbreviation from the season team object) and `historical` (true when that season's name, city or abbreviation differs from the current season's); the same two fields are on the past team header and on a standings row. The link code stays today's. The past playoffs, Finals and Cup sides are named by the season team object. The web draws a historical side as the guest sigla box with `seasonCode` and no team color or strip. A final game of the day feed has `available` stats with null leaders and team stats. The Cup selector keeps the season on show. The All-Star edition sends `format` as parts (`targetPoints`, `untimed`, `periods`, `minutes`) instead of `formatLine`. The season code of a historical identity is now the source's own abbreviation (`adr/0055`). `SEASON_BUILD_VERSION` is 3.

Recorded in [`adr/0053-season-level-rules-for-past-seasons.md`](adr/0053-season-level-rules-for-past-seasons.md):

- **Season level rules for past seasons**: a team exists in a season when its season team object answers, `isActive` is never read. Since `adr/0059` a past team has a null roster and null leaders (before it, the roster was the players with a stat line in the box scores of its final games; those stored feeds keep it), the state table `past_games` keeps the stored rows it has, and, since `adr/0061` (before it, from the Finals box scores and the stored past game players), the past playoffs leaders and awards are named from the shared player identities, and the past Finals `averages` are null. `TeamLeader.position` may be null. The number of a past player is null since `adr/0059`. The league sides of a past schedule, game log, day and standings are named from their own payloads since `adr/0059` (before it, by the season team object), with today's code. `detailAvailable` is true for every final game of a past schedule and game log, their dates are registered, and the past game kind knows a registered id and builds its day first. The two quarterfinals of a past Cup conference are placed by start time with a null seed label. The only game of a single-game All-Star edition is its championship, and two sides that share a name are drawn with their code. The eight kept season kinds carry `buildVersion`, and a stored feed of another or no version is rebuilt on its next request.

Recorded in [`adr/0055-past-season-reading-rules-and-versioned-stored-data.md`](adr/0055-past-season-reading-rules-and-versioned-stored-data.md):

- **Past season reading rules and versioned stored data**: the Cup group note of the first edition ("NBA In-Season Tournament - Group Play") is the group round. An award has as many winners as the source sends. A box score row with no player id is skipped and logged once, by every reader. A team or player stat the source does not send is null, never a failure (a value that is sent and is not a number still fails), and the page hides it. The season code of a historical identity is the source's own abbreviation, the season code of an identity equal to today's is the standard code. Every plain-code field of a past feed carries `seasonCode`, and every career row of both player feeds carries `seasonCodes` from the stored franchise names runs, set when served; a missing or outdated names list is built in the background (`FeedCache.warm`). The postseason mark carries the series wins and the winner, and a player award carries its `code` and `team`. The franchise names, the past calendars and the stored past game players carry `buildVersion`, a team feed is stale while its stored names are of another version, and `SEASON_BUILD_VERSION` is 3.

Recorded in [`adr/0056-paced-past-builds-and-one-edition-mvp-path.md`](adr/0056-paced-past-builds-and-one-edition-mvp-path.md):

- **Paced past builds and one edition MVP path**: the pacing of the past roster reads (`SOURCE_BUILD_PAUSE_MS`) was removed by `adr/0059`; a 429 or 503 stops a build with the reason "rate limited" (`adr/0058`). The inputs of a finished edition's MVP (awards, sections, extras) are read by one function for the season feed and for the current feed's previous edition, with the season feed's policy (a 404 nulls its part, any other failure raises); on the current feed a failure keeps the stored previous blocks when they carry an MVP, else fails the build. "Same MVP" leaves `leagueTeam` out.

Recorded in [`adr/0057-past-game-detail-leaders.md`](adr/0057-past-game-detail-leaders.md):

- **Past game detail leaders**: the game detail feed has a nullable `leaders` (the games feed's `Leaders`), filled only by the past game detail build through the leader rule of ADR 0009 and null on the current feed, the live refresh and the games job. A side without a stat line leaves it null without failing the build. A stored past game detail without the `leaders` key is served, then rebuilt on its next request; one with a null block of the current version is fresh; `SEASON_BUILD_VERSION` stays 3. A league leader has a photo. The past game page draws no leaders block; the day cards read the field on their first expand.

Recorded in [`adr/0058-bounded-past-competition-reads.md`](adr/0058-bounded-past-competition-reads.md):

- **Bounded reads of the past competition builds**: the past playoffs (140 since `adr/0073`, identity reads included), Finals (12 since `adr/0061`), Cup (44), Cup matchup (2) and All-Star (60) builds declare a read budget counted in the shared client (a request that reaches the network is a read; a cache hit is not), read at most four requests at once with no pause, and stop with a logged reason and nothing stored when they pass the budget or are rate limited (429, 503). The past playoffs read the standings, the postseason schedule of the first 8 teams of each conference (10 from 2021), the play-in window and days, the leaders, the awards and the Finals game details (no finalist record since `adr/0073`), and no postseason window, bracket day, team info or roster. Team colors come from the cached team info, else null. The past Finals reads no roster: `averages` is null (nullable). The playoffs and Cup sides are named from their own payloads. The past All-Star takes its previous edition from the stored feed of the season before. `SEASON_BUILD_VERSION` stays 3.

Recorded in [`adr/0059-bounded-past-page-reads.md`](adr/0059-bounded-past-page-reads.md):

- **Bounded reads of the past page builds**: the past team (5, 4 sent), player (4), day (1), game detail (1) and standings (1) builds declare a read budget counted in the shared client, read at most four requests at once with no pause, and stop with a logged reason and nothing stored when they pass the budget or are rate limited. Their league sides are named from their own payloads (the scoreboard day, the player game log, the team schedules, the standings rows) with the season code of the stored franchise names, and no build reads a season team object per side. `TeamFeed.colors`, `leaders` and `roster` and `PlayerFeed.awards` are nullable (the current feeds still set them): a past team has a null roster and null leaders and colors from the cached team info, and a past player has a null number, draft and awards, its season rows from the two career statistics reads and its team from the stored franchise names. The dates of a team's final games are registered from its schedules. A player stored in a past playoffs or Finals feed is a known id, and an id known from stored past data never waits for the rosters. `SeasonRosters` and `SOURCE_BUILD_PAUSE_MS` are removed. `SEASON_BUILD_VERSION` stays 3.

Recorded in [`adr/0060-playoffs-series-state-from-its-games.md`](adr/0060-playoffs-series-state-from-its-games.md):

- **Playoffs series state from its games**: the wins, status, summary and winner of a playoffs series, the complete state and the champion's Finals result are counted from the final games (a game's winner is its source winner flag, else the higher score), never read from the source's series object, so a past season built from team schedules that send none reaches the complete state. A series with four wins for one team is complete (`{code} wins series 4-{n}`), one with a final game is in progress (`{code} leads series {a}-{b}` or `Series tied {a}-{a}`), and one with no final game is upcoming with null wins and summary. Two teams at four wins fail the build. A past schedule event takes its season type from `seasonType.type` (3, 5, missing as 3, any other skipped). The feed cache records a build or dependency error with its own non-empty `reason`, else with its type. `SEASON_BUILD_VERSION` stays 3.

Recorded in [`adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md`](adr/0061-past-playoffs-player-identities-and-finals-mvp-averages.md):

- **Past playoffs player identities and Finals MVP averages**: the past playoffs names the first five leaders of each category (three since `adr/0066`) and every award winner from a shared player identity reader (`PlayerIdentities`), one athlete object read per player kept in the state table `player_identities` for 30 days, misses read at most eight at once on the wide lane of the read budget; a read that fails gives "—" with no photo and is not stored, a rate limit stops the build, and a player is never left out. A leader's or winner's team is its own team reference. The champion's record (removed by `adr/0073`) was the counted Finals winner's. The past playoffs budget is 63 (61 since `adr/0073`) plus 45 leader reads plus one read per award winner (`ReadBudget.extend`, retired by `adr/0066`); the past Finals reads the MVP's postseason career once (budget 12), keeps `averages` null and gives the MVP the career row of the season label, else null. The past playoffs and Finals kinds carry `SEASON_BUILD_VERSION + 1`; every other season kind keeps `SEASON_BUILD_VERSION`, which stays 3.

Recorded in [`adr/0062-bounded-upstream-reads-and-on-demand-builds.md`](adr/0062-bounded-upstream-reads-and-on-demand-builds.md):

- **Bounded upstream reads and on-demand builds**: the shared client keeps at most eight requests in flight, budgeted or not (the budget slot first). A 429 or 503 answer pauses every request until its `Retry-After` (seconds or HTTP date; 60 seconds when missing or unreadable; at most 15 minutes), a paused read raises "source paused" with no request, a fresh cache entry is still served, the start is logged once without the URL and a later rate limit only extends the pause. The feed cache starts at most 16 builds: a missing feed at the cap answers 503, a stale one is served as stored, and a refresh, a warm-up and a dependency start nothing. A build runs at most 60 seconds and is recorded as "build timed out". A paused read is a rate limit (a budgeted build stops as "rate limited") and a failed request (a highlight attempt is not spent).

Recorded in [`adr/0063-bounded-state-and-kept-feeds.md`](adr/0063-bounded-state-and-kept-feeds.md):

- **Bounded state and kept feeds**: the state database runs in WAL mode and every connection waits up to 5 seconds on a lock. With the games job's daily fetch, source cache entries fetched more than 7 days ago, `games` rows dated more than 10 days before the current US Eastern date, and `past_games` and `player_identities` rows not touched in 90 days are deleted, and the stored file and build row of every id of the ten kept kinds (day, past game detail, calendar, and the past team, player, playoffs, Finals, Cup, Cup matchup and All-Star feeds) not served in 90 days are deleted and built again on their next request. The past player ids learned from stored feeds are kept in `past_player_ids` and never deleted, and the daily cleanup saves them before it deletes any file. A past game detail build registers its game in `past_games`. Highlights, stars and job health are never deleted. The day, past game detail and Finals feeds read only the highlights of their games, and `/health` lists at most 50 failed builds, newest failure first.

Recorded in [`adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md`](adr/0064-degrade-one-bad-item-instead-of-failing-a-feed.md):

- **Degrade one bad item instead of failing a feed**: a game or team that cannot be read is skipped, or has that block null, with a log line naming its id or team code, and never fails the feed (rule G, degrade rule). It replaces ADR 0038 for league events and live details that cannot be read, ADR 0043 for a names build whose current season could not be read, and rule D for a final detail with no summary.

Recorded in [`adr/0065-background-work-limited-to-games-highlights-and-stars.md`](adr/0065-background-work-limited-to-games-highlights-and-stars.md):

- **Background work limited to games, highlights and stars**: only the games, highlights and stars jobs are scheduled. The All-Star discovery job and the highlights backfill are removed; the All-Star build finds its edition from the season calendar and the highlights are found by the on-demand search (rule G). The franchise names are built once per team and kept. It replaces the discovery of ADR 0036, the backfill of ADR 0048, the 7-day names of ADR 0055 and rules D, E and F of ADR 0020 where they differ.

Recorded in [`adr/0066-cut-read-amplification-of-on-demand-builds.md`](adr/0066-cut-read-amplification-of-on-demand-builds.md):

- **Cut read amplification of on-demand builds**: the current playoffs build reads a scoreboard day before today through the source cache fresh for 7 days, or from the latest final time of a postseason game of that day when later; today and later days keep 30 seconds. It runs in two budgets that count reads only (2, then the day count plus 59 since `adr/0073`), at most four in flight, so a rate-limited team info, leaders or awards read only nulls its part. The season playoffs declares one budget of 140 since `adr/0073` (61, 27 leader identities, at most 52 distinct award winners; a further winner is shown with "—"), lists three leaders per category and removes `ReadBudget.extend`. The Cup build reads a team schedule fresh for 24 hours, 1 hour for a team with a game today in the games job's shown games (and for every team before the job's first run), under a budget of 44 that counts reads only. Team info is fresh for 24 hours. The standings (32) and search (33) builds declare a budget that counts reads only. The team feed reads the six Cup group tables only from the first Cup game (November 1 until known) to December 31 while the stored Cup feed is not complete, else it takes the mark from the stored Cup feed through the Cup section's injected provider. A season player whose build finds no season game log or no season row is unknown (404, nothing stored, no game registered, remembered in memory), and a stored feed with an empty game log is not kept. The day feed check takes the shown days from the games job's memory after its first run, and the past game detail index is built at startup and fed by `FeedKind.after_publish`. Stored past playoffs keep five leaders until rebuilt for another reason.

Recorded in [`adr/0067-read-budgets-of-every-on-demand-build.md`](adr/0067-read-budgets-of-every-on-demand-build.md):

- **Read budgets of every on-demand build**: the current game detail (5), team (15), player (11), Cup matchup (9), playoffs finals (48) and All-Star (122) builds and the calendar build (1) declare a read budget equal to their worst-case read count. The current builds count reads only (`stop_on_rate_limit` false), the calendar stops on a rate limit for a past season, and a dependency built first keeps its own budget. The current Finals reads the postseason averages of at most 18 roster players per finalist, in jersey order, and always the Finals MVP; a further player is listed with no values and one warning is logged. The All-Star budget assumes up to 8 games per edition and up to 30 award documents per season; past that the build fails over budget and keeps the stored feed. It extends ADR 0066 and replaces nothing in it.

Recorded in [`adr/0068-shared-team-identity-and-hero-accents.md`](adr/0068-shared-team-identity-and-hero-accents.md):

- **Shared team identity and hero accents**: the stars job reads each team's info once a day and keeps each team's logo and colors in the state store (`team_identities`). Every league team object of every feed (an `Opponent` and its subclasses, a standings row, a search team and player team, the team feed root, a player's team and an All-Star league team) carries `logo`, and an `Opponent`, a search player's team and a player's team also carry `colors`; the others keep the colors they were built with. They are added when a feed is served, and at publish for the games feed, and are null on a guest, a historical side and an unknown team. Every game of the games feed carries `accent`, the color each side shows in the hero, by a rule in OKLab with a lightness floor of 0.36 and a distance floor of 0.12.

Recorded in [`adr/0069-daily-expiry-of-fallback-standings-and-team-feeds.md`](adr/0069-daily-expiry-of-fallback-standings-and-team-feeds.md):

- **Daily expiry of fallback feeds**: a standings or team feed whose build used the rule L fallback (the division standings, or the team leaders of the previous season) also expires at the first `DAILY_FETCH_TIME` in US Eastern strictly after its build; the fallback is recorded with the build in `feed_builds`, and a build without it, or a row from before, keeps the current rule.

Recorded in [`adr/0070-team-logos-in-the-player-career-rows.md`](adr/0070-team-logos-in-the-player-career-rows.md):

- **Team logos in the career rows**: each season row of the player feeds carries `logos`, one entry per team, added when the feed is served: the team's identity logo when the season's code equals today's code, else null (historical, unknown or no identity). The Career row has none. The web draws an inline mark before each code.

Recorded in [`adr/0071-playoffs-bracket-without-a-camera.md`](adr/0071-playoffs-bracket-without-a-camera.md):

- **Playoffs bracket without a camera**: the playoffs bracket is a plain grid at 1:1 (no translate or scale), sharp at every browser zoom; the playoffs section no longer imports the shared camera, which the Cup keeps on desktop.

Recorded in [`adr/0072-resolved-team-colors-in-the-playoffs-and-cup-feeds.md`](adr/0072-resolved-team-colors-in-the-playoffs-and-cup-feeds.md):

- **Resolved team colors in the playoffs and Cup feeds**: the series, bracket slots, champions and Finals MVPs (and the Finals MVP winners among the awards) carry `accent`, the resolved color of the rule of ADR 0068 from the team identity, a pair keyed `top` and `bottom` for a series or slot (smaller seed first; in the Cup, then the away side second). It is null for a side with no team, a guest, a historical side, an unknown code or a renamed plain code. It is added when the feed is served and never stored, so no rebuild.

Recorded in [`adr/0073-no-champion-record-or-point-differential-in-the-playoffs-feed.md`](adr/0073-no-champion-record-or-point-differential-in-the-playoffs-feed.md):

- **No champion record or point differential in the playoffs feed**: the playoffs champion has no `record`, `home`, `road` or `pointDifferential`; the current build reads no postseason record (`OTHER_READS` 59) and the past build no finalist record (`READ_BUDGET` 140: 61, 27, 52). A stored playoffs feed, current or past, whose champion still carries them is read with them dropped (`RETIRED_CHAMPION_FIELDS`), not rebuilt; any other unknown key still fails. The Finals feeds keep their finalist records.

## Future

- The shape of an undecided All-Star game: verify against the source when the next edition is scheduled whether its sides come with neither a code nor a name, as ADR 0039 assumes.
- A notification panel for job failures.
- Official game clips: research official sources with clips tied to a game, so a videos section can return (see ADR 0027).
- Team videos: the latest uploads of each team's official channel, on the team page.
