// web/tests/lib/feed/load.test.ts
//
// Tests for loading the games feed, a game's detail feed and a team's feed.
//
// Tested:
// - Returns the parsed feed on a 200, asking for JSON from the given URL
// - Throws a FeedLoadError on a 503, a network error, a body that is not JSON and JSON without days
// - gameFeedUrl puts the encoded game id in place of {id}
// - loadGameDetailFeed returns the detail feed, reports a 404 as not-found and every other failure
// - teamFeedUrl puts the encoded team code in place of {code}
// - loadTeamFeed returns the team feed, reports a 404 as not-found and every other failure
//
// What is covered:
// - Happy path and every failure the page treats as "data unavailable"
// - A mocked fetch that throws for any URL other than the expected one, no real network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/load.test.ts
//
// SEE: web/src/lib/feed/load.ts
import { describe, expect, it, vi } from 'vitest';

import {
	FeedLoadError,
	gameFeedUrl,
	loadGameDetailFeed,
	loadGamesFeed,
	loadTeamFeed,
	teamFeedUrl
} from '../../../src/lib/feed/load';

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

const DETAIL_TEMPLATE = 'https://feeds.example.com/games/{id}.json';
const DETAIL_URL = 'https://feeds.example.com/games/401.json';

function detailFetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== DETAIL_URL) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('gameFeedUrl', () => {
	it('builds the detail feed URL by putting the encoded id in place of {id}', () => {
		expect(gameFeedUrl(DETAIL_TEMPLATE, '401')).toBe(DETAIL_URL);
		expect(gameFeedUrl(DETAIL_TEMPLATE, 'a/b c')).toBe(
			'https://feeds.example.com/games/a%2Fb%20c.json'
		);
	});
});

describe('loadGameDetailFeed', () => {
	it('returns the parsed detail feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { id: '401', status: 'live' };
		const fetchFn = detailFetchAnswering(() => json(feed));
		await expect(loadGameDetailFeed(DETAIL_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(DETAIL_URL, { headers: { accept: 'application/json' } });
	});

	it('throws a not-found FeedLoadError when the detail feed answers 404', async () => {
		const fetchFn = detailFetchAnswering(() => json({ detail: 'no game' }, 404));
		const error = await loadGameDetailFeed(DETAIL_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('not-found');
	});

	it('throws a FeedLoadError on a 503, a network error, a non-JSON body and JSON without an id', async () => {
		await expect(
			loadGameDetailFeed(
				DETAIL_URL,
				detailFetchAnswering(() => json({}, 503))
			)
		).rejects.toMatchObject({ reason: 'status' });
		await expect(
			loadGameDetailFeed(
				DETAIL_URL,
				detailFetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')))
			)
		).rejects.toMatchObject({ reason: 'network' });
		await expect(
			loadGameDetailFeed(
				DETAIL_URL,
				detailFetchAnswering(() => Promise.resolve(new Response('<html>', { status: 200 })))
			)
		).rejects.toMatchObject({ reason: 'body' });
		await expect(
			loadGameDetailFeed(
				DETAIL_URL,
				detailFetchAnswering(() => json({ status: 'live' }))
			)
		).rejects.toMatchObject({ reason: 'body' });
	});
});

const TEAM_TEMPLATE = 'https://feeds.example.com/teams/{code}.json';
const TEAM_URL = 'https://feeds.example.com/teams/okc.json';

function teamFetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== TEAM_URL) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('teamFeedUrl', () => {
	it('builds the team feed URL by putting the encoded code in place of {code}', () => {
		expect(teamFeedUrl(TEAM_TEMPLATE, 'okc')).toBe(TEAM_URL);
		expect(teamFeedUrl(TEAM_TEMPLATE, 'a/b c')).toBe(
			'https://feeds.example.com/teams/a%2Fb%20c.json'
		);
	});
});

describe('loadTeamFeed', () => {
	it('returns the parsed team feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { code: 'OKC', name: 'Thunder' };
		const fetchFn = teamFetchAnswering(() => json(feed));
		await expect(loadTeamFeed(TEAM_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(TEAM_URL, { headers: { accept: 'application/json' } });
	});

	it('throws a not-found FeedLoadError when the team feed answers 404', async () => {
		const fetchFn = teamFetchAnswering(() => json({ detail: 'no team' }, 404));
		const error = await loadTeamFeed(TEAM_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('not-found');
	});

	it('throws a FeedLoadError on a 503, a network error, a non-JSON body and JSON without a code', async () => {
		await expect(
			loadTeamFeed(
				TEAM_URL,
				teamFetchAnswering(() => json({}, 503))
			)
		).rejects.toMatchObject({ reason: 'status' });
		await expect(
			loadTeamFeed(
				TEAM_URL,
				teamFetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')))
			)
		).rejects.toMatchObject({ reason: 'network' });
		await expect(
			loadTeamFeed(
				TEAM_URL,
				teamFetchAnswering(() => Promise.resolve(new Response('<html>', { status: 200 })))
			)
		).rejects.toMatchObject({ reason: 'body' });
		await expect(
			loadTeamFeed(
				TEAM_URL,
				teamFetchAnswering(() => json({ name: 'Thunder' }))
			)
		).rejects.toMatchObject({ reason: 'body' });
	});
});
