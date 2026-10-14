// web/tests/routes/all-star/+page.test.ts
//
// Tests for the All-Star route.
//
// Tested:
// - The route turns off server rendering and keeps prerender from the layout
// - Shows the search trigger in the nav and All-Star as the current page with href /all-star
// - Loads the All-Star feed and renders the before, live and after states from their recorded feeds
// - Shows the skeleton until the first load settles
// - Shows the data unavailable row on a 503, a network failure, or with no URL configured
// - After a 503 it polls again at 60 s and renders the page when that load succeeds
// - A live feed polls again at 30 s and the new clock shows
// - Pauses polling while the tab is hidden and loads at once when visible again
// - Keeps the last feed on screen when a later poll fails
// - Renders in Spanish
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, sections, footer
// - Recorded feeds (tests/lib/feed/fixtures/all-star-*.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/all-star/+page.test.ts
//
// SEE: web/src/routes/all-star/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { AllStarFeed } from '../../../src/lib/contract/all-star';
import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/all-star/+page.svelte';

const config = vi.hoisted(() => ({ url: undefined as string | undefined }));
vi.mock('../../../src/lib/feed/config', () => ({
	get allStarFeedUrl() {
		return config.url;
	}
}));

const FEED_URL = 'https://feeds.example.com/all-star.json';
const fixture = (name: 'before' | 'live' | 'after'): AllStarFeed =>
	JSON.parse(
		readFileSync(
			join(__dirname, '..', '..', 'lib', 'feed', 'fixtures', `all-star-${name}.json`),
			'utf8'
		)
	);

const UNAVAILABLE = "Data isn't available right now. Check back later.";

type Answer = () => Promise<unknown>;
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(body: unknown): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
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
	const result = render(Page);
	await settle();
	return result;
}

const ids = (container: HTMLElement) =>
	[...container.querySelectorAll('.sections > section')].map((s) => s.id);

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2027-02-14T23:30:00Z'));
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }))
	);
	config.url = FEED_URL;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('All-Star route', () => {
	it('turns off server rendering and inherits prerender from the layout', async () => {
		const options = await import('../../../src/routes/all-star/+page');
		expect(options.ssr).toBe(false);
		expect((options as { prerender?: boolean }).prerender).toBeUndefined();
	});
});

describe('All-Star page', () => {
	it('shows the search trigger in the nav and All-Star as the current page', async () => {
		stubFetch(answerWith(fixture('after')));
		await renderPage();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
		const link = screen.getByRole('link', { name: 'All-Star' });
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(link.getAttribute('href')).toBe('/all-star');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
	});

	it('renders the before state with Last time and the link to the previous edition', async () => {
		stubFetch(answerWith(fixture('before')));
		const { container } = await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][0]).toBe(FEED_URL);
		expect(screen.getByText('Next edition')).toBeTruthy();
		expect(ids(container)).toEqual(['last-time']);
		expect(
			screen
				.getByRole('link', { name: /Every game, box score and highlight from 2026/ })
				.getAttribute('href')
		).toBe('/all-star/previous');
		expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
	});

	it('renders the live state', async () => {
		stubFetch(answerWith(fixture('live')));
		const { container } = await renderPage();
		expect(screen.getByText('Live now', { selector: '.kicker' })).toBeTruthy();
		expect(ids(container)).toEqual(['games', 'teams']);
		expect(container.querySelector('.clock')?.textContent).toBe('5:12');
	});

	it('renders the after state with the champion, the MVP and the games', async () => {
		stubFetch(answerWith(fixture('after')));
		const { container } = await renderPage();
		expect(screen.getByRole('heading', { level: 1, name: 'Team Stripes' })).toBeTruthy();
		expect(ids(container)).toEqual(['mvp', 'games', 'teams']);
		expect(container.querySelectorAll('.game-card')).toHaveLength(4);
	});

	it('shows the skeleton until the first load settles', async () => {
		let finish: (answer: unknown) => void = () => {};
		stubFetch(() => new Promise((resolve) => (finish = resolve)));
		const { container } = await renderPage();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('section[aria-busy=true]')).not.toBeNull();
		finish({ ok: true, status: 200, json: () => Promise.resolve(fixture('after')) });
		await settle();
		expect(container.querySelector('section[aria-busy=true]')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
	});

	it('shows the data unavailable row on a network failure, a 503, or with no URL configured', async () => {
		stubFetch(answerFailing);
		const network = await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		network.unmount();

		stubFetch(answerStatus(503));
		const status = await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		status.unmount();

		config.url = undefined;
		stubFetch(answerWith(fixture('after')));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('keeps polling after a 503 and renders the page when a later load succeeds', async () => {
		stubFetch(answerStatus(503), answerWith(fixture('after')));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByRole('heading', { level: 1, name: 'Team Stripes' })).toBeTruthy();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('polls every 60 s when not live', async () => {
		stubFetch(answerWith(fixture('after')));
		await renderPage();
		await vi.advanceTimersByTimeAsync(59_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('polls every 30 s while live and shows the new clock', async () => {
		const next = fixture('live');
		next.edition.games[1].clock = '4:41';
		stubFetch(answerWith(fixture('live')), answerWith(next));
		const { container } = await renderPage();
		expect(container.querySelector('.clock')?.textContent).toBe('5:12');
		await vi.advanceTimersByTimeAsync(29_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(container.querySelector('.clock')?.textContent).toBe('4:41');
	});

	it('pauses while the tab is hidden and loads at once when it is visible again', async () => {
		const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
		stubFetch(answerWith(fixture('after')));
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
		stubFetch(answerWith(fixture('after')), answerFailing);
		await renderPage();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByRole('heading', { level: 1, name: 'Team Stripes' })).toBeTruthy();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es-ES']);
		stubFetch(answerWith(fixture('after')));
		await renderPage();
		expect(screen.getByText('Campeones del día')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
		expect(screen.getByText('Partidos', { selector: 'h2' })).toBeTruthy();
	});
});
