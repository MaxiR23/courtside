// web/tests/routes/game/[id]/+page.test.ts
//
// Tests for the game detail page.
//
// Tested:
// - The route turns off prerender and server rendering
// - Loads the feed of the game in the URL and renders its header and tabs
// - Shows the loading skeleton until the first load settles
// - Shows "Game not found." when the feed answers 404
// - Shows the data unavailable row on a network failure, a 503, a feed it cannot show, or with no URL configured
// - Polls again after 30 s while the game is live and after 60 s once it is not
// - Pauses while the tab is hidden and loads at once when it is visible again
// - Keeps the last feed on screen when a later poll fails
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, tabs, footer
// - A recorded feed (tests/lib/feed/fixtures/game-detail.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/game/[id]/+page.test.ts"
//
// SEE: web/src/routes/game/[id]/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GameDetailFeed } from '../../../../src/lib/contract/game-detail';

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
const finalGame = (): GameDetailFeed => ({ ...recorded(), status: 'final', winner: 'LAL' });

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
		stubFetch(answerWith(recorded()), answerWith(finalGame()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(29_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await tick();
		expect(screen.getByText(/^Final · /)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(59_999);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(3);
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
});
