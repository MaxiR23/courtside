// Playoffs bracket motion on the Web Animations API: the phone series sheet slides up.
// The duration comes from the design tokens.
import type { PlayParams } from '#lib/hero/motion.ts';

export const sheetSlide: PlayParams = {
	keyframes: () => [{ transform: 'translateY(100%)' }, { transform: 'none' }],
	durationToken: '--playoffs-sheet-duration'
};
