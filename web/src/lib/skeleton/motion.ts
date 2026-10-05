// The skeletons' motion on the Web Animations API, in the same shape as the hero's.
import type { PlayParams } from '#lib/hero/motion.ts';

/** The skeletons' subtle shimmer: a slow opacity loop. `play` skips it with reduced motion. */
export const shimmer: PlayParams = {
	keyframes: (read) => [
		{ opacity: 1 },
		{ opacity: read('--skeleton-shimmer-opacity') },
		{ opacity: 1 }
	],
	durationToken: '--skeleton-shimmer-duration',
	easing: 'ease-in-out',
	iterations: Infinity
};
