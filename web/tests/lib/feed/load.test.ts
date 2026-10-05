// web/tests/lib/feed/load.test.ts
//
// Tests for loading the games feed.
//
// Tested:
// - Returns the parsed feed on a 200, asking for JSON from the given URL
// - Throws a FeedLoadError on a 503, a network error, a body that is not JSON and JSON without days
//
// What is covered:
// - Happy path and every failure the page treats as "data unavailable"
// - A mocked fetch that throws for any URL other than the expected one, no real network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/load.test.ts
//
// SEE: web/src/lib/feed/load.ts
import { describe, expect, it, vi } from 'vitest';

import { FeedLoadError, loadGamesFeed } from '../../../src/lib/feed/load';

const URL_OK = 'https://feeds.example.com/games.json';

function fetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== URL_OK) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

const json = (body: unknown, status = 200) =>
	Promise.resolve(new Response(JSON.stringify(body), { status }));

describe('loadGamesFeed', () => {
	it('returns the parsed feed on a 200', async () => {
		const feed = { generatedAt: '2026-10-04T12:00:00Z', days: [] };
		const fetchFn = fetchAnswering(() => json(feed));
		await expect(loadGamesFeed(URL_OK, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(URL_OK, { headers: { accept: 'application/json' } });
	});

	it('throws on a 503 before the first publication', async () => {
		const fetchFn = fetchAnswering(() => json({ detail: 'not ready' }, 503));
		await expect(loadGamesFeed(URL_OK, fetchFn)).rejects.toMatchObject({
			name: 'FeedLoadError',
			reason: 'status'
		});
	});

	it('throws on a network error', async () => {
		const fetchFn = fetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')));
		const error = await loadGamesFeed(URL_OK, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('network');
	});

	it('throws on a body that is not JSON', async () => {
		const fetchFn = fetchAnswering(() => Promise.resolve(new Response('<html>', { status: 200 })));
		await expect(loadGamesFeed(URL_OK, fetchFn)).rejects.toMatchObject({ reason: 'body' });
	});

	it('throws on JSON without days', async () => {
		const fetchFn = fetchAnswering(() => json({ generatedAt: 'x' }));
		await expect(loadGamesFeed(URL_OK, fetchFn)).rejects.toMatchObject({ reason: 'body' });
	});
});
