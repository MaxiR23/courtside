// web/tests/routes/game/[id]/+page.test.ts
//
// Tests for the game detail page.
//
// Tested:
// - Shows the search trigger in the nav
// - The route turns off prerender and server rendering
// - Loads the feed of the game in the URL and renders its header and tabs
// - Draws the shared nav with a Standings link to /standings and no current link
// - Shows the loading skeleton until the first load settles
// - Shows "Game not found." when the feed answers 404
// - Shows the data unavailable row on a network failure, a 503, a feed it cannot show, or with no URL configured
// - Polls again after 30 s while the game is live and after 60 s once it is not final but not live
// - Loads a final game once and sends no second request, also after the tab is visible again
// - Stops polling once a live game turns final
// - Pauses while the tab is hidden and loads at once when it is visible again
// - Keeps the last feed on screen when a later poll fails
// - Renders the win probability chart with "Even" for a feed built before the leader field
// - Links the header team names to /team/{code} in lowercase, box score and injured player names to /player/{id}
// - Shows an injured player's name as plain text for a feed without playerId
// - Renders no link inside a button or another link
// - The chart check targets the chart by role and name: absent without win probability points
// - The document title is "{away} at {home}" then the site name, in English and Spanish, with no score in any game status; Courtside while loading; the loading title in English and Spanish
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, tabs, footer
// - A recorded feed (tests/lib/feed/fixtures/game-detail.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/game/[id]/+page.test.ts"
//
// SEE: web/src/routes/game/[id]/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GameDetailFeed, Injury } from '../../../../src/lib/contract/game-detail';
import { preferLanguages } from '../../../prefer-languages';

import Page from '../../../../src/routes/game/[id]/+page.svelte';

const config = vi.hoisted(() => ({
	url: undefined as string | undefined,
	platform: undefined as string | undefined
}));
vi.mock('../../../../src/lib/feed/config', () => ({
	get gameDetailFeedUrl() {
		return config.url;
	},
	get videoPlatformName() {
		return config.platform;
	}
}));

const TEMPLATE = 'https://feeds.example.com/games/{id}.json';
const FEED_URL = 'https://feeds.example.com/games/401.json';
const recorded = (): GameDetailFeed =>
	JSON.parse(
		readFileSync(
			join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures', 'game-detail.json'),
			'utf8'
		)
	) as GameDetailFeed;
const finalGame = (): GameDetailFeed => ({ ...recorded(), status: 'final', winner: 'away' });

type Answer = () => Promise<unknown>;
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(feed: GameDetailFeed): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(feed) });
const answerStatus =
	(status: number): Answer =>
	() =>
		Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) });
const answerFailing: Answer = () => Promise.reject(new TypeError('Failed to fetch'));

function stubFetch(...next: Answer[]) {
	answers = next;
	fetchMock = vi.fn((url: string) => {
		if (url !== FEED_URL) throw new Error(`Unexpected URL ${url}`);
		const answer = answers.length > 1 ? answers.shift() : answers[0];
		return (answer as Answer)();
	});
	vi.stubGlobal('fetch', fetchMock);
}

async function settle() {
	await vi.advanceTimersByTimeAsync(0);
	await tick();
}

async function renderPage() {
	const result = render(Page, { props: { params: { id: '401' }, data: {} } });
	await settle();
	return result;
}

beforeEach(() => {
	document.title = '';
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-10-07T23:30:00Z'));
	config.url = TEMPLATE;
	config.platform = 'Video platform';
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('game detail route', () => {
	it('turns off prerender and server rendering for this route', async () => {
		const options = await import('../../../../src/routes/game/[id]/+page');
		expect(options.prerender).toBe(false);
		expect(options.ssr).toBe(false);
	});
});

describe('game detail page', () => {
	it('loads the feed of the game in the URL and renders its header and tabs', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][0]).toBe(FEED_URL);
		expect(screen.getAllByRole('heading', { level: 1 }).map((h) => h.textContent)).toEqual([
			'Lakers',
			'Warriors'
		]);
		expect(screen.getByText('Q3 · 4:12 · Chase Center')).toBeTruthy();
		const nav = screen.getByRole('navigation', { name: 'Sections' });
		expect([...nav.querySelectorAll('a')].map((a) => a.textContent)).toEqual([
			'Score',
			'Win prob.',
			'Box score',
			'Injuries'
		]);
		expect(container.querySelector('.mini-score')).not.toBeNull();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('draws the shared nav with a Standings link and no current link', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
		expect(document.querySelector('[aria-current="page"]:not(nav[aria-label] *)')).toBeNull();
	});

	it('shows the search trigger in the nav', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
	});

	it('shows the loading skeleton until the first load settles', async () => {
		let finish: (answer: unknown) => void = () => {};
		stubFetch(() => new Promise((resolve) => (finish = resolve)));
		const { container } = await renderPage();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.section-skeleton')).not.toBeNull();
		finish({ ok: true, status: 200, json: () => Promise.resolve(recorded()) });
		await settle();
		expect(container.querySelector('.section-skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(screen.getByText('Q3 · 4:12 · Chase Center')).toBeTruthy();
	});

	it('shows "Game not found." when the feed answers 404', async () => {
		stubFetch(answerStatus(404));
		await renderPage();
		expect(screen.getByText('Game not found.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'All games' })).toHaveLength(2);
		expect(screen.queryByText("Data isn't available right now. Check back later.")).toBeNull();
	});

	it('shows the data unavailable row on a network failure, a 503, a feed it cannot show, or with no URL configured', async () => {
		const unavailable = "Data isn't available right now. Check back later.";
		stubFetch(answerFailing);
		const network = await renderPage();
		expect(screen.getByText(unavailable)).toBeTruthy();
		network.unmount();

		stubFetch(answerStatus(503));
		const status = await renderPage();
		expect(screen.getByText(unavailable)).toBeTruthy();
		expect(screen.queryByText('Game not found.')).toBeNull();
		status.unmount();

		stubFetch(answerWith({ ...recorded(), score: null } as unknown as GameDetailFeed));
		const rejected = await renderPage();
		expect(screen.getByText(unavailable)).toBeTruthy();
		rejected.unmount();

		config.url = undefined;
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(unavailable)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('polls again after 30 s while the game is live and after 60 s once it is not', async () => {
		stubFetch(answerWith(recorded()), answerWith({ ...recorded(), status: 'delayed' }));
		await renderPage();
		await vi.advanceTimersByTimeAsync(29_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await tick();
		await vi.advanceTimersByTimeAsync(59_999);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(3);
	});

	it('loads a final game once and sends no second request, also after the tab becomes visible again', async () => {
		const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
		stubFetch(answerWith(finalGame()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		state.mockReturnValue('hidden');
		document.dispatchEvent(new Event('visibilitychange'));
		state.mockReturnValue('visible');
		document.dispatchEvent(new Event('visibilitychange'));
		await settle();
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('stops polling once a live game turns final', async () => {
		stubFetch(answerWith(recorded()), answerWith(finalGame()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('pauses while the tab is hidden and loads at once when it is visible again', async () => {
		const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
		stubFetch(answerWith(recorded()));
		await renderPage();
		state.mockReturnValue('hidden');
		document.dispatchEvent(new Event('visibilitychange'));
		await vi.advanceTimersByTimeAsync(5 * 60_000);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		state.mockReturnValue('visible');
		document.dispatchEvent(new Event('visibilitychange'));
		await settle();
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('keeps the last feed on screen when a later poll fails', async () => {
		stubFetch(answerWith(recorded()), answerFailing);
		await renderPage();
		await vi.advanceTimersByTimeAsync(30_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByText('Q3 · 4:12 · Chase Center')).toBeTruthy();
		expect(screen.queryByText("Data isn't available right now. Check back later.")).toBeNull();
	});

	it('renders the win probability chart with "Even" for a feed built before the leader field', async () => {
		const old: Partial<GameDetailFeed> = { ...recorded() };
		delete old.winProbabilityLeader;
		stubFetch(answerWith(old as unknown as GameDetailFeed));
		await renderPage();
		expect(screen.getByRole('heading', { name: 'Win probability' })).toBeTruthy();
		expect(screen.getByText('Even')).toBeTruthy();
		expect(screen.getByRole('img', { name: 'Win probability' })).toBeTruthy();
		expect(screen.queryByText("Data isn't available right now. Check back later.")).toBeNull();
	});

	it('draws no win probability chart for a feed without win probability points', async () => {
		stubFetch(answerWith({ ...recorded(), winProbability: null }));
		await renderPage();
		expect(screen.queryByRole('img', { name: 'Win probability' })).toBeNull();
	});

	it('links the header team names to /team/{code} in lowercase', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const names = [...container.querySelectorAll('h1 a')];
		expect(names.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
			['Lakers', '/team/lal'],
			['Warriors', '/team/gsw']
		]);
	});

	it('links box score player names to /player/{id}', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('link', { name: 'LeBron James' }).getAttribute('href')).toBe(
			'/player/p-LAL'
		);
	});

	it("links the injured player's name to /player/{id}", async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('link', { name: 'Austin Reaves' }).getAttribute('href')).toBe(
			'/player/4066457'
		);
	});

	it("shows the injured player's name as plain text for a feed without playerId", async () => {
		const old = recorded();
		const injury: Partial<Injury> = { ...old.injuries!.away![0] };
		delete injury.playerId;
		old.injuries!.away![0] = injury as Injury;
		stubFetch(answerWith(old));
		await renderPage();
		expect(screen.getByText('Austin Reaves')).toBeTruthy();
		expect(screen.queryByRole('link', { name: 'Austin Reaves' })).toBeNull();
	});

	it('renders no link inside a button or another link', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(container.querySelectorAll('button a, a a')).toHaveLength(0);
	});
});

describe('game document title', () => {
	const named = (): GameDetailFeed => {
		const source = recorded();
		return {
			...source,
			away: { ...source.away, name: 'Comets' },
			home: { ...source.home, name: 'Harbors' }
		};
	};

	it('is the away team at the home team, in English and Spanish', async () => {
		stubFetch(answerWith(named()));
		await renderPage();
		expect(document.title).toBe('Comets at Harbors · Courtside');
		preferLanguages(['es']);
		stubFetch(answerWith(named()));
		await renderPage();
		expect(document.title).toBe('Comets en Harbors · Courtside');
	});

	it('is the site name while loading', async () => {
		stubFetch(() => new Promise(() => {}));
		await renderPage();
		expect(document.title).toBe('Courtside');
	});

	it('is the site name while loading, in Spanish', async () => {
		preferLanguages(['es']);
		stubFetch(() => new Promise(() => {}));
		await renderPage();
		expect(document.title).toBe('Courtside');
	});

	it.each([
		['scheduled', null],
		['live', null],
		['final', 'away'],
		['delayed', null],
		['postponed', null],
		['canceled', null]
	] as const)('never contains the score when the game is %s', async (status, winner) => {
		const feed = { ...named(), status, winner };
		stubFetch(answerWith(feed));
		await renderPage();
		expect(document.title).toBe('Comets at Harbors · Courtside');
		expect(document.title).not.toContain(String(feed.score!.away));
		expect(document.title).not.toContain(String(feed.score!.home));
	});
});
