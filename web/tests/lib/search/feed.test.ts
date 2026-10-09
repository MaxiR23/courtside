// web/tests/lib/search/feed.test.ts
//
// Tests for the search feed store.
//
// Tested:
// - The first open loads once and builds the index
// - A second open while a request is in flight sends no second request
// - A later open loads again, and the index in memory stays usable meanwhile
// - A failed load sets unavailable; the next open loads again and clears it on success
// - A failed revalidation keeps the index and does not set unavailable
// - With no loader the store is unavailable and loads nothing
//
// What is covered:
// - The reactive module without mounting; the loader is a mock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/lib/search/feed.test.ts
//
// SEE: web/src/lib/search/feed.svelte.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it, vi } from 'vitest';

import type { SearchFeed } from '../../../src/lib/contract/search';
import { SearchFeedStore } from '../../../src/lib/search/feed.svelte';

const feed = JSON.parse(
	readFileSync(join(__dirname, '../feed/fixtures/search.json'), 'utf8')
) as SearchFeed;

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('SearchFeedStore', () => {
	it('loads once on the first open and builds the index', async () => {
		const load = vi.fn(() => Promise.resolve(feed));
		const store = new SearchFeedStore(load);
		expect(store.index).toBeNull();
		store.open();
		await flush();
		expect(load).toHaveBeenCalledTimes(1);
		expect(store.index?.teams).toHaveLength(30);
		expect(store.unavailable).toBe(false);
	});

	it('sends no second request while one is in flight', async () => {
		let resolve: (value: SearchFeed) => void = () => {};
		const load = vi.fn(() => new Promise<SearchFeed>((r) => (resolve = r)));
		const store = new SearchFeedStore(load);
		store.open();
		store.open();
		expect(load).toHaveBeenCalledTimes(1);
		resolve(feed);
		await flush();
		expect(store.index).not.toBeNull();
	});

	it('loads again on a later open and keeps the index meanwhile', async () => {
		let resolve: (value: SearchFeed) => void = () => {};
		const load = vi
			.fn<() => Promise<SearchFeed>>()
			.mockResolvedValueOnce(feed)
			.mockImplementationOnce(() => new Promise<SearchFeed>((r) => (resolve = r)));
		const store = new SearchFeedStore(load);
		store.open();
		await flush();
		const first = store.index;
		store.open();
		expect(load).toHaveBeenCalledTimes(2);
		expect(store.index).toBe(first);
		resolve(feed);
		await flush();
		expect(store.index).not.toBe(first);
		expect(store.index).not.toBeNull();
	});

	it('is unavailable after a failed load, and the next open retries and clears it', async () => {
		const load = vi
			.fn<() => Promise<SearchFeed>>()
			.mockRejectedValueOnce(new Error('503'))
			.mockResolvedValueOnce(feed);
		const store = new SearchFeedStore(load);
		store.open();
		await flush();
		expect(store.unavailable).toBe(true);
		expect(store.index).toBeNull();
		store.open();
		expect(store.unavailable).toBe(false);
		await flush();
		expect(load).toHaveBeenCalledTimes(2);
		expect(store.unavailable).toBe(false);
		expect(store.index).not.toBeNull();
	});

	it('keeps the index and stays available when a revalidation fails', async () => {
		const load = vi
			.fn<() => Promise<SearchFeed>>()
			.mockResolvedValueOnce(feed)
			.mockRejectedValueOnce(new Error('network'));
		const store = new SearchFeedStore(load);
		store.open();
		await flush();
		const index = store.index;
		store.open();
		await flush();
		expect(store.index).toBe(index);
		expect(store.unavailable).toBe(false);
	});

	it('is unavailable and loads nothing without a loader', () => {
		const store = new SearchFeedStore(undefined);
		store.open();
		expect(store.unavailable).toBe(true);
		expect(store.index).toBeNull();
	});
});
