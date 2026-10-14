import { cubicOut } from 'svelte/easing';

import { countText } from '#lib/count/count.ts';

type Options = {
	durationMs: number; // --playoffs-count-duration
	timeoutMs: number; // --playoffs-count-timeout: the final values are forced when it ends
	reduced: boolean; // prefers-reduced-motion: the final values show at once
	setTimer?: typeof setTimeout;
	clearTimer?: typeof clearTimeout;
	requestFrame?: typeof requestAnimationFrame;
	cancelFrame?: typeof cancelAnimationFrame;
	now?: () => number;
};

/**
 * The hero's count-up: a progress from 0 to 1 over the duration, eased on animation frames,
 * and a timeout that forces the final values. No animation library (docs/architecture.md).
 */
export class CountUp {
	#progress = $state(0);
	readonly #options: Options;

	constructor(options: Options) {
		this.#options = options;
	}

	/** 0 to 1. */
	get progress(): number {
		return this.#progress;
	}

	/** The value with each number counted by the progress. */
	text(value: string): string {
		return countText(value, this.#progress);
	}

	/** Starts the count; the returned cleanup clears the timeout and stops the frames. */
	start(): () => void {
		const { reduced, durationMs, timeoutMs } = this.#options;
		if (reduced) {
			this.#progress = 1;
			return () => {};
		}
		const setTimer = this.#options.setTimer ?? setTimeout;
		const clearTimer = this.#options.clearTimer ?? clearTimeout;
		const requestFrame = this.#options.requestFrame ?? ((cb) => requestAnimationFrame(cb));
		const cancelFrame = this.#options.cancelFrame ?? ((id) => cancelAnimationFrame(id));
		const now = this.#options.now ?? (() => performance.now());
		const began = now();
		let frame: number | null = null;

		const step = () => {
			const t = durationMs > 0 ? Math.min(1, (now() - began) / durationMs) : 1;
			this.#progress = cubicOut(t);
			frame = t < 1 ? requestFrame(step) : null;
		};
		frame = requestFrame(step);

		const timer = setTimer(() => {
			if (frame !== null) cancelFrame(frame);
			frame = null;
			this.#progress = 1;
		}, timeoutMs);

		return () => {
			clearTimer(timer);
			if (frame !== null) cancelFrame(frame);
			frame = null;
		};
	}
}
