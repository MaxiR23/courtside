// A note's page is rendered in the browser from the static host's fallback page, so the build
// holds no page for each note (docs/adr/0086-news-pages-in-the-web.md).
export const prerender = false;
export const ssr = false;
