# 0001. Testing tools

- Status: Accepted
- Date: 2026-10-04

## Context

Every change that adds or changes behavior ships with its tests, so both
apps need a test runner before any feature work starts. The front end is a
SvelteKit app with Svelte 5. The back end is a FastAPI app in Python.

## Decision

- `/web`: Vitest as the runner, with `@testing-library/svelte` for
  components.
- `/api`: pytest as the runner.

## Consequences

- Conventions for both apps live in `docs/testing.md`.
- Component tests run in jsdom, so layout and animation are not asserted
  there.
- The HTTP mocking tool for `/api` is not decided here. It is chosen with
  the HTTP client when `/api` is scaffolded.