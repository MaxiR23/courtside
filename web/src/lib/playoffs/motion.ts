// Playoffs bracket motion on the Web Animations API: the level 2 games list fades in after the
// camera flight and the mobile series sheet slides up. Durations come from the design tokens.
import type { PlayParams } from '#lib/hero/motion.ts';

export const gamesFade: PlayParams = {
	keyframes: () => [{ opacity: 0 }, { opacity: 1 }],
	durationToken: '--playoffs-games-fade',
	delayToken: '--playoffs-games-fade-delay'
};

export const sheetSlide: PlayParams = {
	keyframes: () => [{ transform: 'translateY(100%)' }, { transform: 'none' }],
	durationToken: '--playoffs-sheet-duration'
};
