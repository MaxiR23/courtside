# Courtside

A dark-mode NBA daily scoreboard. One page, built to check tonight's games at a glance and dig into any of them with one click.

> Personal project. Not affiliated with the NBA.

## What it does

**Hero.** A rotating hero that goes through every game of the day. Each game shows its two stars as cutouts, 7 seconds each, then the next game starts.

**Schedule.** A 7-day strip with today in the middle and the list of games for the selected day. Each game card expands in place to show:

- **Line score** by quarter, overtime included.
- **Top performers**, one per team, with points, rebounds and assists.
- **Team stats**: FG%, 3P%, rebounds, assists and turnovers, compared side by side.
- **Official highlights**, embedded once the game is final.

Scheduled games show tip-off time, venue, broadcast and the players to watch. Live games update on their own while the page is open.

**Spoiler-free mode.** Optional. Final scores stay hidden until you expand the game.

## How it works

Everything is automated. A backend process collects the data on a schedule, validates it and publishes one JSON feed per domain: games, standings, and seasonal sections while they run. The front end only reads those feeds and draws them.

```
data sources  ->  backend jobs  ->  feeds (JSON)  ->  front end
```

## Stack

| Part | Technology |
|---|---|
| Front end | SvelteKit (Svelte 5), static build |
| Back end | Python 3.12, FastAPI, scheduled jobs in the same process |
| Data contract | Pydantic models as the source of truth, TypeScript types generated from them |
| Testing | Vitest with Testing Library for the front end, pytest for the back end |

Details are in [`docs/architecture.md`](docs/architecture.md), and the reasoning behind each decision is recorded in [`docs/adr/`](docs/adr/README.md).

## Repository layout

Planned structure. Folders appear as the project is built.

```
/web    SvelteKit app
/api    FastAPI app and data jobs
/docs   Architecture, workflow, testing and decision records
```

## Development

How issues, branches, reviews and merges work in this repo is described in [`docs/workflow.md`](docs/workflow.md). Testing conventions are in [`docs/testing.md`](docs/testing.md).

### Web (/web)

Setup, from the repository root. Requires Node 22 and pnpm:

```
cd web && pnpm install
```

Run the app:

```
cd web && pnpm run dev
```

Run all tests:

```
cd web && pnpm run test
```

Run one test file:

```
cd web && pnpm exec vitest run tests/routes/+page.test.ts
```

Run the gate:

```
scripts/gate.sh web
```

### API (/api)

Setup, from the repository root. Always use `python3.12`, never `python3`:

```
python3.12 -m venv api/.venv
api/.venv/bin/python -m pip install -r api/requirements-dev.txt
cp api/.env.example api/.env
```

Run the app:

```
cd api && .venv/bin/python -m uvicorn app.main:app --reload
```

Run all tests:

```
cd api && .venv/bin/python -m pytest
```

Run one test file:

```
cd api && .venv/bin/python -m pytest tests/test_settings.py
```

Run the gate:

```
scripts/gate.sh api
```

### Feed contract

Regenerating the contract requires the setup of both apps above. From the
repository root:

```
scripts/contract.sh
```

The gate fails while the committed schema or types are out of date.

### Continuous integration

Every pull request to `main` and every push to `main` runs two jobs,
`api` and `web`. Each one installs its app and runs `scripts/gate.sh`
for it. Both must pass before a pull request merges.

### Git hooks

Enable the local hooks once per clone, from the repository root:

```
git config core.hooksPath .githooks
```

Before a commit, the hooks run the fast gate (lint and format check) for
each app with staged changes (`scripts/gate.sh web fast`,
`scripts/gate.sh api fast`). Before a push, they run the full gate for
each app changed in the pushed commits.

## Status

In development.