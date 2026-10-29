/**
 * A page's feed source, built from its feed URL (docs/design.md, "Shared components"). Call it
 * inside `$derived` with a URL that is itself `$derived` from the route params, the query and the
 * templates: a new URL builds a new, empty source, and the `$effect` that started the old one stops
 * it in its cleanup. `build` gets the URL as a plain string, so its load closure reads no params.
 * A null URL (the season is not settled) gives null, the loading state; an undefined URL (no feed
 * URL configured) gives undefined, the unavailable state.
 */
export function feedSource<S>(
	url: string | null | undefined,
	build: (url: string) => S
): S | null | undefined {
	if (url === null || url === undefined) return url;
	return build(url);
}
