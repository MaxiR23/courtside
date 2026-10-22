// The mobile menu sheet slides up on the Web Animations API, on its own token: the nav is a core
// component and does not read another section's tokens.
import type { PlayParams } from '#lib/hero/motion.ts';

export const navSheetSlide: PlayParams = {
	keyframes: () => [{ transform: 'translateY(100%)' }, { transform: 'none' }],
	durationToken: '--nav-sheet-duration'
};
