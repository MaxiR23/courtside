// The full series page is rendered in the browser, like /playoffs. Prerender stays on from
// the root layout, so the build writes a browser-rendered shell, and docs/deploy.md sends
// /playoffs/series to the fallback page.
export const ssr = false;
