// Search overlay motion on the Web Animations API: the backdrop fades and the panel rises on
// open; both play backwards on close. Durations and distances come from the design tokens.
import { canAnimate, parseMs, type PlayParams } from '#lib/hero/motion.ts';

export const backdropFade: PlayParams = {
	keyframes: () => [{ opacity: 0 }, { opacity: 1 }],
	durationToken: '--list-entrance-duration'
};

export const panelRise: PlayParams = {
	keyframes: (read) => [
		{ opacity: 0, transform: `translateY(${read('--list-entrance-offset')})` },
		{ opacity: 1, transform: 'none' }
	],
	durationToken: '--list-entrance-duration'
};

/** Plays the keyframes backwards. Resolves at once without animation support or with reduced motion. */
export async function playReverse(node: HTMLElement, params: PlayParams): Promise<void> {
	if (!canAnimate(node)) return;
	const read = (name: string) => getComputedStyle(node).getPropertyValue(name).trim();
	const easing = params.easing ?? '--ease';
	const animation = node.animate([...params.keyframes(read)].reverse(), {
		duration: parseMs(read(params.durationToken)),
		easing: easing.startsWith('--') ? read(easing) : easing,
		fill: 'forwards'
	});
	try {
		await animation.finished;
	} catch {
		// Cancelled: the overlay is going away anyway.
	}
}
