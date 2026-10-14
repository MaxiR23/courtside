// A one-second tick for the live clock. The clock is never counted down: a component reads
// `tick` and then the latest feed value, so the text is re-rendered every second from the feed.
// SEE: docs/design-all-star.md, Interactions and motion

export const TICK_MS = 1000;

type Options = {
	setTimer?: typeof setInterval;
	clearTimer?: typeof clearInterval;
};

export class LiveTick {
	tick = $state(0);
	readonly #options: Options;

	constructor(options: Options = {}) {
		this.#options = options;
	}

	/** Starts ticking; the returned cleanup stops it. Call from $effect. */
	start(): () => void {
		const setTimer = this.#options.setTimer ?? setInterval;
		const clearTimer = this.#options.clearTimer ?? clearInterval;
		const timer = setTimer(() => {
			this.tick += 1;
		}, TICK_MS);
		return () => clearTimer(timer);
	}
}
