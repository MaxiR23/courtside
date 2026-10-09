// web/tests/routes/player/[id]/+page.test.ts
//
// Tests for the player page.
//
// Tested:
// - Shows the search trigger in the nav
// - The route turns off prerender and server rendering
// - Loads the feed of the player id in the URL and renders the h1, every section and the tabs
// - Links a game only where the feed has its detail
// - Shows the loading skeleton until the first load settles
// - Shows "Player not found." on a 404
// - Shows the data unavailable row on a network failure, a 503, or with no URL configured
// - After a 503 it polls again at 60 s and renders the player when that load succeeds
// - Polls every 60 s with live null; every 30 s while live is set, the live card replacing the
//   next game card, slowing to 60 s once a load returns live null
// - Pauses while the tab is hidden and loads at once when visible again
// - Keeps the last feed on screen when a later poll fails
// - Renders in English and in Spanish, including the live card with no line
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, tabs, footer
// - A recorded feed (tests/lib/feed/fixtures/player.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/player/[id]/+page.test.ts"
//
// SEE: web/src/routes/player/[id]/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayerFeed } from '../../../../src/lib/contract/player';
import { preferLanguages } from '../../../prefer-languages';

import Page from '../../../../src/routes/player/[id]/+page.svelte';

const config = vi.hoisted(() => ({ url: undefined as string | undefined }));
vi.mock('../../../../src/lib/feed/config', () => ({
	get playerFeedUrl() {
		return config.url;
	}
}));

const TEMPLATE = 'https://feeds.example.com/players/{id}.json';
const feedUrl = (id: string) => `https://feeds.example.com/players/${id}.json`;
const recorded = (): PlayerFeed =>
	JSON.parse(
		readFileSync(
			join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures', 'player.json'),
			'utf8'
		)
	) as PlayerFeed;

const withLive = (): PlayerFeed => {
	const source = recorded();
	source.live = {
		gameId: 'g-live',
		opponent: { code: 'DEN', name: null, city: null, guest: false },
		isHome: false,
		period: 3,
		clock: '4:12',
		teamScore: 78,
		opponentScore: 74,
		line: null
	};
	return source;
};

const UNAVAILABLE = "Data isn't available right now. Check back later.";

type Answer = () => Promise<unknown>;
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(feed: PlayerFeed): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(feed) });
const answerStatus =
	(status: number): Answer =>
	() =>
		Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) });
const answerFailing: Answer = () => Promise.reject(new TypeError('Failed to fetch'));

function stubFetch(id: string, ...next: Answer[]) {
	answers = next;
	fetchMock = vi.fn((url: string) => {
		if (url !== feedUrl(id)) throw new Error(`Unexpected URL ${url}`);
		const answer = answers.length > 1 ? answers.shift() : answers[0];
		return (answer as Answer)();
	});
	vi.stubGlobal('fetch', fetchMock);
}

async function settle() {
	await vi.advanceTimersByTimeAsync(0);
	await tick();
}

async function renderPage(id = 'p-2') {
	const result = render(Page, { props: { params: { id }, data: {} } });
	await settle();
	return result;
}

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-10-07T23:30:00Z'));
	config.url = TEMPLATE;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('player route', () => {
	it('turns off prerender and server rendering for this route', async () => {
		const options = await import('../../../../src/routes/player/[id]/+page');
		expect(options.prerender).toBe(false);
		expect(options.ssr).toBe(false);
	});
});

describe('player page', () => {
	it('loads the feed of the player in the URL and renders the header, sections and tabs', async () => {
		stubFetch('p-2', answerWith(recorded()));
		const { container } = await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][0]).toBe(feedUrl('p-2'));
		expect(screen.getByRole('heading', { level: 1, name: 'Gilgeous-Alexander' })).toBeTruthy();
		const nav = screen.getByRole('navigation', { name: 'Sections' });
		expect([...nav.querySelectorAll('a')].map((a) => a.textContent)).toEqual([
			'Profile',
			'Averages',
			'Seasons',
			'Milestones',
			'Game log',
			'Awards'
		]);
		expect([...container.querySelectorAll('.sections > section')].map((s) => s.id)).toEqual([
			'profile',
			'averages',
			'seasons',
			'milestones',
			'game-log',
			'awards'
		]);
		expect(container.querySelector('.mini-score')?.textContent).toBe('#2 S. Gilgeous-Alexander');
		expect(screen.getByRole('contentinfo')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		expect(document.querySelector('[aria-current="page"]:not(nav[aria-label] *)')).toBeNull();
	});

	it('links a game only where the feed has its detail', async () => {
		stubFetch('p-2', answerWith(recorded()));
		await renderPage();
		const links = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
		expect(links).toContain('/game/g-5');
		expect(links).not.toContain('/game/g-4');
		expect(links).not.toContain('/game/g-6');
	});

	it('shows the search trigger in the nav', async () => {
		stubFetch('p-2', answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
	});

	it('shows the loading skeleton until the first load settles', async () => {
		let finish: (answer: unknown) => void = () => {};
		stubFetch('p-2', () => new Promise((resolve) => (finish = resolve)));
		const { container } = await renderPage();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.section-skeleton')).not.toBeNull();
		finish({ ok: true, status: 200, json: () => Promise.resolve(recorded()) });
		await settle();
		expect(container.querySelector('.section-skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(screen.getByRole('heading', { level: 1, name: 'Gilgeous-Alexander' })).toBeTruthy();
	});

	it('shows "Player not found." on a 404', async () => {
		stubFetch('xyz', answerStatus(404));
		await renderPage('xyz');
		expect(fetchMock.mock.calls[0][0]).toBe(feedUrl('xyz'));
		expect(screen.getByText('Player not found.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'All games' })).toHaveLength(2);
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('shows the data unavailable row on a network failure, a 503, or with no URL configured', async () => {
		stubFetch('p-2', answerFailing);
		const network = await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		network.unmount();

		stubFetch('p-2', answerStatus(503));
		const status = await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.queryByText('Player not found.')).toBeNull();
		status.unmount();

		config.url = undefined;
		stubFetch('p-2', answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('keeps polling after a 503 and renders the player when a later load succeeds', async () => {
		stubFetch('p-2', answerStatus(503), answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByRole('heading', { level: 1, name: 'Gilgeous-Alexander' })).toBeTruthy();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('polls every 60 s with live null', async () => {
		stubFetch('p-2', answerWith(recorded()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(59_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(60_000);
		expect(fetchMock).toHaveBeenCalledTimes(3);
	});

	it('polls every 30 s while live, shows the live card, and slows to 60 s once live is null', async () => {
		stubFetch('p-2', answerWith(withLive()), answerWith(withLive()), answerWith(recorded()));
		await renderPage();
		expect(screen.getByText('LIVE')).toBeTruthy();
		expect(screen.queryByText('Next game')).toBeNull();
		await vi.advanceTimersByTimeAsync(29_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(3);
		await tick();
		expect(screen.queryByText('LIVE')).toBeNull();
		expect(screen.getByText('Next game')).toBeTruthy();
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(3);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(4);
	});

	it('pauses while the tab is hidden and loads at once when it is visible again', async () => {
		const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
		stubFetch('p-2', answerWith(recorded()));
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
		stubFetch('p-2', answerWith(recorded()), answerFailing);
		await renderPage();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByRole('heading', { level: 1, name: 'Gilgeous-Alexander' })).toBeTruthy();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('renders in Spanish, including the live card with no line', async () => {
		preferLanguages(['es']);
		stubFetch('p-2', answerWith(withLive()));
		await renderPage();
		const nav = screen.getByRole('navigation', { name: 'Secciones' });
		expect(nav.textContent).toContain('Perfil');
		expect(screen.getByText('Todavía no entró.')).toBeTruthy();
		expect(screen.getByText('41.º en la NBA')).toBeTruthy();
	});
});
