import type { GamesFeed } from '#lib/contract/games.ts';

export const LIVE_POLL_MS = 30_000;
export const IDLE_POLL_MS = 60_000;

/** ADR 0007: every 30 s while any game is live, every 60 s otherwise. */
export function pollInterval(feed: GamesFeed | null): number {
	const live = feed?.days.some((day) => day.games.some((game) => game.status === 'live'));
	return live ? LIVE_POLL_MS : IDLE_POLL_MS;
}

type Visibility = Pick<Document, 'visibilityState' | 'addEventListener' | 'removeEventListener'>;

function currentTime(): Date {
	return new Date();
}

type Options = {
	now?: () => Date;
	visibility?: () => Visibility;
};

export class GamesFeedPoller {
	feed = $state.raw<GamesFeed | null>(null); // last feed loaded, kept when a later load fails
	receivedAt = $state.raw<Date | null>(null); // when that feed was loaded
	failed = $state(false); // the last load failed

	readonly #load: () => Promise<GamesFeed>;
	readonly #now: () => Date;
	// Getters, not values: the document does not exist during prerender.
	readonly #visibility: () => Visibility;
	#timer: ReturnType<typeof setTimeout> | undefined;
	#loading = false;
	#run = 0; // changes on every start and every cleanup, to drop the result of an old load

	constructor(load: () => Promise<GamesFeed>, options: Options = {}) {
		this.#load = load;
		this.#now = options.now ?? currentTime;
		this.#visibility = options.visibility ?? (() => document);
	}

	/** Loads now and keeps polling. Call from $effect, in the browser only. Returns the cleanup. */
	start(): () => void {
		const run = ++this.#run;
		const page = this.#visibility();
		const onVisibilityChange = () => {
			if (page.visibilityState === 'hidden') {
				this.#clear();
			} else {
				void this.#poll(run);
			}
		};
		page.addEventListener('visibilitychange', onVisibilityChange);
		void this.#poll(run);
		return () => {
			this.#run++;
			this.#clear();
			this.#loading = false;
			page.removeEventListener('visibilitychange', onVisibilityChange);
		};
	}

	#clear(): void {
		clearTimeout(this.#timer);
		this.#timer = undefined;
	}

	async #poll(run: number): Promise<void> {
		if (this.#loading) return;
		this.#clear();
		this.#loading = true;
		let feed: GamesFeed | null = null;
		try {
			feed = await this.#load();
		} catch {
			// Keep the last feed and report the failure.
		}
		if (run !== this.#run) return;
		this.#loading = false;
		if (feed) {
			this.feed = feed;
			this.receivedAt = this.#now();
			this.failed = false;
		} else {
			this.failed = true;
		}
		if (this.#visibility().visibilityState !== 'hidden') {
			this.#timer = setTimeout(() => void this.#poll(run), pollInterval(this.feed));
		}
	}
}
