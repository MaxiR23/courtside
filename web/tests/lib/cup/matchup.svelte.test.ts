// web/tests/lib/cup/matchup.svelte.test.ts
//
// Tests for the Cup matchup store.
//
// Tested:
// - Opening a node loads its matchup once, with its id
// - The matchup loads again after 60 s while open and no more after close
// - A failed load sets failed and keeps polling
// - Opening another node drops the first node's feed
// - With no loader an open node is failed at once
//
// What is covered:
// - The reactive module without mounting; fake timers and a fake document
// - No real network: the loader is a mock
//
// Run with: cd web && pnpm exec vitest run tests/lib/cup/matchup.svelte.test.ts
//
// SEE: web/src/lib/cup/matchup.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CupMatchupFeed, SlotId } from '../../../src/lib/contract/cup-matchup';
import { CupMatchupStore } from '../../../src/lib/cup/matchup.svelte';

const feedOf = (id: SlotId): CupMatchupFeed => ({ id }) as unknown as CupMatchupFeed;

const page = {
	visibilityState: 'visible' as DocumentVisibilityState,
	addEventListener: () => {},
	removeEventListener: () => {}
};

const store = (load: ((id: SlotId) => Promise<CupMatchupFeed>) | undefined) =>
	new CupMatchupStore(load, { visibility: () => page as unknown as Document });

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('CupMatchupStore', () => {
	it('is closed, with nothing loading or failed, at first', () => {
		const matchups = store(vi.fn());
		expect(matchups.openId).toBeNull();
		expect([matchups.feed, matchups.loading, matchups.failed]).toEqual([null, false, false]);
	});

	it('loads the opened node once with its id, loading until it answers', async () => {
		const load = vi.fn((id: SlotId) => Promise.resolve(feedOf(id)));
		const matchups = store(load);
		matchups.open('final');
		expect(matchups.openId).toBe('final');
		expect(matchups.loading).toBe(true);
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(1);
		expect(load).toHaveBeenCalledWith('final');
		expect(matchups.feed?.id).toBe('final');
		expect(matchups.loading).toBe(false);
		matchups.close();
	});

	it('loads again after 60 s while open and never after close', async () => {
		const load = vi.fn((id: SlotId) => Promise.resolve(feedOf(id)));
		const matchups = store(load);
		matchups.open('east-sf');
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(59_999);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(load).toHaveBeenCalledTimes(2);
		matchups.close();
		expect(matchups.openId).toBeNull();
		expect(matchups.feed).toBeNull();
		await vi.advanceTimersByTimeAsync(180_000);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('sets failed on a failed load and keeps polling', async () => {
		const load = vi
			.fn<(id: SlotId) => Promise<CupMatchupFeed>>()
			.mockRejectedValueOnce(new Error('503'))
			.mockResolvedValue(feedOf('final'));
		const matchups = store(load);
		matchups.open('final');
		await vi.advanceTimersByTimeAsync(0);
		expect(matchups.failed).toBe(true);
		expect(matchups.loading).toBe(false);
		await vi.advanceTimersByTimeAsync(60_000);
		expect(load).toHaveBeenCalledTimes(2);
		expect(matchups.failed).toBe(false);
		expect(matchups.feed?.id).toBe('final');
		matchups.close();
	});

	it('drops the first feed when another node opens', async () => {
		const load = vi.fn((id: SlotId) => Promise.resolve(feedOf(id)));
		const matchups = store(load);
		matchups.open('east-qf-1');
		await vi.advanceTimersByTimeAsync(0);
		expect(matchups.feed?.id).toBe('east-qf-1');
		matchups.open('west-qf-1');
		expect(matchups.feed).toBeNull();
		expect(matchups.loading).toBe(true);
		await vi.advanceTimersByTimeAsync(0);
		expect(matchups.feed?.id).toBe('west-qf-1');
		matchups.close();
	});

	it('is failed at once with no loader', () => {
		const matchups = store(undefined);
		matchups.open('final');
		expect(matchups.failed).toBe(true);
		expect(matchups.loading).toBe(false);
		expect(matchups.feed).toBeNull();
	});
});
