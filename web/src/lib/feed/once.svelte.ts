/**
 * Loads one feed once and never polls it: a past season's feed does not change (ADR 0044). Same
 * fields as `FeedPoller`, so a page reads either the same way.
 */
export class FeedOnce<T> {
	feed = $state.raw<T | null>(null); // the feed loaded, null until then
	failed = $state(false); // the load failed
	error = $state.raw<unknown>(null); // what the load threw, null after a success

	readonly #load: () => Promise<T>;
	#run = 0; // changes on every start and every cleanup, to drop the result of an old load

	constructor(load: () => Promise<T>) {
		this.#load = load;
	}

	/** Loads now, once. Call from $effect, in the browser only. Returns the cleanup. */
	start(): () => void {
		const run = ++this.#run;
		void this.#fetch(run);
		return () => {
			this.#run++;
		};
	}

	async #fetch(run: number): Promise<void> {
		let feed: T | null = null;
		let error: unknown = null;
		try {
			feed = await this.#load();
		} catch (thrown) {
			error = thrown;
		}
		if (run !== this.#run) return;
		if (feed) {
			this.feed = feed;
			this.failed = false;
			this.error = null;
		} else {
			this.failed = true;
			this.error = error;
		}
	}
}
