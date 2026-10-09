import type { GameDetailFeed } from '#lib/contract/game-detail.ts';
import type { GamesFeed } from '#lib/contract/games.ts';
import type { PlayerFeed } from '#lib/contract/player.ts';

export const LIVE_POLL_MS = 30_000;
export const IDLE_POLL_MS = 60_000;

/** ADR 0007: every 30 s while any game is live, every 60 s otherwise. */
export function pollInterval(feed: GamesFeed | null): number {
	const live = feed?.days.some((day) => day.games.some((game) => game.status === 'live'));
	return live ? LIVE_POLL_MS : IDLE_POLL_MS;
}

/**
 * Same rules as the home (docs/design-game-detail.md, Polling): 30 s while the game is live,
 * 60 s otherwise.
 */
export function gamePollInterval(feed: GameDetailFeed | null): number {
	return feed?.status === 'live' ? LIVE_POLL_MS : IDLE_POLL_MS;
}

/** docs/design-profiles.md, Polling: every 60 s. */
export function teamPollInterval(): number {
	return IDLE_POLL_MS;
}

/** docs/design-standings-search.md: every 60 s. */
export function standingsPollInterval(): number {
	return IDLE_POLL_MS;
}

/** ADR 0021: every 30 s while the player's team is live, every 60 s otherwise. */
export function playerPollInterval(feed: PlayerFeed | null): number {
	return feed?.live ? LIVE_POLL_MS : IDLE_POLL_MS;
}

type Visibility = Pick<Document, 'visibilityState' | 'addEventListener' | 'removeEventListener'>;

function currentTime(): Date {
	return new Date();
}

type Options = {
	now?: () => Date;
	visibility?: () => Visibility;
};

export class FeedPoller<T> {
	feed = $state.raw<T | null>(null); // last feed loaded, kept when a later load fails
	receivedAt = $state.raw<Date | null>(null); // when that feed was loaded
	failed = $state(false); // the last load failed
	error = $state.raw<unknown>(null); // what the last load threw, null after a success

	readonly #load: () => Promise<T>;
	readonly #interval: (feed: T | null) => number;
	readonly #now: () => Date;
	// Getters, not values: the document does not exist during prerender.
	readonly #visibility: () => Visibility;
	#timer: ReturnType<typeof setTimeout> | undefined;
	#loading = false;
	#run = 0; // changes on every start and every cleanup, to drop the result of an old load

	constructor(load: () => Promise<T>, interval: (feed: T | null) => number, options: Options = {}) {
		this.#load = load;
		this.#interval = interval;
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
		let feed: T | null = null;
		let error: unknown = null;
		try {
			feed = await this.#load();
		} catch (thrown) {
			// Keep the last feed and report the failure.
			error = thrown;
		}
		if (run !== this.#run) return;
		this.#loading = false;
		if (feed) {
			this.feed = feed;
			this.receivedAt = this.#now();
			this.failed = false;
			this.error = null;
		} else {
			this.failed = true;
			this.error = error;
		}
		if (this.#visibility().visibilityState !== 'hidden') {
			this.#timer = setTimeout(() => void this.#poll(run), this.#interval(this.feed));
		}
	}
}

export class GamesFeedPoller extends FeedPoller<GamesFeed> {
	constructor(load: () => Promise<GamesFeed>, options: Options = {}) {
		super(load, pollInterval, options);
	}
}
