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
// - loadStandingsFeed returns the standings feed and reports 503, 404, network and body failures
// - loadCupFeed returns the Cup feed and reports 503, network and body failures
// - loadPlayoffsFeed returns the playoffs feed and reports 503, network and body failures
// - loadPlayoffsFinalsFeed returns the finals feed, reports a 404 as not-found and every other failure
// - loadAllStarFeed returns the All-Star feed and reports 503, network and body failures
// - cupMatchupFeedUrl puts the encoded slot id in place of every {id}
// - loadCupMatchupFeed returns the matchup feed with a no-cache request, reports a 404 as not-found and every other failure
// - loadSearchFeed returns the search feed with a no-cache request and reports 503, network and body failures
// - playerFeedUrl puts the encoded player id in place of {id}
// - loadPlayerFeed returns the player feed, reports a 404 as not-found and every other failure
// - calendarFeedUrl and dayFeedUrl put the encoded season or date in place of every placeholder
// - loadCalendarFeed and loadDayFeed return the feed, report a 404 as not-found, a 503 as status, a network failure and a bad shape as body
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
	loadPlayerFeed,
	loadPlayoffsFeed,
	loadAllStarFeed,
	loadPlayoffsFinalsFeed,
	loadSearchFeed,
	loadCupFeed,
	loadCupMatchupFeed,
	cupMatchupFeedUrl,
	loadStandingsFeed,
	playerFeedUrl,
	loadTeamFeed,
	teamFeedUrl,
	calendarFeedUrl,
	dayFeedUrl,
	loadCalendarFeed,
	loadDayFeed
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

const PLAYER_TEMPLATE = 'https://feeds.example.com/players/{id}.json';
const PLAYER_URL = 'https://feeds.example.com/players/p-2.json';

function playerFetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== PLAYER_URL) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('playerFeedUrl', () => {
	it('builds the player feed URL by putting the encoded id in place of {id}', () => {
		expect(playerFeedUrl(PLAYER_TEMPLATE, 'p-2')).toBe(PLAYER_URL);
		expect(playerFeedUrl(PLAYER_TEMPLATE, 'a/b c')).toBe(
			'https://feeds.example.com/players/a%2Fb%20c.json'
		);
	});
});

describe('loadPlayerFeed', () => {
	it('returns the parsed player feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { id: 'p-2', lastName: 'Gilgeous-Alexander' };
		const fetchFn = playerFetchAnswering(() => json(feed));
		await expect(loadPlayerFeed(PLAYER_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(PLAYER_URL, { headers: { accept: 'application/json' } });
	});

	it('throws a not-found FeedLoadError when the player feed answers 404', async () => {
		const fetchFn = playerFetchAnswering(() => json({ detail: 'no player' }, 404));
		const error = await loadPlayerFeed(PLAYER_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('not-found');
	});

	it('throws a FeedLoadError on a 503, a network error, a non-JSON body and JSON without an id', async () => {
		await expect(
			loadPlayerFeed(
				PLAYER_URL,
				playerFetchAnswering(() => json({}, 503))
			)
		).rejects.toMatchObject({ reason: 'status' });
		await expect(
			loadPlayerFeed(
				PLAYER_URL,
				playerFetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')))
			)
		).rejects.toMatchObject({ reason: 'network' });
		await expect(
			loadPlayerFeed(
				PLAYER_URL,
				playerFetchAnswering(() => Promise.resolve(new Response('<html>', { status: 200 })))
			)
		).rejects.toMatchObject({ reason: 'body' });
		await expect(
			loadPlayerFeed(
				PLAYER_URL,
				playerFetchAnswering(() => json({ lastName: 'X' }))
			)
		).rejects.toMatchObject({ reason: 'body' });
	});
});

const STANDINGS_URL = 'https://feeds.example.com/standings.json';

function standingsFetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== STANDINGS_URL) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('loadStandingsFeed', () => {
	it('returns the parsed standings feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { season: '2025-26', conferences: [], divisions: [] };
		const fetchFn = standingsFetchAnswering(() => json(feed));
		await expect(loadStandingsFeed(STANDINGS_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(STANDINGS_URL, {
			headers: { accept: 'application/json' }
		});
	});

	it('throws a status error on a 503 and on a 404', async () => {
		for (const status of [503, 404]) {
			const fetchFn = standingsFetchAnswering(() => json({ detail: 'no' }, status));
			await expect(loadStandingsFeed(STANDINGS_URL, fetchFn)).rejects.toMatchObject({
				name: 'FeedLoadError',
				reason: 'status'
			});
		}
	});

	it('throws a network error', async () => {
		const fetchFn = standingsFetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')));
		const error = await loadStandingsFeed(STANDINGS_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('network');
	});

	it('throws a body error on a non-JSON body and on JSON without conferences', async () => {
		const html = standingsFetchAnswering(() =>
			Promise.resolve(new Response('<html>', { status: 200 }))
		);
		await expect(loadStandingsFeed(STANDINGS_URL, html)).rejects.toMatchObject({ reason: 'body' });
		const empty = standingsFetchAnswering(() => json({ season: 'x' }));
		await expect(loadStandingsFeed(STANDINGS_URL, empty)).rejects.toMatchObject({
			reason: 'body'
		});
	});
});

const CUP_URL = 'https://feeds.example.com/cup.json';

function cupFetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== CUP_URL) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('loadCupFeed', () => {
	it('returns the parsed Cup feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { season: '2026', stages: [], groups: [] };
		const fetchFn = cupFetchAnswering(() => json(feed));
		await expect(loadCupFeed(CUP_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(CUP_URL, {
			headers: { accept: 'application/json' }
		});
	});

	it('throws a status error on a 503', async () => {
		const fetchFn = cupFetchAnswering(() => json({ detail: 'no' }, 503));
		await expect(loadCupFeed(CUP_URL, fetchFn)).rejects.toMatchObject({
			name: 'FeedLoadError',
			reason: 'status'
		});
	});

	it('throws a network error', async () => {
		const fetchFn = cupFetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')));
		const error = await loadCupFeed(CUP_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('network');
	});

	it('throws a body error on a non-JSON body and on JSON without stages or groups', async () => {
		const html = cupFetchAnswering(() => Promise.resolve(new Response('<html>', { status: 200 })));
		await expect(loadCupFeed(CUP_URL, html)).rejects.toMatchObject({ reason: 'body' });
		const empty = cupFetchAnswering(() => json({ season: 'x' }));
		await expect(loadCupFeed(CUP_URL, empty)).rejects.toMatchObject({ reason: 'body' });
		const noGroups = cupFetchAnswering(() => json({ stages: [] }));
		await expect(loadCupFeed(CUP_URL, noGroups)).rejects.toMatchObject({ reason: 'body' });
	});
});

const PLAYOFFS_URL = 'https://feeds.example.com/playoffs.json';
const FINALS_URL = 'https://feeds.example.com/playoffs/finals.json';

function urlFetchAnswering(expected: string, answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== expected) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('loadPlayoffsFeed', () => {
	it('returns the parsed playoffs feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { season: '2026', stages: [], bracket: [] };
		const fetchFn = urlFetchAnswering(PLAYOFFS_URL, () => json(feed));
		await expect(loadPlayoffsFeed(PLAYOFFS_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(PLAYOFFS_URL, {
			headers: { accept: 'application/json' }
		});
	});

	it('throws a status error on a 503', async () => {
		const fetchFn = urlFetchAnswering(PLAYOFFS_URL, () => json({ detail: 'no' }, 503));
		await expect(loadPlayoffsFeed(PLAYOFFS_URL, fetchFn)).rejects.toMatchObject({
			name: 'FeedLoadError',
			reason: 'status'
		});
	});

	it('throws a network error', async () => {
		const fetchFn = urlFetchAnswering(PLAYOFFS_URL, () =>
			Promise.reject(new TypeError('Failed to fetch'))
		);
		const error = await loadPlayoffsFeed(PLAYOFFS_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('network');
	});

	it('throws a body error on a non-JSON body and on JSON without stages or bracket', async () => {
		const html = urlFetchAnswering(PLAYOFFS_URL, () =>
			Promise.resolve(new Response('<html>', { status: 200 }))
		);
		await expect(loadPlayoffsFeed(PLAYOFFS_URL, html)).rejects.toMatchObject({ reason: 'body' });
		const empty = urlFetchAnswering(PLAYOFFS_URL, () => json({ season: 'x' }));
		await expect(loadPlayoffsFeed(PLAYOFFS_URL, empty)).rejects.toMatchObject({ reason: 'body' });
		const noBracket = urlFetchAnswering(PLAYOFFS_URL, () => json({ stages: [] }));
		await expect(loadPlayoffsFeed(PLAYOFFS_URL, noBracket)).rejects.toMatchObject({
			reason: 'body'
		});
	});
});

describe('loadPlayoffsFinalsFeed', () => {
	it('returns the parsed finals feed on a 200', async () => {
		const feed = { season: '2026', games: [], road: [] };
		const fetchFn = urlFetchAnswering(FINALS_URL, () => json(feed));
		await expect(loadPlayoffsFinalsFeed(FINALS_URL, fetchFn)).resolves.toEqual(feed);
	});

	it('reports a 404 as not-found', async () => {
		const fetchFn = urlFetchAnswering(FINALS_URL, () => json({ detail: 'no' }, 404));
		await expect(loadPlayoffsFinalsFeed(FINALS_URL, fetchFn)).rejects.toMatchObject({
			reason: 'not-found'
		});
	});

	it('throws a status error on a 503', async () => {
		const fetchFn = urlFetchAnswering(FINALS_URL, () => json({ detail: 'no' }, 503));
		await expect(loadPlayoffsFinalsFeed(FINALS_URL, fetchFn)).rejects.toMatchObject({
			reason: 'status'
		});
	});

	it('throws a network error', async () => {
		const fetchFn = urlFetchAnswering(FINALS_URL, () =>
			Promise.reject(new TypeError('Failed to fetch'))
		);
		await expect(loadPlayoffsFinalsFeed(FINALS_URL, fetchFn)).rejects.toMatchObject({
			reason: 'network'
		});
	});

	it('throws a body error on JSON without games or road', async () => {
		const empty = urlFetchAnswering(FINALS_URL, () => json({ season: 'x' }));
		await expect(loadPlayoffsFinalsFeed(FINALS_URL, empty)).rejects.toMatchObject({
			reason: 'body'
		});
		const noRoad = urlFetchAnswering(FINALS_URL, () => json({ games: [] }));
		await expect(loadPlayoffsFinalsFeed(FINALS_URL, noRoad)).rejects.toMatchObject({
			reason: 'body'
		});
	});
});

const ALL_STAR_URL = 'https://feeds.example.com/all-star.json';

describe('loadAllStarFeed', () => {
	it('returns the parsed All-Star feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { year: 2027, state: 'before', edition: { games: [] } };
		const fetchFn = urlFetchAnswering(ALL_STAR_URL, () => json(feed));
		await expect(loadAllStarFeed(ALL_STAR_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(ALL_STAR_URL, {
			headers: { accept: 'application/json' }
		});
	});

	it('throws a status error on a 503 and on a 404', async () => {
		for (const status of [503, 404]) {
			const fetchFn = urlFetchAnswering(ALL_STAR_URL, () => json({ detail: 'no' }, status));
			await expect(loadAllStarFeed(ALL_STAR_URL, fetchFn)).rejects.toMatchObject({
				name: 'FeedLoadError',
				reason: 'status'
			});
		}
	});

	it('throws a network error', async () => {
		const fetchFn = urlFetchAnswering(ALL_STAR_URL, () =>
			Promise.reject(new TypeError('Failed to fetch'))
		);
		await expect(loadAllStarFeed(ALL_STAR_URL, fetchFn)).rejects.toMatchObject({
			reason: 'network'
		});
	});

	it('throws a body error on a non-JSON body and on JSON without a state or edition games', async () => {
		const html = urlFetchAnswering(ALL_STAR_URL, () =>
			Promise.resolve(new Response('<html>', { status: 200 }))
		);
		await expect(loadAllStarFeed(ALL_STAR_URL, html)).rejects.toMatchObject({ reason: 'body' });
		for (const body of [
			null,
			'x',
			{ year: 1 },
			{ state: 'live' },
			{ state: 'live', edition: null }
		]) {
			const bad = urlFetchAnswering(ALL_STAR_URL, () => json(body));
			await expect(loadAllStarFeed(ALL_STAR_URL, bad)).rejects.toMatchObject({ reason: 'body' });
		}
		const noGames = urlFetchAnswering(ALL_STAR_URL, () =>
			json({ state: 'live', edition: { teams: [] } })
		);
		await expect(loadAllStarFeed(ALL_STAR_URL, noGames)).rejects.toMatchObject({ reason: 'body' });
	});
});

const MATCHUP_TEMPLATE = 'https://feeds.example.com/cup/matchups/{id}.json';
const MATCHUP_URL = 'https://feeds.example.com/cup/matchups/final.json';

function matchupFetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== MATCHUP_URL) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('cupMatchupFeedUrl', () => {
	it('puts the encoded id in place of every {id}', () => {
		expect(cupMatchupFeedUrl(MATCHUP_TEMPLATE, 'final')).toBe(MATCHUP_URL);
		expect(cupMatchupFeedUrl(MATCHUP_TEMPLATE, 'a/b c')).toBe(
			'https://feeds.example.com/cup/matchups/a%2Fb%20c.json'
		);
		expect(cupMatchupFeedUrl('https://feeds.example.com/{id}/{id}.json', 'x')).toBe(
			'https://feeds.example.com/x/x.json'
		);
	});
});

describe('loadCupMatchupFeed', () => {
	it('returns the parsed feed, asking the browser to revalidate on every request', async () => {
		const feed = { id: 'final', top: {}, bottom: {} };
		const fetchFn = matchupFetchAnswering(() => json(feed));
		await expect(loadCupMatchupFeed(MATCHUP_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(MATCHUP_URL, {
			cache: 'no-cache',
			headers: { accept: 'application/json' }
		});
	});

	it('throws a not-found error on a 404', async () => {
		const fetchFn = matchupFetchAnswering(() => json({ detail: 'no' }, 404));
		await expect(loadCupMatchupFeed(MATCHUP_URL, fetchFn)).rejects.toMatchObject({
			reason: 'not-found'
		});
	});

	it('throws a status error on a 503 and a network error on a failed request', async () => {
		await expect(
			loadCupMatchupFeed(
				MATCHUP_URL,
				matchupFetchAnswering(() => json({}, 503))
			)
		).rejects.toMatchObject({ name: 'FeedLoadError', reason: 'status' });
		await expect(
			loadCupMatchupFeed(
				MATCHUP_URL,
				matchupFetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')))
			)
		).rejects.toMatchObject({ reason: 'network' });
	});

	it('throws a body error on a non-JSON body and on JSON without an id or sides', async () => {
		const html = matchupFetchAnswering(() =>
			Promise.resolve(new Response('<html>', { status: 200 }))
		);
		await expect(loadCupMatchupFeed(MATCHUP_URL, html)).rejects.toMatchObject({ reason: 'body' });
		for (const body of [
			{ top: {}, bottom: {} },
			{ id: 'final', top: {} },
			{ id: 'final', top: null, bottom: {} },
			null
		]) {
			await expect(
				loadCupMatchupFeed(
					MATCHUP_URL,
					matchupFetchAnswering(() => json(body))
				)
			).rejects.toMatchObject({ reason: 'body' });
		}
	});
});

const SEARCH_URL = 'https://feeds.example.com/search.json';

function searchFetchAnswering(answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== SEARCH_URL) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('loadSearchFeed', () => {
	it('returns the parsed feed, asking the browser to revalidate on every request', async () => {
		const feed = { teams: [], players: [] };
		const fetchFn = searchFetchAnswering(() => json(feed));
		await expect(loadSearchFeed(SEARCH_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(SEARCH_URL, {
			cache: 'no-cache',
			headers: { accept: 'application/json' }
		});
	});

	it('throws a status error on a 503', async () => {
		const fetchFn = searchFetchAnswering(() => json({ detail: 'no' }, 503));
		await expect(loadSearchFeed(SEARCH_URL, fetchFn)).rejects.toMatchObject({
			name: 'FeedLoadError',
			reason: 'status'
		});
	});

	it('throws a network error', async () => {
		const fetchFn = searchFetchAnswering(() => Promise.reject(new TypeError('Failed to fetch')));
		const error = await loadSearchFeed(SEARCH_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('network');
	});

	it('throws a body error on a non-JSON body and on JSON without the arrays', async () => {
		const html = searchFetchAnswering(() =>
			Promise.resolve(new Response('<html>', { status: 200 }))
		);
		await expect(loadSearchFeed(SEARCH_URL, html)).rejects.toMatchObject({ reason: 'body' });
		const noPlayers = searchFetchAnswering(() => json({ teams: [] }));
		await expect(loadSearchFeed(SEARCH_URL, noPlayers)).rejects.toMatchObject({ reason: 'body' });
		const noTeams = searchFetchAnswering(() => json({ players: [] }));
		await expect(loadSearchFeed(SEARCH_URL, noTeams)).rejects.toMatchObject({ reason: 'body' });
	});
});

const CALENDAR_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CALENDAR_URL = 'https://feeds.example.com/seasons/1999/calendar.json';
const DAY_TEMPLATE = 'https://feeds.example.com/days/{date}.json';
const DAY_URL = 'https://feeds.example.com/days/1999-02-05.json';

function fetchAt(expected: string, answer: () => Promise<Response>) {
	return vi.fn((url: string | URL | Request) => {
		if (url !== expected) throw new Error(`Unexpected URL ${String(url)}`);
		return answer();
	}) as unknown as typeof fetch & ReturnType<typeof vi.fn>;
}

describe('calendarFeedUrl and dayFeedUrl', () => {
	it('put the encoded value in place of every placeholder', () => {
		expect(calendarFeedUrl(CALENDAR_TEMPLATE, '1999')).toBe(CALENDAR_URL);
		expect(calendarFeedUrl(CALENDAR_TEMPLATE, 'current')).toBe(
			'https://feeds.example.com/seasons/current/calendar.json'
		);
		expect(calendarFeedUrl('https://feeds.example.com/{season}/{season}', 'a/b')).toBe(
			'https://feeds.example.com/a%2Fb/a%2Fb'
		);
		expect(dayFeedUrl(DAY_TEMPLATE, '1999-02-05')).toBe(DAY_URL);
		expect(dayFeedUrl('https://feeds.example.com/{date}/{date}', 'a b')).toBe(
			'https://feeds.example.com/a%20b/a%20b'
		);
	});
});

describe('loadCalendarFeed', () => {
	it('returns the parsed feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { season: 1999, days: ['1999-02-05'], seasons: [{ season: 1999 }] };
		const fetchFn = fetchAt(CALENDAR_URL, () => json(feed));
		await expect(loadCalendarFeed(CALENDAR_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(CALENDAR_URL, {
			headers: { accept: 'application/json' }
		});
	});

	it('reports a 404 as not-found', async () => {
		const fetchFn = fetchAt(CALENDAR_URL, () => json({ detail: 'no season' }, 404));
		const error = await loadCalendarFeed(CALENDAR_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('not-found');
	});

	it('reports a 503, a network failure and a bad shape', async () => {
		await expect(
			loadCalendarFeed(
				CALENDAR_URL,
				fetchAt(CALENDAR_URL, () => json({}, 503))
			)
		).rejects.toMatchObject({ reason: 'status' });
		await expect(
			loadCalendarFeed(
				CALENDAR_URL,
				fetchAt(CALENDAR_URL, () => Promise.reject(new TypeError('Failed to fetch')))
			)
		).rejects.toMatchObject({ reason: 'network' });
		await expect(
			loadCalendarFeed(
				CALENDAR_URL,
				fetchAt(CALENDAR_URL, () => json({ days: [] }))
			)
		).rejects.toMatchObject({ reason: 'body' });
		await expect(
			loadCalendarFeed(
				CALENDAR_URL,
				fetchAt(CALENDAR_URL, () => json(null))
			)
		).rejects.toMatchObject({ reason: 'body' });
	});
});

describe('loadDayFeed', () => {
	it('returns the parsed feed on a 200, asking for JSON from the given URL', async () => {
		const feed = { season: 1999, day: { date: '1999-02-05', games: [] } };
		const fetchFn = fetchAt(DAY_URL, () => json(feed));
		await expect(loadDayFeed(DAY_URL, fetchFn)).resolves.toEqual(feed);
		expect(fetchFn).toHaveBeenCalledWith(DAY_URL, { headers: { accept: 'application/json' } });
	});

	it('reports a 404 as not-found', async () => {
		const fetchFn = fetchAt(DAY_URL, () => json({ detail: 'no day' }, 404));
		const error = await loadDayFeed(DAY_URL, fetchFn).catch((e: unknown) => e);
		expect(error).toBeInstanceOf(FeedLoadError);
		expect((error as FeedLoadError).reason).toBe('not-found');
	});

	it('reports a 503, a network failure and a bad shape', async () => {
		await expect(
			loadDayFeed(
				DAY_URL,
				fetchAt(DAY_URL, () => json({}, 503))
			)
		).rejects.toMatchObject({ reason: 'status' });
		await expect(
			loadDayFeed(
				DAY_URL,
				fetchAt(DAY_URL, () => Promise.reject(new TypeError('Failed to fetch')))
			)
		).rejects.toMatchObject({ reason: 'network' });
		await expect(
			loadDayFeed(
				DAY_URL,
				fetchAt(DAY_URL, () => json({ day: {} }))
			)
		).rejects.toMatchObject({ reason: 'body' });
		await expect(
			loadDayFeed(
				DAY_URL,
				fetchAt(DAY_URL, () => json(null))
			)
		).rejects.toMatchObject({ reason: 'body' });
	});
});
