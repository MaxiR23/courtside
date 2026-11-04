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
- On the operator's machine, to run `scripts/deploy.sh`: the Vercel CLI (`pnpm add -g vercel`, then
  `vercel login`), `ssh` and `curl`.

### Alternative: a domain with a certificate

The same, with ports 80 and 443 (TCP) and 443 (UDP) open, and a DNS record of
the API domain pointing to the machine. It must resolve before the first
start, or the certificate request fails. The origin secret is still required,
so the domain must sit behind a front door that sends the `X-Origin-Secret`
header: a browser fetching feeds straight from `https://api.example.com` gets
403.

## Deploy the backend

1. Clone the repository.
2. `cp api/.env.example api/.env` and fill in every variable. In production
   the browser fetches feeds from the Vercel site's own origin
   (`https://<site>/api/feeds/...`), so the request is not cross-origin and
   `CORS_ORIGINS` can stay `[]`. List an origin, e.g. `["https://example.com"]`,
   only for a front end served from another origin that reads the API through
   a front door adding the secret. Compose interpolates `$` in this file, so
   write a literal `$` as `$$`.
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

`deploy/vercel.json` uses them: it forwards `/api/*` to `BACKEND_URL` and sets
`x-origin-secret` from `ORIGIN_SECRET`, replacing any value the visitor sent.

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

## Deploy with the script

`scripts/deploy.sh` deploys the backend over SSH and the front end to Vercel
from the operator's machine.

### One-time setup

1. An SSH alias in `~/.ssh/config`:

   ```
   Host courtside-vm
     HostName vm.example.com
     User <user>
     IdentityFile <path to the key>
   ```

   The alias user needs passwordless `sudo`, because the script runs
   `sudo docker compose` without a terminal.
2. `cp .env.deploy.example .env.deploy` and fill in the four keys
   (`DEPLOY_VERCEL_PROJECT_ID` after step 3). The file is
   ignored by git, and the script never prints its values. `DEPLOY_SSH_HOST`
   takes the alias from step 1 (or a hostname): only letters, digits, dots,
   hyphens and underscores, not starting with `-`. Any other value, such as
   `user@host`, a value with a space or `=`, or an ssh option, stops the deploy
   before any ssh call with a message that names the key and not the value.
3. A folder dedicated to the deploy, e.g.
   `mkdir ~/courtside-vercel && cd ~/courtside-vercel && vercel link`. Its
   absolute path goes in `DEPLOY_VERCEL_DIR`. It must not be `/`, the home
   folder, a folder inside the repository or a folder that contains the
   repository. The script replaces everything in it except `.vercel`. Then copy
   the `projectId` value of `.vercel/project.json` in that folder into
   `DEPLOY_VERCEL_PROJECT_ID`. In `web` and `all` modes the script reads that
   `projectId` and stops before the build, naming the keys and not the values,
   when `DEPLOY_VERCEL_PROJECT_ID` is missing, when the file has no `projectId`
   or when the two differ, so a folder linked to another Vercel project is
   never deployed. `api` mode does not need the key.
4. In the Vercel project, the production variables `BACKEND_URL` and
   `ORIGIN_SECRET` (see "Vercel project variables").
5. The machine has the clone at `~/courtside` and was set up per "Deploy the
   backend".

### Daily use

- `scripts/deploy.sh` deploys both sides, api first. `scripts/deploy.sh api`
  and `scripts/deploy.sh web` deploy one side.
- It runs only from `main`, with a clean tree and `main` equal to
  `origin/main`, and records that commit.
- api fetches on the machine and fast-forwards its clone to exactly that
  commit. It stops before the rebuild when the move is not a fast-forward or
  the machine's HEAD is not that commit, naming both hashes. Then it rebuilds
  and waits up to 180 s for the `api` service to be healthy. A merge to `main`
  that lands during a deploy is not picked up: run the script again to ship it.
- web checks that the linked folder's `projectId` equals
  `DEPLOY_VERCEL_PROJECT_ID`, then builds with every feed URL set to `DEPLOY_SITE_URL/api/feeds/...`,
  without touching `web/.env`, which still provides `VIDEO_PLATFORM_NAME`. It
  then publishes with `vercel deploy --prod`.
- It ends by checking that `/` and `/api/health` on the site answer 200.

## Build and publish the front end

1. `cp web/.env.example web/.env`
2. Set `GAMES_FEED_URL=https://www.example.com/api/feeds/games.json`,
   `STANDINGS_FEED_URL=https://www.example.com/api/feeds/standings.json`,
   `SEARCH_FEED_URL=https://www.example.com/api/feeds/search.json`,
   `CUP_FEED_URL=https://www.example.com/api/feeds/cup.json`,
   `CUP_MATCHUP_FEED_URL=https://www.example.com/api/feeds/cup/matchups/{id}.json`,
   `PLAYOFFS_FEED_URL=https://www.example.com/api/feeds/playoffs.json`,
   `PLAYOFFS_FINALS_FEED_URL=https://www.example.com/api/feeds/playoffs/finals.json`,
   `ALL_STAR_FEED_URL=https://www.example.com/api/feeds/all-star.json`,
   `HOME_FEED_URL=https://www.example.com/api/feeds/home.json`,
   `POWER_RANKING_FEED_URL=https://www.example.com/api/feeds/power-ranking.json`,
   `GAME_DETAIL_FEED_URL=https://www.example.com/api/feeds/games/{id}.json`,
   `TEAM_FEED_URL=https://www.example.com/api/feeds/teams/{code}.json`,
   `PLAYER_FEED_URL=https://www.example.com/api/feeds/players/{id}.json`,
   `CALENDAR_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/calendar.json`,
   `DAY_FEED_URL=https://www.example.com/api/feeds/days/{date}.json`,
   `SEASON_STANDINGS_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/standings.json`,
   `SEASON_TEAM_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/teams/{code}.json`,
   `SEASON_PLAYER_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/players/{id}.json`,
   `SEASON_CUP_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/cup.json`,
   `SEASON_CUP_MATCHUP_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/cup/matchups/{slot}.json`,
   `SEASON_PLAYOFFS_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/playoffs.json`,
   `SEASON_PLAYOFFS_FINALS_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/playoffs/finals.json`,
   `SEASON_ALL_STAR_FEED_URL=https://www.example.com/api/feeds/seasons/{season}/all-star.json` and
   `VIDEO_PLATFORM_NAME`.

   The URLs must point at the Vercel site's forwarded paths,
   `https://<site>/api/feeds/...`, never at the machine, which answers 403.
   `scripts/deploy.sh` sets them for the build.
3. `cd web && pnpm install --frozen-lockfile && pnpm run build`
4. Upload the contents of `web/build/` together with `deploy/vercel.json` (the
   Vercel CLI from the linked folder, as `scripts/deploy.sh` does).

### Browser-rendered paths

`deploy/vercel.json` serves `200.html` for these paths when they are not a file (ADR 0020 and ADR 0021):

- `/standings`
- `/cup`
- `/playoffs`
- `/playoffs/series`
- `/all-star`
- `/all-star/previous`
- `/day/*`
- `/game/*`
- `/player/*`
- `/team/*`

The settings are read at build time: changing them means rebuilding and
uploading again.

## Update

- Backend: `scripts/deploy.sh api` (or by hand on the machine: `git pull`,
  then `docker compose up -d --build`). The `data` volume
  is kept. Never use `docker compose down -v`: it deletes the volumes.
- Front end: `scripts/deploy.sh web`.
- Images: change the pinned tag in `api/Dockerfile` or `compose.yaml` through
  a pull request.

### Upgrade note: hardening settings

The deployed `api/.env` changes with this upgrade (see `api/.env.example`):

- Drop `HIGHLIGHTS_BACKFILL_PAGES`. It is still accepted and ignored, with a warning that does not show its value.
- Add `HIGHLIGHTS_SEARCH_API_URL`, the URL of the highlights search source. Set its value on the server only.
- Add `HIGHLIGHTS_SEARCH_DAILY_CAP`, the searches per US Eastern day. Its default is 80; leave it unset to keep it.

Without `HIGHLIGHTS_SEARCH_API_URL` no on-demand highlights search runs.

### Upgrade note: visitor rate limit

`RATE_LIMIT_PER_MINUTE` in `api/.env` is optional. Its default is 120 feed requests per visitor per minute, and 0 turns the limit off. The visitor is read from `x-real-ip`, which Vercel sends; a request without it is keyed on its connection address, which behind Caddy is the proxy's. Every visitor then shares one limit and the polled pages get 429. The front door must forward `x-real-ip` to the API; if it does not (check after the first deploy with `deploy/vercel.json`), set `RATE_LIMIT_PER_MINUTE=0`.

## Change to a feed's shape

When a change alters the shape of a feed, deploy first the side that accepts
both the old and the new shape, then the other one right after. Each pull
request that changes a feed's shape names which side goes first. With the
script, deploy the side that goes first with `scripts/deploy.sh api` or
`scripts/deploy.sh web`, then the other.

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
