export const SLIDE_INTERVAL_MS = 7000;

export class Slideshow {
	current = $state(0);
	// Increments on every slide change or restart, to rekey the progress fill.
	cycle = $state(0);

	readonly #count: number;
	readonly #intervalMs: number;
	#timer: ReturnType<typeof setTimeout> | undefined;
	#running = false;

	constructor(count: number, intervalMs: number = SLIDE_INTERVAL_MS) {
		if (!Number.isInteger(count) || count < 1) {
			throw new RangeError(`Slide count must be an integer of at least 1, got ${count}`);
		}
		this.#count = count;
		this.#intervalMs = intervalMs;
	}

	next(): void {
		this.current = (this.current + 1) % this.#count;
		this.cycle += 1;
	}

	goTo(index: number): void {
		if (!Number.isInteger(index) || index < 0 || index >= this.#count) {
			throw new RangeError(`Slide ${index} is out of range for ${this.#count} slides`);
		}
		this.current = index;
		this.cycle += 1;
		if (this.#running) this.#schedule();
	}

	start(): () => void {
		this.#running = true;
		this.#schedule();
		return () => this.#stop();
	}

	#schedule(): void {
		clearTimeout(this.#timer);
		this.#timer = setTimeout(() => {
			this.next();
			this.#schedule();
		}, this.#intervalMs);
	}

	#stop(): void {
		this.#running = false;
		clearTimeout(this.#timer);
		this.#timer = undefined;
	}
}
