import { MediaQuery } from 'svelte/reactivity';

// Mirrors --game-row-breakpoint in tokens.css. CSS cannot use var() in a media condition.
export const GAME_ROW_BREAKPOINT_PX = 680;
export const WIDE_QUERY = `(min-width: ${GAME_ROW_BREAKPOINT_PX}px)`;

/** Whether the desktop row applies. Without matchMedia (server, tests) it is the desktop row. */
export function wideViewport(): { readonly current: boolean } {
	if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
		return { current: true };
	}
	return new MediaQuery(WIDE_QUERY);
}
