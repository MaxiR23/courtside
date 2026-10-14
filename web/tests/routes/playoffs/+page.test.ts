// web/tests/routes/playoffs/+page.test.ts
//
// Tests for the playoffs route.
//
// Tested:
// - The route turns off server rendering and keeps prerender from the layout
// - Shows the search trigger in the nav and Playoffs as the current page
// - Loads the playoffs feed and renders the picture state
// - Requests no finals feed in the picture, play-in and playoffs states
// - Loads the finals feed in the complete state and renders the hype sections
// - Hides only the finals sections when the finals feed answers 404 or 503
// - Shows the skeleton until the first load settles
// - Shows the data unavailable row on a 503, a network failure, or with no URL configured
// - After a 503 it polls again at 60 s and renders the page when that load succeeds
// - Pauses polling while the tab is hidden and loads at once when visible again
// - Keeps the last playoffs feed on screen when a later poll fails
// - Renders in Spanish
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, sections, footer
// - Recorded feeds (tests/lib/feed/fixtures/playoffs-*.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/playoffs/+page.test.ts
//
// SEE: web/src/routes/playoffs/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed, PlayoffsState } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/playoffs/+page.svelte';

const config = vi.hoisted(() => ({
	url: undefined as string | undefined,
	finals: undefined as string | undefined
}));
vi.mock('../../../src/lib/feed/config', () => ({
	get playoffsFeedUrl() {
		return config.url;
	},
	get playoffsFinalsFeedUrl() {
		return config.finals;
	}
}));

const FEED_URL = 'https://feeds.example.com/playoffs.json';
const FINALS_URL = 'https://feeds.example.com/playoffs/finals.json';
const fixture = <T>(file: string): T =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', 'lib', 'feed', 'fixtures', file), 'utf8')
	) as T;
const picture = () => fixture<PlayoffsFeed>('playoffs-picture.json');
const inState = (state: PlayoffsState): PlayoffsFeed => {
	const feed = fixture<PlayoffsFeed>('playoffs-complete.json');
	feed.state = state;
	if (state !== 'complete') feed.champion = null;
	if (state === 'playoffs') feed.currentRound = 1;
	return feed;
};

const UNAVAILABLE = "Data isn't available right now. Check back later.";

type Answer = () => Promise<unknown>;
let answers: Answer[];
let finalsAnswer: Answer;
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
	finalsAnswer = answerWith(fixture<PlayoffsFinalsFeed>('playoffs-finals.json'));
	fetchMock = vi.fn((url: string) => {
		if (url === FINALS_URL) return finalsAnswer();
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

const finalsCalls = () => fetchMock.mock.calls.filter((call) => call[0] === FINALS_URL);
const ids = (container: HTMLElement) =>
	[...container.querySelectorAll('.sections > section')].map((s) => s.id);

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2027-06-20T23:30:00Z'));
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }))
	);
	config.url = FEED_URL;
	config.finals = FINALS_URL;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('Playoffs route', () => {
	it('turns off server rendering and inherits prerender from the layout', async () => {
		const options = await import('../../../src/routes/playoffs/+page');
		expect(options.ssr).toBe(false);
		expect((options as { prerender?: boolean }).prerender).toBeUndefined();
	});
});

describe('Playoffs page', () => {
	it('shows the search trigger in the nav and Playoffs as the current page', async () => {
		stubFetch(answerWith(picture()));
		await renderPage();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
		const link = screen.getByRole('link', { name: 'Playoffs' });
		expect(link.getAttribute('aria-current')).toBe('page');
		expect(link.getAttribute('href')).toBe('/playoffs');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
	});

	it('loads the playoffs feed and renders the picture state', async () => {
		stubFetch(answerWith(picture()));
		const { container } = await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][0]).toBe(FEED_URL);
		expect(screen.getByRole('heading', { level: 1, name: 'Playoffs' })).toBeTruthy();
		expect(screen.getAllByText('Playoff picture').length).toBeGreaterThan(0);
		expect(ids(container)).toEqual(['picture', 'bracket', 'play-in', 'leaders', 'awards']);
		expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
	});

	it('requests no finals feed in the picture, play-in and playoffs states', async () => {
		for (const state of ['picture', 'playin', 'playoffs'] as const) {
			stubFetch(answerWith(state === 'picture' ? picture() : inState(state)));
			const { unmount } = await renderPage();
			expect(finalsCalls()).toHaveLength(0);
			unmount();
		}
	});

	it('loads the finals feed in the complete state and renders the hype sections', async () => {
		stubFetch(answerWith(inState('complete')));
		const { container } = await renderPage();
		expect(finalsCalls()).toHaveLength(1);
		expect(ids(container)).toEqual([
			'finals-mvp',
			'series',
			'road',
			'head-to-head',
			'leaders',
			'bracket',
			'play-in',
			'awards'
		]);
		expect(screen.getByRole('heading', { level: 1, name: 'Champions' })).toBeTruthy();
	});

	it('loads the finals feed in the finals state as well', async () => {
		stubFetch(answerWith(inState('finals')));
		const { container } = await renderPage();
		expect(finalsCalls()).toHaveLength(1);
		expect(ids(container)).toContain('series');
	});

	it('hides only the finals sections when the finals feed answers 404 or 503', async () => {
		for (const status of [404, 503]) {
			stubFetch(answerWith(inState('complete')));
			finalsAnswer = answerStatus(status);
			const { container, unmount } = await renderPage();
			expect(ids(container)).toEqual(['leaders', 'bracket', 'play-in', 'awards']);
			expect(screen.getByRole('heading', { level: 1, name: 'Champions' })).toBeTruthy();
			unmount();
		}
	});

	it('hides the finals sections with no finals URL configured', async () => {
		config.finals = undefined;
		stubFetch(answerWith(inState('complete')));
		const { container } = await renderPage();
		expect(finalsCalls()).toHaveLength(0);
		expect(ids(container)).toEqual(['leaders', 'bracket', 'play-in', 'awards']);
	});

	it('shows the skeleton until the first load settles', async () => {
		let finish: (answer: unknown) => void = () => {};
		stubFetch(() => new Promise((resolve) => (finish = resolve)));
		const { container } = await renderPage();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.table-skeleton')).not.toBeNull();
		finish({ ok: true, status: 200, json: () => Promise.resolve(picture()) });
		await settle();
		expect(container.querySelector('.table-skeleton')).toBeNull();
		expect(screen.getAllByText('Playoff picture').length).toBeGreaterThan(0);
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
		stubFetch(answerWith(picture()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('keeps polling after a 503 and renders the page when a later load succeeds', async () => {
		stubFetch(answerStatus(503), answerWith(picture()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getAllByText('Playoff picture').length).toBeGreaterThan(0);
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('polls every 60 s', async () => {
		stubFetch(answerWith(picture()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(59_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('pauses while the tab is hidden and loads at once when it is visible again', async () => {
		const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
		stubFetch(answerWith(picture()));
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

	it('keeps the last playoffs feed on screen when a later poll fails', async () => {
		stubFetch(answerWith(picture()), answerFailing);
		await renderPage();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getAllByText('Playoff picture').length).toBeGreaterThan(0);
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es-ES']);
		stubFetch(answerWith(picture()));
		await renderPage();
		expect(screen.getByRole('heading', { level: 1, name: 'Playoffs' })).toBeTruthy();
		expect(screen.getAllByText('Panorama de playoffs').length).toBeGreaterThan(0);
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});
});
