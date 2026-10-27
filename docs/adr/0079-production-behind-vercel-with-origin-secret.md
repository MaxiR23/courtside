# 0079. Production behind Vercel with an origin secret

- Status: Accepted
- Date: 2026-10-27

## Context
ADR 0016 assumed the API had its own domain with certificates obtained by
Caddy, and a provider-neutral static host. The production setup has no
domain, and the browser must only talk to the front end site over HTTPS.
Raised in #386.

## Decision
- One EC2 virtual machine runs `compose.yaml` with Docker Compose, with a
  fixed public IP and no domain. `API_DOMAIN=:80`, so Caddy serves plain HTTP
  on port 80 and requests no certificate.
- Port 22 is open only to the owner's IP; port 80 is open to everyone.
- The static build is hosted on Vercel. The browser talks only to the Vercel
  site over HTTPS. Vercel forwards `/api/*` to the machine over HTTP (project
  variable `BACKEND_URL`) and serves `200.html` for the browser-rendered
  paths.
- Origin secret: Caddy answers 403, before the API, to any request whose
  `X-Origin-Secret` header is not equal to `ORIGIN_SECRET` from the root
  `.env`. Vercel sends it from its project variable of the same name. Compose
  refuses to start without it.
- Caddy compresses responses with `encode zstd gzip`.
- The domain-with-certificate setup (`API_DOMAIN` set to a domain) stays as
  the alternative. It still requires the origin secret.
- This ADR replaces ADR 0016 for the machine, the certificates and the front
  end host only.

## Consequences
- ADR 0016 keeps the API image, the single worker, the health check, the
  volumes, the restart policy and the pinned images. Its status line is the
  only edit it gets.
- It refines the "Hosting" of ADR 0007 without superseding it: a reverse
  proxy is still in front of the API, and HTTPS reaches the browser through
  Vercel. ADR 0007 is not edited.
- A direct request to the machine gets 403, so the machine is not a public
  API. The browser can no longer fetch feeds straight from it.
- The hop from Vercel to the machine is plain HTTP, so the secret travels
  unencrypted on it. Rotating it means changing both values and restarting
  the proxy.
- The health check runs inside the api container and never goes through
  Caddy.
- The Vercel config and the deploy script are not decided here.
- The steps live in `docs/deploy.md`.
