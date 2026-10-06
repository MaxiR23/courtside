# Deploy

Runbook for the production setup recorded in
[`adr/0016-production-hosting.md`](adr/0016-production-hosting.md). All
domains below are placeholders.

## Requirements

- A virtual machine with Docker Engine and the Compose plugin. Enable the
  Docker service at boot, so `restart: unless-stopped` brings the stack back
  after a reboot.
- Ports 80 and 443 (TCP) and 443 (UDP) open.
- A DNS record of the API domain pointing to the machine. It must resolve
  before the first start, or the certificate request fails.
- Git.
- Node 24 and pnpm 12 where the front end is built.

## Deploy the backend

1. Clone the repository.
2. `cp api/.env.example api/.env` and fill in every variable. `CORS_ORIGINS`
   must list the front end origin, e.g. `["https://example.com"]`; without
   it the page shows "data unavailable" even though the API is up. Compose
   interpolates `$` in this file, so write a literal `$` as `$$`.
3. `cp .env.example .env` and set `API_DOMAIN`, e.g. `api.example.com`.
4. `docker compose up -d --build`
5. Check: `docker compose ps` shows the api service as `healthy`, and
   `curl https://api.example.com/health` answers 200. The health check proves
   the process answers, not that the feeds are fresh.

## Build and publish the front end

1. `cp web/.env.example web/.env`
2. Set `GAMES_FEED_URL=https://api.example.com/feeds/games.json` and
   `VIDEO_PLATFORM_NAME`.
3. `cd web && pnpm install --frozen-lockfile && pnpm run build`
4. Upload the contents of `web/build/` to the static host.

The settings are read at build time: changing them means rebuilding and
uploading again.

## Update

- Backend: `git pull`, then `docker compose up -d --build`. The `data` volume
  is kept. Never use `docker compose down -v`: it deletes the volumes.
- Front end: rebuild and upload.
- Images: change the pinned tag in `api/Dockerfile` or `compose.yaml` through
  a pull request.

## Move to another machine

1. On the old machine: `docker compose stop`.
2. Back up the volume:

   ```
   docker run --rm -v courtside_data:/data:ro -v "$PWD":/backup python:3.14.8-slim-bookworm tar czf /backup/courtside-data.tgz -C /data .
   ```

3. Copy `courtside-data.tgz`, `api/.env` and `.env` to the new machine, which
   meets the same Requirements.
4. Clone the repository there, put both `.env` files in place and restore:

   ```
   docker volume create courtside_data
   docker run --rm -v courtside_data:/data -v "$PWD":/backup python:3.14.8-slim-bookworm sh -c "tar xzf /backup/courtside-data.tgz -C /data && chown -R 10001:10001 /data"
   ```

5. `docker compose up -d --build`
6. Point the DNS record to the new machine. Certificates are issued again
   there.

## Logs

`docker compose logs -f api`
