# 0004. Web tooling

- Status: Accepted
- Date: 2026-10-05

## Context

`/web` is being scaffolded and needs a build, lint, format, type checking
and a test setup before feature work starts.

## Decision

- Created with the official Svelte CLI (`sv create`) through pnpm.
- TypeScript in strict mode, with svelte-check for type checking.
- ESLint with `eslint-plugin-svelte` and Prettier with
  `prettier-plugin-svelte`.
- Vitest with `@testing-library/svelte` and its Vite plugin, in jsdom.
  Tests live in `web/tests/`, mirroring `web/src/`.
- `adapter-static` with the whole site prerendered.
- Node 22, declared in `web/package.json`.

## Consequences

- Tool configuration lives in the config files at the root of `web/`.
  With SvelteKit 3 the SvelteKit options, including the adapter, are set
  in `web/vite.config.ts`.
- The gate runs the tools through `scripts/gate.sh web`, which calls the
  scripts in `web/package.json`.
- TypeScript stays on the 6.0 line until the SvelteKit, svelte-check and
  typescript-eslint peer ranges accept 7. jsdom stays on the 29 line
  until the Node in use satisfies jsdom 30.
- The Vitest add-on of the CLI is not used because it scaffolds browser
  mode and colocated tests.
