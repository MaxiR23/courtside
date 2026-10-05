import { play, type CrossfadeParams, type PlayParams } from '#lib/hero/motion.ts';

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

/** Grows the panel's row track from nothing to its content height. */
export const panelExpand = (open: boolean): CrossfadeParams => ({
	active: open,
	hidden: () => ({ gridTemplateRows: '0fr' }),
	shown: { gridTemplateRows: '1fr' },
	durationToken: '--panel-expand-duration'
});

/** Slides the panel content down into place, a beat after the panel starts to open. */
export const panelContent = (open: boolean): CrossfadeParams => ({
	active: open,
	hidden: (read) => ({
		opacity: 0,
		transform: `translateY(${read('--panel-content-offset')})`
	}),
	shown: { opacity: 1, transform: 'none' },
	durationToken: '--panel-content-duration',
	delayToken: '--panel-content-delay'
});

/** Fades the open card's tint. */
export const panelTint = (open: boolean): CrossfadeParams => ({
	active: open,
	hidden: () => ({ opacity: 0 }),
	shown: { opacity: 1 },
	durationToken: '--panel-tint-duration'
});

/** Grows a stat bar out from the center. */
export const statBar = (open: boolean): CrossfadeParams => ({
	active: open,
	hidden: () => ({ transform: 'scaleX(0)' }),
	shown: { transform: 'none' },
	durationToken: '--stat-bar-duration',
	delayToken: '--stat-bar-delay'
});
