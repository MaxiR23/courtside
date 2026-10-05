# Courtside

A dark-mode NBA daily scoreboard. One page, built to check tonight's games at a glance and dig into any of them with one click.

> Personal project. Not affiliated with the NBA.

## What it does

**Hero.** Tonight's featured game, with each team's star player shown as a cutout. The two players alternate every 7 seconds.

**Schedule.** A 7-day strip with today in the middle and the list of games for the selected day. Each game card expands in place to show:

- **Line score** by quarter, overtime included.
- **Top performers**, one per team, with points, rebounds and assists.
- **Team stats**: FG%, 3P%, rebounds, assists and turnovers, compared side by side.
- **Official highlights**, embedded once the game is final.

Scheduled games show tip-off time, venue, broadcast and the players to watch. Live games update on their own while the page is open.

**Spoiler-free mode.** Optional. Final scores stay hidden until you expand the game.

## How it works

Everything is automated. A backend process collects the game data on a schedule, validates it and publishes a single JSON feed. The front end only reads that feed and draws it.

```
data sources  ->  backend jobs  ->  games.json  ->  front end
```

## Stack

| Part | Technology |
|---|---|
| Front end | SvelteKit (Svelte 5), static build |
| Back end | Python 3.12, FastAPI, scheduled jobs in the same process |
| Data contract | Pydantic models as the source of truth, TypeScript types generated from them |

Details and the reasoning behind each choice are in [`docs/architecture.md`](docs/architecture.md).

## Repository layout

Planned structure. Folders appear as the project is built.

```
/web    SvelteKit app
/api    FastAPI app and data jobs
/docs   Architecture, workflow and data documentation
```

## Development

How issues, branches, reviews and merges work in this repo is described in [`docs/workflow.md`](docs/workflow.md).

## Status

In development.