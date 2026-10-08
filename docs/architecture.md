# Architecture

How Courtside is built and why. This document records decisions that are in force. Anything not decided yet is listed under [Open decisions](#open-decisions) and must not be assumed by any change.

## Principles

1. **The source is asked at most once per URL per freshness window, whatever the number of visitors; live data is refreshed on a schedule that slows down when nobody is present; everything else is built only when requested.**
2. **The front end only draws.** It reads published feeds and renders them. It holds no business rules about games, standings or players.
3. **One contract, defined once.** The shape of every feed is defined in backend code and generated for the front end. Nothing is redefined by hand on either side.
4. **Every input is validated.** Data coming from a source is validated before it is used. A feed is validated before it is published.
5. **Small core, removable extras.** The core is the scoreboard. Seasonal sections are self-contained and can be added or removed without touching the core.

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

- Jobs run on a schedule inside the backend process. Each job owns one kind of data. Refresh cadences, the shared source cache, presence and on-demand builds follow the rules in [`source-rules.md`](source-rules.md), adopted by [`adr/0020-source-rules.md`](adr/0020-source-rules.md), which supersede the cadences of [`adr/0007-backend-runtime-and-data-pipeline.md`](adr/0007-backend-runtime-and-data-pipeline.md) and [`adr/0014-star-guarantees.md`](adr/0014-star-guarantees.md). The feed's today changes at US Eastern midnight once no game of the previous day is live, as set in [`adr/0013-day-change.md`](adr/0013-day-change.md). The attempts for a final game's detail and highlights follow [`adr/0010-final-game-attempts.md`](adr/0010-final-game-attempts.md). A failed request does not use up a highlight attempt; the same attempt is retried no sooner than 10 minutes later, as set in [`adr/0018-highlight-request-failures.md`](adr/0018-highlight-request-failures.md). The highlights lookup reads the channel's uploads through the official video API, as set in [`adr/0015-highlights-source.md`](adr/0015-highlights-source.md). The stars job runs in its own task, as set in [`adr/0014-star-guarantees.md`](adr/0014-star-guarantees.md). Standings have no job yet, and no cadence is set for them.
- A job that fails keeps the last valid feed published. A partial or invalid feed is never written.
- Each job records its last successful run, so the backend can report its own health.

### Feeds

- One feed per domain, each a JSON file:
  - `games.json`: games for the days shown on the site, with scores, status and game details.
  - `standings.json`: standings tables.
  - `games/{id}.json`: one detail feed per game in the days shown, built on request (a final game's once, at its final time), drawn by the front end's `/game/{id}` route. Its route is set in [`adr/0020-source-rules.md`](adr/0020-source-rules.md), first set by ADR 0019; its refresh, retries and deletion follow [`adr/0020-source-rules.md`](adr/0020-source-rules.md).
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
- Svelte 5 runes only. Syntax from earlier Svelte versions is not used.
- The front end fetches feeds and polls them while the page is open. Polling pauses while the tab is hidden.
- Motion uses Svelte's built-in transitions and the Web Animations API. No animation library.
- Every user-facing string lives in the translation messages (`web/messages/en.json`, `web/messages/es.json`), compiled by Paraglide JS. English is the base; Spanish is shown when the browser prefers it. The language never appears in the URL. Dates and numbers are formatted with the browser's `Intl` for the active language.
- Recorded in [`adr/0004-web-tooling.md`](adr/0004-web-tooling.md) and [`adr/0006-translations.md`](adr/0006-translations.md).

## Performance

The site has to load and respond fast on a phone. These rules apply to every change:

- The front end's static files are served from a CDN.
- Feeds stay small and contain only what the page draws.
- Images are served at the size they are displayed and load only when they are about to be shown.
- Fonts load only the weights in use.
- No dependency is added to the front end without a reason recorded in its pull request.

## Seasonal sections

Sections such as All-Star or the Finals are temporary. Each one is self-contained: its own route or component, its own feed and its own job. Removing a section removes those pieces and touches nothing in the core.

## Configuration

- Configuration is read only through `Settings` in `api/app/settings.py`, from the environment and from `api/.env`.
- `.env` is never committed. `api/.env.example` lists every variable `Settings` reads.
- Data source URLs and keys live only in configuration, never in code or documentation.
- Recorded in [`adr/0003-api-tooling-and-configuration.md`](adr/0003-api-tooling-and-configuration.md).
- The front end's build-time settings are declared in `web/src/env.ts` and listed in `web/.env.example`: the games feed URL, the game detail feed URL (with an `{id}` placeholder) and the video platform's name.
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
api/app/feeds/             One module per feed model, plus schema.py, which exports the schemas
api/app/sources/           One module per data source adapter, plus http.py (shared client and SourceError) and teams.py (team codes)
api/app/jobs/              One module per job, plus scheduler.py (the in-process scheduler), on_demand.py (the on-demand feed cache), presence.py (rule B), game_detail_feed.py (the game detail feed kind), team_feed.py (the team feed builder) and player_feed.py (the player feed builder)
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

- **State retention**: each game's US Eastern date is stored with its job state; with the games job's daily fetch, the final time and stats attempts of games dated more than 30 days ago are deleted. Highlights and highlight attempts are never deleted; stars and job health keep one row per team and per job.

Recorded in [`adr/0012-hero-rotation.md`](adr/0012-hero-rotation.md):

- **Hero rotation**: the hero rotates through the games of the day that are not postponed or canceled; with none, it shows no game. Delayed games stay in the rotation.

Recorded in [`adr/0013-day-change.md`](adr/0013-day-change.md):

- **Day change**: the feed's today changes at US Eastern midnight; while any game of the previous day is live, the previous day stays today. The morning run refreshes the 7 days shown and never moves the window.

Recorded in [`adr/0014-star-guarantees.md`](adr/0014-star-guarantees.md):

- **Star guarantees**: every game shows both stars. The stars job runs in its own task and fetches all teams concurrently; the first games feed waits until every team has a star; a team with no roster player among its season leaders gets its star from individual averages; a failed team keeps its last known star.

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

## Future

- A notification panel for job failures.
