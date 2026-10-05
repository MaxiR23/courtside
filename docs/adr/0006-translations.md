# 0006. Translations

- Status: Accepted
- Date: 2026-10-05

## Context

Every user-facing string must be translatable, in English and Spanish. The
site is a static build and the language must not appear in the URL.

## Decision

- The official Svelte CLI add-on `paraglide` (Paraglide JS, pinned to an
  exact version).
- The inlang plugins (`@inlang/plugin-message-format`,
  `@inlang/plugin-m-function-matcher`) are devDependencies pinned to
  exact versions and loaded from `web/node_modules`, not from a CDN.
- English is the base language, Spanish the second.
- The locale comes from the browser preference (`preferredLanguage`, then
  `baseLocale`), with no language in the URL, no cookie and no stored
  choice.
- Messages live in `web/messages/{locale}.json` and compile to
  `#lib/paraglide`, which is generated and gitignored.
- Dates and numbers use the browser's `Intl` with the active locale,
  through `#lib/format/locale.ts`.

## Consequences

- Prerendered HTML is English. Spanish replaces it on the client at
  hydration, so a Spanish browser may briefly show English first.
- The add-on's reroute hook and hidden locale links are removed, because
  they put the language in the URL.
- `pnpm run check` compiles the messages first, so a fresh checkout passes
  svelte-check.
- Compiling needs no network beyond `pnpm install`. Upgrading a plugin
  is a dependency bump, and `web/tests/inlang-plugins-are-local.test.ts`
  fails if a plugin is loaded from a URL again.
- The strategy is declared twice: in `web/vite.config.ts` and in the
  `check` script flags. Changing it means changing both.
- A manual language switcher or localized URLs would need a new ADR.
