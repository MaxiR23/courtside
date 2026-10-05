import { play, type PlayParams } from '#lib/hero/motion.ts';

export const listEntrance = (index: number): PlayParams => ({
	keyframes: (read) => [
		{ opacity: 0, transform: `translateY(${read('--list-entrance-offset')})` },
		{ opacity: 1, transform: 'none' }
	],
	durationToken: '--list-entrance-duration',
	delayToken: '--list-entrance-stagger',
	delaySteps: index
});

/** Plays the staggered entrance on mount, but only once the list has had an entrance run. */
export function cardEntrance(node: HTMLElement, params: { index: number; run: number }) {
	if (params.run === 0) return;
	return play(node, listEntrance(params.index));
}
