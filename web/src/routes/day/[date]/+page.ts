// /day/{date} is rendered in the browser from the fallback page: the dates are not known at
// build time (ADR 0042), as for the other routes with a param.
export const prerender = false;
export const ssr = false;
