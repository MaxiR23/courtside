export const SPOILER_FREE_KEY = 'courtside.spoiler-free';

export class SpoilerFree {
	on = $state(false); // off by default

	readonly #storage: () => Storage | undefined;

	// A getter, not a value: reading window.localStorage itself can throw (blocked storage).
	constructor(storage: () => Storage | undefined = () => globalThis.localStorage) {
		this.#storage = storage;
	}

	/** Reads the remembered choice. Call from $effect, in the browser only. */
	load(): void {
		try {
			this.on = this.#storage()?.getItem(SPOILER_FREE_KEY) === 'on';
		} catch {
			// Storage unavailable: keep the in-memory value.
		}
	}

	toggle(): void {
		this.on = !this.on;
		try {
			this.#storage()?.setItem(SPOILER_FREE_KEY, this.on ? 'on' : 'off');
		} catch {
			// Storage unavailable or full: the choice still holds for this visit.
		}
	}
}
