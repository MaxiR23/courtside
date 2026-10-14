// The live dot's pulse on the Web Animations API, in the shape of the skeleton shimmer.
// Values come from the --allstar-live-dot-* tokens; `play` skips it under reduced motion.
// SEE: docs/design-all-star.md, Interactions and motion
import type { PlayParams } from '#lib/hero/motion.ts';

export const livePulse: PlayParams = {
	keyframes: (read) => [
		{ opacity: 1, transform: 'scale(1)' },
		{
			opacity: read('--allstar-live-dot-opacity'),
			transform: `scale(${read('--allstar-live-dot-scale')})`
		},
		{ opacity: 1, transform: 'scale(1)' }
	],
	durationToken: '--allstar-live-dot-duration',
	easing: 'ease-in-out',
	iterations: Infinity
};
