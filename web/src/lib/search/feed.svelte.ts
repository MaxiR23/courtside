import type { SearchFeed } from '#lib/contract/search.ts';
import { buildSearchIndex, type SearchIndex } from '#lib/search/match.ts';

/**
 * The search index, in memory for the page's life. It loads on every open: the first open
 * fetches it, later opens revalidate it (the loader asks the browser to). Unlike FeedPoller it
 * never loads on a timer.
 */
export class SearchFeedStore {
	index = $state.raw<SearchIndex | null>(null); // last index built, kept when a later load fails
	unavailable = $state(false);

	readonly #load: (() => Promise<SearchFeed>) | undefined;
	#loading = false;

	// No loader means no feed URL is set: the overlay shows the unavailable line.
	constructor(load: (() => Promise<SearchFeed>) | undefined) {
		this.#load = load;
	}

	/** Call once per open. */
	open(): void {
		if (!this.#load) {
			this.unavailable = true;
			return;
		}
		if (this.#loading) return;
		this.#loading = true;
		if (this.index === null) this.unavailable = false;
		this.#load().then(
			(feed) => {
				this.index = buildSearchIndex(feed);
				this.unavailable = false;
				this.#loading = false;
			},
			() => {
				// An index that is in stays in use when a later load fails.
				if (this.index === null) this.unavailable = true;
				this.#loading = false;
			}
		);
	}
}
