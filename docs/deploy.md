# Deploy

Runbook for the production setup recorded in
[`adr/0079-production-behind-vercel-with-origin-secret.md`](adr/0079-production-behind-vercel-with-origin-secret.md),
on top of [`adr/0016-production-hosting.md`](adr/0016-production-hosting.md).
All domains below are placeholders.

## Requirements

### Production (no domain)

- A virtual machine with Docker Engine and the Compose plugin. Enable the
  Docker service at boot, so `restart: unless-stopped` brings the stack back
  after a reboot.
- A fixed public IP.
- Port 80 (TCP) open to everyone, port 22 open only to the owner's IP, and no
  other inbound port.
- Git.
- Node 24 and pnpm 12 where the front end is built.

### Alternative: a domain with a certificate

The same, with ports 80 and 443 (TCP) and 443 (UDP) open, and a DNS record of
the API domain pointing to the machine. It must resolve before the first
start, or the certificate request fails. The origin secret is still required,
so the domain must sit behind a front door that sends the `X-Origin-Secret`
header: a browser fetching feeds straight from `https://api.example.com` gets
403.

## Deploy the backend

1. Clone the repository.
2. `cp api/.env.example api/.env` and fill in every variable. `CORS_ORIGINS`
   must list the front end origin, e.g. `["https://example.com"]`; without
   it the page shows "data unavailable" even though the API is up. Compose
   interpolates `$` in this file, so write a literal `$` as `$$`.
3. `cp .env.example .env`, set `API_DOMAIN=:80` (the alternative: the domain,
   e.g. `api.example.com`) and set `ORIGIN_SECRET` to the output of
   `openssl rand -hex 32`, the same value as the Vercel project variable.
   Without it, `docker compose up` stops with `set ORIGIN_SECRET in .env at
   the repository root`.
4. `docker compose up -d --build`
5. Check: `docker compose ps` shows the api service as `healthy`, then run
   "Check the origin" below. The health check proves the process answers, not
   that the feeds are fresh.

### Vercel project variables

Both are for production:

- `BACKEND_URL`: the machine's address over HTTP, e.g. `http://vm.example.com`
  (the real value is the machine's public IP, set only in Vercel).
- `ORIGIN_SECRET`: equal to the value in the root `.env`.

The Vercel config that uses them comes in a later change.

### Check the origin

The gate cannot run Caddy, so this is the check of the proxy behavior.
`vm.example.com` stands for the machine's public IP. The secret is read from
`.env` and is never typed or printed. `/health` is too small to be compressed
(Caddy skips bodies under 512 bytes), so compression is checked on a feed.

```
# From any other machine: no header, then a wrong one. Both print 403.
curl -s -o /dev/null -w '%{http_code}\n' http://vm.example.com/health
curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Origin-Secret: wrong' http://vm.example.com/health

# On the machine, from the repository root: the right header prints 200,
# and a feed comes back compressed (Content-Encoding: gzip).
secret="$(grep '^ORIGIN_SECRET=' .env | cut -d= -f2-)"
curl -s -o /dev/null -w '%{http_code}\n' -H "X-Origin-Secret: $secret" http://127.0.0.1/health
curl -s -o /dev/null -D - -H "X-Origin-Secret: $secret" -H 'Accept-Encoding: gzip' http://127.0.0.1/feeds/games.json | grep -i '^content-encoding'

# Rule K: the ETag survives compression. The repeat request with the
# received ETag prints 304.
etag="$(curl -s -o /dev/null -D - -H "X-Origin-Secret: $secret" -H 'Accept-Encoding: gzip' http://127.0.0.1/feeds/games.json | grep -i '^etag:' | cut -d' ' -f2- | tr -d '\r')"
curl -s -o /dev/null -w '%{http_code}\n' -H "X-Origin-Secret: $secret" -H 'Accept-Encoding: gzip' -H "If-None-Match: $etag" http://127.0.0.1/feeds/games.json
```

The same commands work on any machine running the stack with `API_DOMAIN=:80`,
using `http://127.0.0.1` for both halves.

## Build and publish the front end

1. `cp web/.env.example web/.env`
2. Set `GAMES_FEED_URL=https://api.example.com/feeds/games.json`,
   `STANDINGS_FEED_URL=https://api.example.com/feeds/standings.json`,
   `SEARCH_FEED_URL=https://api.example.com/feeds/search.json`,
   `CUP_FEED_URL=https://api.example.com/feeds/cup.json`,
   `CUP_MATCHUP_FEED_URL=https://api.example.com/feeds/cup/matchups/{id}.json`,
   `PLAYOFFS_FEED_URL=https://api.example.com/feeds/playoffs.json`,
   `PLAYOFFS_FINALS_FEED_URL=https://api.example.com/feeds/playoffs/finals.json`,
   `ALL_STAR_FEED_URL=https://api.example.com/feeds/all-star.json`,
   `HOME_FEED_URL=https://api.example.com/feeds/home.json`,
   `POWER_RANKING_FEED_URL=https://api.example.com/feeds/power-ranking.json`,
   `GAME_DETAIL_FEED_URL=https://api.example.com/feeds/games/{id}.json`,
   `TEAM_FEED_URL=https://api.example.com/feeds/teams/{code}.json`,
   `PLAYER_FEED_URL=https://api.example.com/feeds/players/{id}.json`,
   `CALENDAR_FEED_URL=https://api.example.com/feeds/seasons/{season}/calendar.json`,
   `DAY_FEED_URL=https://api.example.com/feeds/days/{date}.json`,
   `SEASON_STANDINGS_FEED_URL=https://api.example.com/feeds/seasons/{season}/standings.json`,
   `SEASON_TEAM_FEED_URL=https://api.example.com/feeds/seasons/{season}/teams/{code}.json`,
   `SEASON_PLAYER_FEED_URL=https://api.example.com/feeds/seasons/{season}/players/{id}.json`,
   `SEASON_CUP_FEED_URL=https://api.example.com/feeds/seasons/{season}/cup.json`,
   `SEASON_CUP_MATCHUP_FEED_URL=https://api.example.com/feeds/seasons/{season}/cup/matchups/{slot}.json`,
   `SEASON_PLAYOFFS_FEED_URL=https://api.example.com/feeds/seasons/{season}/playoffs.json`,
   `SEASON_PLAYOFFS_FINALS_FEED_URL=https://api.example.com/feeds/seasons/{season}/playoffs/finals.json`,
   `SEASON_ALL_STAR_FEED_URL=https://api.example.com/feeds/seasons/{season}/all-star.json` and
   `VIDEO_PLATFORM_NAME`.

   The URLs above are placeholders. The browser fetches feeds, so they must
   point at the front door that adds `X-Origin-Secret`, never at the machine
   or `api.example.com` directly, which answer 403. In production that front
   door is the Vercel site's forwarded paths, `https://<site>/api/feeds/...`
   (for example `https://www.example.com/api/feeds/games.json`), which the
   later Vercel config change defines. Until that change lands, a production
   front end cannot reach the API.
3. `cd web && pnpm install --frozen-lockfile && pnpm run build`
4. Upload the contents of `web/build/` to the static host (Vercel in production). Configure the static
   host to serve `200.html` for `/standings`, `/cup`, `/playoffs`, `/playoffs/series`, `/all-star`, `/all-star/previous` and for every `/day/*`, `/game/*`, `/player/*` and `/team/*` path that is not a file (those pages
   are rendered in the browser from it, ADR 0020 and ADR 0021).

The settings are read at build time: changing them means rebuilding and
uploading again.

## Update

- Backend: `git pull`, then `docker compose up -d --build`. The `data` volume
  is kept. Never use `docker compose down -v`: it deletes the volumes.
- Front end: rebuild and upload.
- Images: change the pinned tag in `api/Dockerfile` or `compose.yaml` through
  a pull request.

### Upgrade note: hardening settings

The deployed `api/.env` changes with this upgrade (see `api/.env.example`):

- Drop `HIGHLIGHTS_BACKFILL_PAGES`. It is still accepted and ignored, with a warning that does not show its value.
- Add `HIGHLIGHTS_SEARCH_API_URL`, the URL of the highlights search source. Set its value on the server only.
- Add `HIGHLIGHTS_SEARCH_DAILY_CAP`, the searches per US Eastern day. Its default is 80; leave it unset to keep it.

Without `HIGHLIGHTS_SEARCH_API_URL` no on-demand highlights search runs.

### Upgrade note: visitor rate limit

`RATE_LIMIT_PER_MINUTE` in `api/.env` is optional. Its default is 120 feed requests per visitor per minute, and 0 turns the limit off. The visitor is read from `x-real-ip`, which Vercel sends; a request without it is keyed on its connection address, which behind Caddy is the proxy's. Every visitor then shares one limit and the polled pages get 429. The front door must forward `x-real-ip` to the API; if it does not (check after the Vercel config lands), set `RATE_LIMIT_PER_MINUTE=0`.

## Change to a feed's shape

When a change alters the shape of a feed, deploy first the side that accepts
both the old and the new shape, then the other one right after. Each pull
request that changes a feed's shape names which side goes first.

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
6. Point the DNS record (alternative) or `BACKEND_URL` in Vercel (production)
   to the new machine. Certificates are issued again there in the alternative.

## CDN in front of the API

Rule K of [`source-rules.md`](source-rules.md), adopted by
[`adr/0020-source-rules.md`](adr/0020-source-rules.md): feed responses keep
`Cache-Control: public, max-age=10` and the ETag. The CDN in front of the API
must honor the origin's Cache-Control, must not add `s-maxage` and must keep
"Always Online" off. Reference: Cloudflare's Origin Cache Control
documentation, where `s-maxage` disables `stale-while-revalidate` and "Always
Online" ignores it.

In production, the layer in front of the API is the Vercel site
([`adr/0079`](adr/0079-production-behind-vercel-with-origin-secret.md)). Any CDN or front door in
front of the machine must send `X-Origin-Secret`, or every request gets 403.
The rule K requirements above apply to whatever layer is in front.

## Logs

`docker compose logs -f api`
