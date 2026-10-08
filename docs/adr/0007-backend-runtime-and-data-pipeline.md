# 0007. Backend runtime and data pipeline

- Status: Superseded by 0020 for its refresh cadences only
- Date: 2026-10-05

## Context

The backend must stay running for its jobs, cost nothing and be easy to
move. Before any backend issue is built, the hosting, runtime, cadences
and matching rules need to be written down. Data sources are described
generically: adapters own their URLs and formats.

## Decision

### Hosting

- One always-free virtual machine, never upgraded to a paid account.
- Everything runs with Docker Compose and is configured through `.env`.
- No provider-specific service is used. Moving to another server means
  copying the `.env` and the data volume and running one command.
- HTTPS comes from a reverse proxy that obtains and renews free
  certificates automatically, behind a free subdomain pointing to the
  machine.

### Runtime

- The scheduler runs inside the FastAPI process.
- The HTTP client is httpx, mocked in tests with respx.
- Job state lives in one SQLite file on the data volume.
- Feeds stay JSON files, validated and written atomically.

### Day boundary

A day is the date in US Eastern time, as the league's schedule defines it.

### Cadences

- Once a day, in the morning US Eastern time: the schedule for the 7 days
  shown and each team's star.
- From a game's scheduled start: every minute until it is live. A delayed
  game keeps being checked.
- While a game is live: every 30 seconds.
- When a game is final: its final time is stored and it is no longer
  checked.
- Postponed and canceled games are no longer checked.
- Highlights: one attempt 1 hour, 2 hours and 3 hours after the final
  time, then no more.

### Stars

Each team's star is the player on the current roster with the highest
points plus rebounds plus assists per game. Current season statistics are
used once they exist for the team. Until then, the previous regular
season's statistics are used, filtered by the current roster.

### Hero

There is no single featured game. The hero rotates through every game of
the day, so the feed carries the stars of every game.

### Highlights

- Only the league's official video channel is used, through its public
  feed.
- A video matches a game by both teams, the highlights label and the date
  in its title.
- After the third failed attempt, the game shows the pending state.

### Game statuses

Scheduled, live and final, plus delayed, postponed and canceled.

### Failures

Every job failure is logged with its reason, and the health endpoint
reports each job's last successful run.

### Front end polling

Every 30 seconds while any game is live, every 60 seconds otherwise.
Polling is paused while the tab is hidden and refreshes as soon as the tab
is visible again.

## Consequences

- The host is replaceable: nothing depends on a provider's services.
- A single process holds the scheduler, so a restart resumes from the
  SQLite state.
- Highlights that never match stay pending after three attempts.
- The design for the rotating hero is a separate change.
- A notification panel for job failures is listed under "Future" in
  `docs/architecture.md`.
