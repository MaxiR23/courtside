// The game detail reads of a past day's cards: one per game, on its first expand, kept for the life of the page and never polled.
// SEE: docs/adr/0057-past-game-detail-leaders.md, docs/adr/0054-historical-sides-and-past-pages.md
import type { GameDetailFeed } from '#lib/contract/game-detail.ts';
import { FeedOnce } from '#lib/feed/once.svelte.ts';

/**
 * The game detail of each past card that was opened. A read starts the first time a game is opened
 * and never again; a failed read shows nothing. With no loader nothing loads.
 */
export class DayCardStats {
	#reads = $state.raw<Record<string, FeedOnce<GameDetailFeed>>>({});
	#stops: (() => void)[] = [];
	readonly #load: ((id: string) => Promise<GameDetailFeed>) | undefined;

	constructor(load: ((id: string) => Promise<GameDetailFeed>) | undefined) {
		this.#load = load;
	}

	/** The game detail loaded for this game, null until it is in or when the read failed. */
	feed(id: string): GameDetailFeed | null {
		return this.#reads[id]?.feed ?? null;
	}

	/** Starts the read of this game, once. */
	open(id: string): void {
		const load = this.#load;
		if (!load || id in this.#reads) return;
		const read = new FeedOnce<GameDetailFeed>(() => load(id));
		this.#reads = { ...this.#reads, [id]: read };
		this.#stops.push(read.start());
	}

	/** Releases every read: a late answer is dropped. */
	stop(): void {
		for (const stop of this.#stops) stop();
		this.#stops = [];
	}
}
