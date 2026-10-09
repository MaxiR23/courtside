// The standings page is rendered in the browser, like every other page's nav
// (docs/design-standings-search.md). Prerender stays on from the root layout, so the
// build writes a browser-rendered shell, and docs/deploy.md sends /standings to the
// fallback page.
export const ssr = false;
