// Game detail motion on the Web Animations API, from the design tokens.
import { play, type PlayParams } from '#lib/hero/motion.ts';

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
