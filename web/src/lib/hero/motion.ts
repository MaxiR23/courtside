// Hero motion on the Web Animations API. Durations, distances and easing come
// from the design tokens, read from the computed style at the time they play.

export type TokenReader = (name: string) => string;

export type PlayParams = {
	keyframes: (read: TokenReader) => Keyframe[];
	durationToken: string;
	delayToken?: string;
	delaySteps?: number; // multiplies the delay token, for staggers
	easing?: string; // a token name when it starts with "--", else a CSS easing
	iterations?: number;
	fill?: FillMode;
};

export type CrossfadeParams = {
	active: boolean;
	hidden: (read: TokenReader) => Keyframe;
	shown: Keyframe;
	durationToken: string;
	delayToken?: string; // when set, the hidden look also holds during the delay
};

/** Converts a CSS time such as "1s", "0.5s" or "500ms" to milliseconds. */
export function parseMs(value: string): number {
	const match = value.trim().match(/^(-?\d*\.?\d+)(ms|s)$/);
	if (!match) return 0;
	return match[2] === 's' ? Number(match[1]) * 1000 : Number(match[1]);
}

function reader(node: Element): TokenReader {
	return (name) => getComputedStyle(node).getPropertyValue(name).trim();
}

export function canAnimate(node: Element): boolean {
	if (typeof node.animate !== 'function') return false;
	if (typeof matchMedia !== 'function') return true;
	return !matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function easingOf(read: TokenReader, easing: string): string {
	return easing.startsWith('--') ? read(easing) : easing;
}

/** Plays keyframes on mount. Does nothing without animation support or with reduced motion. */
export function play(node: HTMLElement, params: PlayParams) {
	if (!canAnimate(node)) return;
	const read = reader(node);
	const animation = node.animate(params.keyframes(read), {
		duration: parseMs(read(params.durationToken)),
		delay: params.delayToken ? parseMs(read(params.delayToken)) * (params.delaySteps ?? 1) : 0,
		easing: easingOf(read, params.easing ?? '--ease'),
		iterations: params.iterations ?? 1,
		fill: params.fill ?? 'both'
	});
	return { destroy: () => animation.cancel() };
}

/** Animates between the hidden and shown looks when `active` changes. The CSS holds the resting looks. */
export function crossfade(node: HTMLElement, initial: CrossfadeParams) {
	let active = initial.active;
	let running: Animation | undefined;
	return {
		update(next: CrossfadeParams) {
			if (next.active === active) return;
			active = next.active;
			if (!canAnimate(node)) return;
			const read = reader(node);
			const hidden = next.hidden(read);
			running?.cancel();
			running = node.animate(active ? [hidden, next.shown] : [next.shown, hidden], {
				duration: parseMs(read(next.durationToken)),
				easing: read('--ease'),
				...(next.delayToken
					? { delay: parseMs(read(next.delayToken)), fill: 'backwards' as const }
					: {})
			});
		},
		destroy: () => running?.cancel()
	};
}

/**
 * Glides a transform from where it is to where the CSS now puts it.
 * Call `run` after the DOM holds the new value.
 */
export class Glide {
	#last = 'none';
	#running: Animation | undefined;

	run(node: HTMLElement, durationToken: string): void {
		const read = reader(node);
		let from = this.#last;
		if (this.#running) {
			from = getComputedStyle(node).transform;
			this.#running.cancel();
			this.#running = undefined;
		}
		const to = getComputedStyle(node).transform;
		this.#last = to;
		if (from === to || !canAnimate(node)) return;
		this.#running = node.animate([{ transform: from }, { transform: to }], {
			duration: parseMs(read(durationToken)),
			easing: read('--ease')
		});
	}
}

export const entrance = (delayToken: string): PlayParams => ({
	keyframes: (read) => [
		{ opacity: 0, transform: `translateY(${read('--hero-entrance-offset')})` },
		{ opacity: 1, transform: 'none' }
	],
	durationToken: '--hero-entrance-duration',
	delayToken
});

export const frameEntrance: PlayParams = {
	keyframes: (read) => [
		{
			opacity: 0,
			transform: `translateY(${read('--hero-frame-entrance-offset')}) scale(${read('--hero-frame-entrance-scale')})`
		},
		{ opacity: 1, transform: 'none' }
	],
	durationToken: '--hero-frame-entrance-duration',
	delayToken: '--hero-delay-frame'
};

export const progressFill: PlayParams = {
	keyframes: () => [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }],
	durationToken: '--hero-slide-interval',
	easing: 'linear'
};

export const float: PlayParams = {
	keyframes: (read) => [
		{ transform: 'none' },
		{ transform: `translateY(${read('--hero-float-distance')})` },
		{ transform: 'none' }
	],
	durationToken: '--hero-float-duration',
	easing: 'ease-in-out',
	iterations: Infinity
};

export const floorShadow: PlayParams = {
	keyframes: (read) => [
		{ transform: 'none', opacity: 1 },
		{
			transform: `scaleX(${read('--hero-float-shadow-scale')})`,
			opacity: read('--hero-float-shadow-opacity')
		},
		{ transform: 'none', opacity: 1 }
	],
	durationToken: '--hero-float-duration',
	easing: 'ease-in-out',
	iterations: Infinity
};
