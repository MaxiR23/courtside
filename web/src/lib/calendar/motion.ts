// The mobile calendar sheet slides up on the Web Animations API, on its own token: a core
// component does not depend on a seasonal section's tokens.
import type { PlayParams } from '#lib/hero/motion.ts';

export const calendarSheetSlide: PlayParams = {
	keyframes: () => [{ transform: 'translateY(100%)' }, { transform: 'none' }],
	durationToken: '--past-sheet-duration'
};
