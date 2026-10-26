import type { AllStarFeed } from '#lib/contract/all-star.ts';
import type { GameDetailFeed } from '#lib/contract/game-detail.ts';
import type { GamesFeed } from '#lib/contract/games.ts';
import type { PlayerFeed } from '#lib/contract/player.ts';
import type { PlayoffsFeed } from '#lib/contract/playoffs.ts';
import type { PowerRankingFeed } from '#lib/contract/power-ranking.ts';
import type { StandingsFeed } from '#lib/contract/standings.ts';
import type { CupFeed } from '#lib/contract/cup.ts';
import type { TeamFeed } from '#lib/contract/team.ts';

export const LIVE_POLL_MS = 30_000;
export const IDLE_POLL_MS = 60_000;
export const SLOW_POLL_MS = 300_000;

/** ADR 0007: every 30 s while any game is live, every 60 s otherwise. */
export function pollInterval(feed: GamesFeed | null): number {
	const live = feed?.days.some((day) => day.games.some((game) => game.status === 'live'));
	return live ? LIVE_POLL_MS : IDLE_POLL_MS;
}

/**
 * docs/design-game-detail.md, Polling: 30 s while live, 60 s otherwise, and no more polling once
 * the game is final (past seasons included). Null means the feed is done.
 */
export function gamePollInterval(feed: GameDetailFeed | null): number | null {
	if (feed?.status === 'final') return null;
	return feed?.status === 'live' ? LIVE_POLL_MS : IDLE_POLL_MS;
}

/**
 * docs/design-profiles.md, Polling: every 5 min once a feed is loaded (the team feed has no live
 * part), every 60 s while no feed has loaded yet.
 */
export function teamPollInterval(feed: TeamFeed | null): number {
	return feed ? SLOW_POLL_MS : IDLE_POLL_MS;
}

/** docs/design-standings-search.md, Polling: every 5 min once final, every 60 s otherwise. */
export function standingsPollInterval(feed: StandingsFeed | null): number {
	return feed?.state === 'final' ? SLOW_POLL_MS : IDLE_POLL_MS;
}

/** docs/design-standings-search.md, Polling: the power ranking every 5 min once loaded, every 60 s while none has loaded. */
export function powerRankingPollInterval(feed: PowerRankingFeed | null): number {
	return feed ? SLOW_POLL_MS : IDLE_POLL_MS;
}

/** docs/design-cup.md, Polling: every 5 min once the Cup is complete, every 60 s otherwise. */
export function cupPollInterval(feed: CupFeed | null): number {
	return feed?.stage === 'complete' ? SLOW_POLL_MS : IDLE_POLL_MS;
}

/** docs/design-cup.md, Polling: the open matchup panel every 60 s. */
export function cupMatchupPollInterval(): number {
	return IDLE_POLL_MS;
}

/** docs/design-playoffs.md, Polling: every 5 min once complete, every 60 s otherwise. */
export function playoffsPollInterval(feed: PlayoffsFeed | null): number {
	return feed?.state === 'complete' ? SLOW_POLL_MS : IDLE_POLL_MS;
}

/** ADR 0036: every 30 s while the day is live (the feed expires 30 s after the build), else 60 s. */
export function allStarPollInterval(feed: AllStarFeed | null): number {
	return feed?.state === 'live' ? LIVE_POLL_MS : IDLE_POLL_MS;
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
	readonly #interval: (feed: T | null) => number | null;
	readonly #now: () => Date;
	// Getters, not values: the document does not exist during prerender.
	readonly #visibility: () => Visibility;
	#timer: ReturnType<typeof setTimeout> | undefined;
	#loading = false;
	#done = false; // the interval said the feed can no longer change
	#run = 0; // changes on every start and every cleanup, to drop the result of an old load

	constructor(
		load: () => Promise<T>,
		interval: (feed: T | null) => number | null,
		options: Options = {}
	) {
		this.#load = load;
		this.#interval = interval;
		this.#now = options.now ?? currentTime;
		this.#visibility = options.visibility ?? (() => document);
	}

	/** Loads now and keeps polling until the interval returns null. Call from $effect, in the browser only. Returns the cleanup. */
	start(): () => void {
		const run = ++this.#run;
		this.#done = false;
		const page = this.#visibility();
		const onVisibilityChange = () => {
			if (page.visibilityState === 'hidden') {
				this.#clear();
			} else if (!this.#done) {
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
		const next = this.#interval(this.feed);
		if (next === null) {
			this.#done = true;
			return;
		}
		if (this.#visibility().visibilityState !== 'hidden') {
			this.#timer = setTimeout(() => void this.#poll(run), next);
		}
	}
}

export class GamesFeedPoller extends FeedPoller<GamesFeed> {
	constructor(load: () => Promise<GamesFeed>, options: Options = {}) {
		super(load, pollInterval, options);
	}
}
