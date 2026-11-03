// web/tests/lib/news/pages.svelte.test.ts
//
// Tests for the paging of the News page.
//
// Tested:
// - It loads page 1 on start
// - loadMore loads the next page and appends; a repeated id is dropped
// - hasMore false stops loadMore
// - Two quick loadMore calls send one request
// - A failed later page keeps the notes and hasMore
// - A failure on page 1 sets failed and the error
// - An answer that arrives after the cleanup is dropped
//
// What is covered:
// - The reactive module without mounting; the load function is a mock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/news/pages.svelte.test.ts
//
// SEE: web/src/lib/news/pages.svelte.ts
import { describe, expect, it, vi } from 'vitest';

import type { NewsFeed, NewsNote } from '../../../src/lib/contract/news';
import { NewsPages } from '../../../src/lib/news/pages.svelte';

const note = (id: string) => ({ id }) as NewsNote;
const page = (n: number, ids: string[], hasMore = true) =>
	({ page: n, hasMore, notes: ids.map(note) }) as unknown as NewsFeed;
const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('NewsPages', () => {
	it('loads page 1 on start', async () => {
		const load = vi.fn().mockResolvedValue(page(1, ['a', 'b']));
		const pages = new NewsPages(load);
		pages.start();
		await flush();
		expect(load).toHaveBeenCalledWith(1);
		expect(pages.notes.map((n) => n.id)).toEqual(['a', 'b']);
		expect(pages.loaded).toBe(true);
		expect(pages.hasMore).toBe(true);
	});

	it('loads page 2 on loadMore, appends and drops a repeated id', async () => {
		const load = vi
			.fn()
			.mockResolvedValueOnce(page(1, ['a', 'b']))
			.mockResolvedValueOnce(page(2, ['b', 'c'], false));
		const pages = new NewsPages(load);
		pages.start();
		await flush();
		await pages.loadMore();
		expect(load).toHaveBeenLastCalledWith(2);
		expect(pages.notes.map((n) => n.id)).toEqual(['a', 'b', 'c']);
		expect(pages.hasMore).toBe(false);
	});

	it('does nothing once hasMore is false', async () => {
		const load = vi.fn().mockResolvedValue(page(1, ['a'], false));
		const pages = new NewsPages(load);
		pages.start();
		await flush();
		await pages.loadMore();
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('sends one request for two quick loadMore calls', async () => {
		const load = vi
			.fn()
			.mockResolvedValueOnce(page(1, ['a']))
			.mockResolvedValue(page(2, ['b']));
		const pages = new NewsPages(load);
		pages.start();
		await flush();
		const first = pages.loadMore();
		expect(pages.loadingMore).toBe(true);
		const second = pages.loadMore();
		await Promise.all([first, second]);
		expect(load).toHaveBeenCalledTimes(2);
		expect(pages.loadingMore).toBe(false);
	});

	it('keeps the notes and hasMore when page 2 fails, and asks for page 2 again', async () => {
		const load = vi
			.fn()
			.mockResolvedValueOnce(page(1, ['a']))
			.mockRejectedValueOnce(new Error('down'))
			.mockResolvedValueOnce(page(2, ['b'], false));
		const pages = new NewsPages(load);
		pages.start();
		await flush();
		await pages.loadMore();
		expect(pages.notes.map((n) => n.id)).toEqual(['a']);
		expect(pages.hasMore).toBe(true);
		expect(pages.failed).toBe(false);
		await pages.loadMore();
		expect(load).toHaveBeenLastCalledWith(2);
		expect(pages.notes.map((n) => n.id)).toEqual(['a', 'b']);
	});

	it('sets failed and the error when page 1 fails', async () => {
		const error = new Error('404');
		const pages = new NewsPages(vi.fn().mockRejectedValue(error));
		pages.start();
		await flush();
		expect(pages.failed).toBe(true);
		expect(pages.error).toBe(error);
		expect(pages.loaded).toBe(false);
	});

	it('drops a late result after the cleanup', async () => {
		let resolve: (feed: NewsFeed) => void = () => {};
		const load = vi.fn(() => new Promise<NewsFeed>((r) => (resolve = r)));
		const pages = new NewsPages(load);
		const stop = pages.start();
		stop();
		resolve(page(1, ['a']));
		await flush();
		expect(pages.loaded).toBe(false);
		expect(pages.notes).toEqual([]);
	});
});
