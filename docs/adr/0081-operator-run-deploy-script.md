# 0081. Operator-run deploy script

- Status: Accepted
- Date: 2026-10-27

## Context

ADR 0079 put production behind Vercel and said "The Vercel config and the deploy
script are not decided here". Issue #392 adds them. The choices touch `/web`'s
build, `/api`'s rollout, hosting and the workflow, and the code shows what is
done, not why CI deploys and Vercel's Git integration were turned down.

## Decision

- Deploys are run by the operator with `scripts/deploy.sh [api|web|all]`, from
  `main` equal to `origin/main` with a clean tree. Its settings live in
  `.env.deploy` (never committed).
- The api is updated over SSH with `git pull --ff-only` and
  `sudo docker compose up -d --build` in the machine's clone, then a bounded
  wait of 180 seconds for the api service to be healthy.
- The web is built locally with every feed URL injected at build time as
  `https://<site>/api/feeds/...` (never written to `web/.env`) and uploaded with
  `vercel deploy --prod` from a dedicated folder linked with `vercel link`. The
  folder is outside the repository, is not `/`, the home folder or a folder
  that contains the repository, and its contents are replaced except `.vercel`.
- In `all`, the api is deployed before the web.
- `deploy/vercel.json` uses `routes` with `env` expansion for `BACKEND_URL` and a
  `set` transform for `ORIGIN_SECRET`, next to `rewrites` to `200.html`.
- The run ends with a smoke check that `/` and `/api/health` on the site answer 200.

## Consequences

- CI deploys and Vercel's Git integration are ruled out for now: a deploy needs
  the operator's machine, its SSH access and its Vercel login.
- A wrong folder value could wipe a folder, so the script refuses the unsafe
  locations before it deletes anything.
- Moving to CI or Git integration later needs a new ADR that supersedes this one.
