// web/tests/lib/day/card-stats.svelte.test.ts
//
// Tests for the game detail reads of a past day's cards.
//
// Tested:
// - Opening a game loads its game detail once, with its id
// - A second open of the same game does not load again; another game loads on its own
// - A game that was never opened is not loaded and has no feed
// - A failed load gives no feed and is not tried again
// - With no loader nothing loads
// - Stopping drops a late answer
//
// What is covered:
// - The reactive module without mounting; the loader is a mock, no network, no clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/day/card-stats.svelte.test.ts
//
// SEE: web/src/lib/day/card-stats.svelte.ts
import { describe, expect, it, vi } from 'vitest';

import type { GameDetailFeed } from '../../../src/lib/contract/game-detail';
import { DayCardStats } from '../../../src/lib/day/card-stats.svelte';

const feedOf = (id: string): GameDetailFeed => ({ id }) as unknown as GameDetailFeed;
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('DayCardStats', () => {
	it('loads the game detail of an opened game once', async () => {
		const load = vi.fn((id: string) => Promise.resolve(feedOf(id)));
		const reads = new DayCardStats(load);
		reads.open('g1');
		reads.open('g1');
		await settle();
		expect(load).toHaveBeenCalledTimes(1);
		expect(load).toHaveBeenCalledWith('g1');
		expect(reads.feed('g1')?.id).toBe('g1');
	});

	it('loads each game on its own and leaves the others alone', async () => {
		const load = vi.fn((id: string) => Promise.resolve(feedOf(id)));
		const reads = new DayCardStats(load);
		reads.open('g1');
		reads.open('g2');
		await settle();
		expect(load.mock.calls.map(([id]) => id)).toEqual(['g1', 'g2']);
		expect(reads.feed('g3')).toBeNull();
	});

	it('gives no feed for a failed load and does not try again', async () => {
		const load = vi.fn(() => Promise.reject(new Error('down')));
		const reads = new DayCardStats(load);
		reads.open('g1');
		await settle();
		reads.open('g1');
		await settle();
		expect(reads.feed('g1')).toBeNull();
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('loads nothing with no loader', () => {
		const reads = new DayCardStats(undefined);
		reads.open('g1');
		expect(reads.feed('g1')).toBeNull();
	});

	it('drops a late answer after stop', async () => {
		let answer: (feed: GameDetailFeed) => void = () => {};
		const load = vi.fn(() => new Promise<GameDetailFeed>((resolve) => (answer = resolve)));
		const reads = new DayCardStats(load);
		reads.open('g1');
		reads.stop();
		answer(feedOf('g1'));
		await settle();
		expect(reads.feed('g1')).toBeNull();
	});
});
