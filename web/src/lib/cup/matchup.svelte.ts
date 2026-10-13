import type { CupMatchupFeed, SlotId } from '#lib/contract/cup-matchup.ts';
import { cupPollInterval, FeedPoller } from '#lib/feed/poller.svelte.ts';

type PollerOptions = ConstructorParameters<typeof FeedPoller>[2];

/**
 * The matchup feed of the node that is open. It loads when a node opens and polls with the Cup
 * page's interval while the panel stays open; a new poller per open means a feed from another node
 * is never shown. With no loader (no URL configured) an open node is failed at once.
 */
export class CupMatchupStore {
	openId = $state<SlotId | null>(null);
	#poller = $state.raw<FeedPoller<CupMatchupFeed> | null>(null);
	#stop: (() => void) | undefined;
	readonly #load: ((id: SlotId) => Promise<CupMatchupFeed>) | undefined;
	readonly #options: PollerOptions;

	constructor(
		load: ((id: SlotId) => Promise<CupMatchupFeed>) | undefined,
		options?: PollerOptions
	) {
		this.#load = load;
		this.#options = options;
	}

	/** The last matchup loaded for the open node, kept when a later load fails. */
	get feed(): CupMatchupFeed | null {
		return this.#poller?.feed ?? null;
	}

	/** The node is open and its feed is not available. */
	get failed(): boolean {
		if (this.openId === null) return false;
		return this.#poller ? this.#poller.failed : true;
	}

	/** The node is open and its first load has not answered. */
	get loading(): boolean {
		return this.openId !== null && this.feed === null && !this.failed;
	}

	open(id: SlotId): void {
		this.#release();
		this.openId = id;
		const load = this.#load;
		if (!load) return;
		const poller = new FeedPoller<CupMatchupFeed>(() => load(id), cupPollInterval, this.#options);
		this.#poller = poller;
		this.#stop = poller.start();
	}

	close(): void {
		this.#release();
		this.openId = null;
	}

	#release(): void {
		this.#stop?.();
		this.#stop = undefined;
		this.#poller = null;
	}
}
