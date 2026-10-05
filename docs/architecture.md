# Architecture

How Courtside is built and why. This document records decisions that are in force. Anything not decided yet is listed under [Open decisions](#open-decisions) and must not be assumed by any change.

## Principles

1. **Visitors never reach a data source.** The backend collects data on its own schedule and publishes ready-made feeds. The number of visits never changes how often a source is called.
2. **The front end only draws.** It reads published feeds and renders them. It holds no business rules about games, standings or players.
3. **One contract, defined once.** The shape of every feed is defined in backend code and generated for the front end. Nothing is redefined by hand on either side.
4. **Every input is validated.** Data coming from a source is validated before it is used. A feed is validated before it is published.
5. **Small core, removable extras.** The core is the scoreboard. Seasonal sections are self-contained and can be added or removed without touching the core.

## Stack

| Part | Technology |
|---|---|
| Front end | SvelteKit with Svelte 5, built as static files |
| Back end | Python 3.12 with FastAPI, with scheduled jobs running in the same process |
| Data contract | Pydantic models, exported as JSON Schema, with TypeScript types generated from it |
| Testing | Vitest with Testing Library for `/web`, pytest for `/api`. Conventions in [`testing.md`](testing.md) |

Exact versions of every dependency are pinned when the project is scaffolded.

## Data flow

```
data sources  ->  source adapters  ->  jobs  ->  feeds (JSON)  ->  front end
```

### Source adapters

- One adapter per data source. Each adapter is the only code that knows that source's URLs, formats and quirks.
- Every adapter returns validated Pydantic models. Raw source data never leaves the adapter.
- When a primary source fails or returns invalid data, the job falls back to a secondary source if one exists for that data.

### Jobs

- Jobs run on a schedule inside the backend process. Each job owns one kind of data and has its own refresh cadence: a live game changes every minute, standings do not.
- A job that fails keeps the last valid feed published. A partial or invalid feed is never written.
- Each job records its last successful run, so the backend can report its own health.

### Feeds

- One feed per domain, each a JSON file:
  - `games.json`: games for the days shown on the site, with scores, status and game details.
  - `standings.json`: standings tables.
  - Seasonal feeds, such as playoffs or All-Star, added only while their section exists.
- Each feed is validated against its model before publishing and written atomically, so a reader never sees a half-written file.
- Feeds are served with cache headers and sit behind a CDN.

## Data contract

- The Pydantic models in the backend are the single source of truth for every feed.
- A JSON Schema is exported from those models, and the front end's TypeScript types are generated from that schema.
- Generated types are never edited by hand. A contract change starts in the models and is regenerated.

## Front end

- A static SvelteKit build. No server-side rendering is required to view the site.
- Svelte 5 runes only. Syntax from earlier Svelte versions is not used.
- The front end fetches feeds and polls them while the page is open. Polling pauses while the tab is hidden.
- Motion uses Svelte's built-in transitions and the Web Animations API. No animation library.

## Performance

The site has to load and respond fast on a phone. These rules apply to every change:

- The site is served as static files from a CDN.
- Feeds stay small and contain only what the page draws.
- Images are served at the size they are displayed and load only when they are about to be shown.
- Fonts load only the weights in use.
- No dependency is added to the front end without a reason recorded in its pull request.

## Seasonal sections

Sections such as All-Star or the Finals are temporary. Each one is self-contained: its own route or component, its own feed and its own job. Removing a section removes those pieces and touches nothing in the core.

## Repository layout

```
/web    SvelteKit app
/api    FastAPI app, source adapters, jobs and feed models
/docs   Architecture, workflow and data documentation
```

The internal structure of `/web` and `/api` is defined when each is scaffolded and documented here at that point.

## Open decisions

These are not decided. A change that depends on one of them stops and asks.
When one is closed, it gets an ADR in [`adr/`](adr/README.md) and this
document is updated in the same change.

- **Hosting** for the front end and for the backend process. The backend must stay running for its jobs, so platforms that sleep on inactivity do not fit.
- **Storage** for job state between runs: a local database or files on disk.
- **Refresh cadences** for each job.
- **Star player selection**: the rule that picks each team's star shown in the hero.
- **Highlight matching**: how a final game is matched to its official highlight video.
- **Missing data**: what the page shows when a feed has no data for a day. Sample data is not an option in production.