# 0003. API tooling and configuration

- Status: Accepted
- Date: 2026-10-05

## Context

`/api` is being scaffolded and needs lint, format, type checking and a
configuration mechanism before feature work starts.

## Decision

- ruff for lint and format.
- mypy in strict mode over `app` and `tests`.
- The `app` package follows FastAPI's "Bigger Applications" layout.
- Configuration only through one pydantic-settings `Settings` class, read
  from the environment and from `api/.env`, loaded once through
  `get_settings()`. `.env` is never committed.
- `api/.env.example` lists every variable `Settings` reads, with no real
  values.
- Data source URLs and keys live only in configuration, never in code or
  documentation.

## Consequences

- Tool configuration lives in `api/pyproject.toml`, which holds no
  packaging metadata.
- The gate runs the tools through `scripts/gate.sh api`.
- No module reads environment variables directly.
- A new setting adds a field to `Settings` and a line to `.env.example`.
- `httpx` is installed only for FastAPI's test client. The HTTP client for
  source adapters, and its mocking tool, are still undecided. They are
  chosen with the first source adapter, which defers the timing stated in
  ADR 0001.
