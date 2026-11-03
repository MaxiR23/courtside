import type { NewsFeed, NewsNote } from '#lib/contract/news.ts';

/**
 * The pages of one news list (the News page): page 1 on start, then one more page per `loadMore`.
 * Notes are deduped by id, the first occurrence wins, because a page can repeat a note published
 * while the reader was on the previous one (ADR 0085). Never polled.
 */
export class NewsPages {
	notes = $state.raw<NewsNote[]>([]); // every note loaded, in feed order
	loaded = $state(false); // page 1 is in
	hasMore = $state(false); // the last page loaded says there is another
	loadingMore = $state(false); // a later page is on its way
	failed = $state(false); // page 1 failed
	error = $state.raw<unknown>(null); // what page 1 threw, null after a success

	readonly #load: (page: number) => Promise<NewsFeed>;
	#page = 0; // the last page loaded
	#run = 0; // changes on every start and every cleanup, to drop the result of an old load

	constructor(load: (page: number) => Promise<NewsFeed>) {
		this.#load = load;
	}

	/** Loads page 1. Call from $effect, in the browser only. Returns the cleanup. */
	start(): () => void {
		const run = ++this.#run;
		void this.#first(run);
		return () => {
			this.#run++;
		};
	}

	/** Loads the next page, one at a time. A failed page keeps the notes and `hasMore`. */
	async loadMore(): Promise<void> {
		if (!this.loaded || !this.hasMore || this.loadingMore) return;
		const run = this.#run;
		this.loadingMore = true;
		let feed: NewsFeed | null;
		try {
			feed = await this.#load(this.#page + 1);
		} catch {
			feed = null;
		}
		if (run !== this.#run) return;
		this.loadingMore = false;
		if (feed) {
			this.#page++;
			this.#append(feed);
		}
	}

	async #first(run: number): Promise<void> {
		let feed: NewsFeed | null = null;
		let error: unknown = null;
		try {
			feed = await this.#load(1);
		} catch (thrown) {
			error = thrown;
		}
		if (run !== this.#run) return;
		if (feed) {
			this.notes = [];
			this.#page = 1;
			this.#append(feed);
			this.loaded = true;
			this.failed = false;
			this.error = null;
		} else {
			this.failed = true;
			this.error = error;
		}
	}

	#append(feed: NewsFeed): void {
		const seen = this.notes.map((note) => note.id);
		const added: NewsNote[] = [];
		for (const note of feed.notes) {
			if (seen.includes(note.id)) continue;
			seen.push(note.id);
			added.push(note);
		}
		this.notes = [...this.notes, ...added];
		this.hasMore = feed.hasMore;
	}
}
