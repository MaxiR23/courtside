import { MediaQuery } from 'svelte/reactivity';

// Mirrors --playoffs-bracket-break in tokens.css. CSS cannot use var() in a media condition.
export const BRACKET_BREAKPOINT_PX = 1180;
export const BRACKET_WIDE_QUERY = `(min-width: ${BRACKET_BREAKPOINT_PX}px)`;

/** Whether the seven-column map applies. Without matchMedia (server, tests) it is the map. */
export function bracketWideViewport(): { readonly current: boolean } {
	if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
		return { current: true };
	}
	return new MediaQuery(BRACKET_WIDE_QUERY);
}
