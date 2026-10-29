// Game detail motion on the Web Animations API, from the design tokens.
import { play, type CrossfadeParams, type PlayParams } from '#lib/hero/motion.ts';

const grow = (from: number, to: number): PlayParams => ({
	keyframes: () => [{ width: `${from * 100}%` }, { width: `${to * 100}%` }],
	durationToken: '--detail-stat-bar-duration'
});

/** Grows a stat bar's width from 0 to its share on mount, and from the old share to the new one on change. */
export function barWidth(node: HTMLElement, share: number) {
	let current = share;
	let running = play(node, grow(0, share));
	return {
		update(next: number) {
			if (next === current) return;
			running?.destroy();
			running = play(node, grow(current, next));
			current = next;
		},
		destroy: () => running?.destroy()
	};
}

/** Fades the game page's mini score in once the scoreboard has left the top of the viewport. */
export const miniScoreFade = (shown: boolean): CrossfadeParams => ({
	active: shown,
	hidden: () => ({ opacity: 0 }),
	shown: { opacity: 1 },
	durationToken: '--panel-tint-duration'
});

/** Opens the mobile score row: padding and the matching negative margin move together, so the flow height holds. */
export const scoreRowOpen = (open: boolean): CrossfadeParams => ({
	active: open,
	hidden: () => ({ paddingTop: '0px', marginBottom: '0px' }),
	shown: {
		paddingTop: 'var(--mini-score-row-height-mobile)',
		marginBottom: 'calc(-1 * var(--mini-score-row-height-mobile))'
	},
	durationToken: '--panel-tint-duration'
});
