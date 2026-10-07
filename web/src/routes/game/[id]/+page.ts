// A game's page is rendered in the browser from the static host's fallback page, so the build
// holds no page for each game (docs/adr/0019-game-detail-route-and-feed.md).
export const prerender = false;
export const ssr = false;
