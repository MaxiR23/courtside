# 0016. Production hosting

- Status: Accepted
- Date: 2026-10-06

## Context
ADR 0007 decides the hosting in principle: an always-free virtual machine
that is never upgraded, Docker Compose, `.env`, and a reverse proxy with
automatic certificates. It does not set the concrete setup. Raised in #83.

## Decision
- The backend runs on one always-on virtual machine on a free plan, never
  upgraded, with Docker Compose from `compose.yaml` at the repository root.
- The API image is built from `api/Dockerfile`. It runs as a non-root user,
  with one uvicorn process because the scheduler is in-process, and a health
  check on `/health`.
- Caddy is the reverse proxy. It obtains and renews certificates for
  `API_DOMAIN`, read from the root `.env`, because `api/.env` only holds the
  variables `Settings` reads.
- The job state and the feeds live on the named volume `data`, mounted at
  `/data`. Certificates live on their own volume.
- Both services restart unless stopped.
- The front end is built as static files with its build-time settings and
  uploaded to a static hosting service with a CDN. No provider-specific
  service is used.
- Images are pinned to exact version tags.

## Consequences
- Refines the "Hosting" of ADR 0007 without superseding it as a whole.
  ADR 0007 is not edited.
- Moving means copying both `.env` files and the `data` volume, then running
  `docker compose up -d --build`.
- A second API worker is ruled out while the scheduler runs in-process.
- The health check proves the process answers, not that the feeds are fresh.
- The steps live in `docs/deploy.md`.
