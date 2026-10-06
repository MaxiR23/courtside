# 0017. Runtime versions

- Status: Accepted
- Date: 2026-10-06

## Context

The project was scaffolded on Python 3.12, Node 22 and pnpm 10. Both
runtimes and pnpm have newer stable lines, and several dependencies had
new majors. Raised in #93.

## Decision

- `/api` runs on Python 3.14: the virtual environment, the api gate, CI
  and the production image (`python:3.14.8-slim-bookworm`, exact tag).
- `/web` runs on Node 24, the current LTS line, declared in
  `web/package.json`. pnpm is 12, pinned exactly in CI. Its settings live
  in `web/pnpm-workspace.yaml`, because pnpm 11 and later read only auth
  and registry settings from `.npmrc`.
- Every dependency in both apps is on its latest stable version, pinned
  exactly. Major versions are adopted and the code they break is migrated.
- Two exceptions follow from the rest of the toolchain, not from a
  migration: `typescript` stays on 6.x, because TypeScript 7 ships no
  JavaScript API and SvelteKit, svelte-check and typescript-eslint
  require 6; `@types/node` follows the Node major in use. A transitive
  package that its parent pins exactly, such as `pydantic_core`, takes
  that version.

## Consequences

- Refines the "Node 22" and the TypeScript and jsdom holds of ADR 0004
  without superseding it as a whole. ADR 0004 is not edited. jsdom is on
  30.
- A local `api/.venv` on another Python version fails the api gate until
  it is recreated with `python3.14`.
- TypeScript 7 is adopted when the peer ranges of SvelteKit, svelte-check
  and typescript-eslint accept it.
- The next upgrade writes a new ADR and leaves this one unedited.
