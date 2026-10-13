// web/tests/routes/cup/+page.test.ts
//
// Tests for the Cup route.
//
// Tested:
// - Shows the search trigger in the nav
// - The route turns off server rendering and keeps prerender from the layout
// - Loads the Cup feed and renders the header, the sections, the nav with Cup current and the footer
// - Shows the skeleton until the first load settles
// - Shows the data unavailable row on a 503, a network failure, or with no URL configured
// - After a 503 it polls again at 60 s and renders the Cup when that load succeeds
// - Polls every 60 s; pauses while the tab is hidden and loads at once when visible again
// - Keeps the last feed on screen when a later poll fails
// - Opens a node: loads its matchup with a no-cache request, shows the panel, polls it again at 60 s while open and stops after Esc
// - A failed matchup shows the unavailable line inside the panel while the bracket stays
// - Renders in Spanish
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, tables, footer
// - A recorded feed (tests/lib/feed/fixtures/cup.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/cup/+page.test.ts
//
// SEE: web/src/routes/cup/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/cup/+page.svelte';

const config = vi.hoisted(() => ({
	url: undefined as string | undefined,
	matchup: undefined as string | undefined
}));
vi.mock('../../../src/lib/feed/config', () => ({
	get cupFeedUrl() {
		return config.url;
	},
	get cupMatchupFeedUrl() {
		return config.matchup;
	}
}));

const FEED_URL = 'https://feeds.example.com/cup.json';
const MATCHUP_TEMPLATE = 'https://feeds.example.com/cup/matchups/{id}.json';
const MATCHUP_URL = 'https://feeds.example.com/cup/matchups/final.json';
const recorded = (): CupFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', 'lib', 'feed', 'fixtures', 'cup.json'), 'utf8')
	) as CupFeed;

const UNAVAILABLE = "Data isn't available right now. Check back later.";

const matchupFeed = (): unknown =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', 'lib', 'feed', 'fixtures', 'cup-matchup.json'), 'utf8')
	);

type Answer = () => Promise<unknown>;
let answers: Answer[];
let matchupAnswer: Answer;
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(feed: CupFeed): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(feed) });
const answerStatus =
	(status: number): Answer =>
	() =>
		Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) });
const answerFailing: Answer = () => Promise.reject(new TypeError('Failed to fetch'));

function stubFetch(...next: Answer[]) {
	answers = next;
	matchupAnswer = () =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(matchupFeed()) });
	fetchMock = vi.fn((url: string) => {
		if (url === MATCHUP_URL) return matchupAnswer();
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

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-10-07T23:30:00Z'));
	config.url = FEED_URL;
	config.matchup = MATCHUP_TEMPLATE;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('Cup route', () => {
	it('turns off server rendering and inherits prerender from the layout', async () => {
		const options = await import('../../../src/routes/cup/+page');
		expect(options.ssr).toBe(false);
		expect((options as { prerender?: boolean }).prerender).toBeUndefined();
	});
});

describe('Cup page', () => {
	it('loads the feed and renders the header, the sections, the nav and the footer', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][0]).toBe(FEED_URL);
		expect(screen.getByRole('heading', { level: 1, name: 'NBA Cup' })).toBeTruthy();
		expect(screen.getAllByText('Group play · 16 of 60 games played').length).toBeGreaterThan(0);
		expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
			'Groups',
			'Wild card',
			'Bracket',
			'Cup games'
		]);
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('aria-current')).toBe('page');
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'Herons' })[0]?.getAttribute('href')).toBe(
			'/team/qxa'
		);
	});

	it('shows the search trigger in the nav', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
	});

	it('shows the skeleton until the first load settles', async () => {
		let finish: (answer: unknown) => void = () => {};
		stubFetch(() => new Promise((resolve) => (finish = resolve)));
		const { container } = await renderPage();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.table-skeleton')).not.toBeNull();
		finish({ ok: true, status: 200, json: () => Promise.resolve(recorded()) });
		await settle();
		expect(container.querySelector('.table-skeleton')).toBeNull();
		expect(screen.getAllByText('Group play · 16 of 60 games played').length).toBeGreaterThan(0);
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
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('keeps polling after a 503 and renders the Cup when a later load succeeds', async () => {
		stubFetch(answerStatus(503), answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getAllByText('Group play · 16 of 60 games played').length).toBeGreaterThan(0);
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('polls every 60 s', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(59_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(60_000);
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
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getAllByText('Group play · 16 of 60 games played').length).toBeGreaterThan(0);
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	const matchupCalls = () => fetchMock.mock.calls.filter((call) => call[0] === MATCHUP_URL);

	it('opens a node: loads its matchup with a no-cache request and shows the panel', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(matchupCalls()).toHaveLength(0);
		await fireEvent.click(screen.getByRole('button', { name: /^Championship ·/ }));
		await settle();
		expect(matchupCalls()).toHaveLength(1);
		expect(matchupCalls()[0]?.[1]).toEqual({
			cache: 'no-cache',
			headers: { accept: 'application/json' }
		});
		expect(screen.getByRole('dialog', { name: 'Championship' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Game page →' }).getAttribute('href')).toBe(
			'/game/9100004'
		);
	});

	it('polls the matchup every 60 s while the panel is open and stops after Esc', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: /^Championship ·/ }));
		await settle();
		await vi.advanceTimersByTimeAsync(60_000);
		expect(matchupCalls()).toHaveLength(2);
		await fireEvent.keyDown(window, { key: 'Escape' });
		await tick();
		expect(screen.queryByRole('dialog')).toBeNull();
		await vi.advanceTimersByTimeAsync(180_000);
		expect(matchupCalls()).toHaveLength(2);
	});

	it('shows the unavailable line inside the panel on a failed matchup while the bracket stays', async () => {
		stubFetch(answerWith(recorded()));
		matchupAnswer = answerStatus(503);
		await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: /^Championship ·/ }));
		await settle();
		const panel = screen.getByRole('dialog');
		expect(panel.textContent).toContain(UNAVAILABLE);
		expect(document.querySelectorAll('.bracket .node')).toHaveLength(7);
	});

	it('is failed at once for a node when no matchup URL is configured', async () => {
		config.matchup = undefined;
		stubFetch(answerWith(recorded()));
		await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: /^Championship ·/ }));
		await settle();
		expect(screen.getByRole('dialog').textContent).toContain(UNAVAILABLE);
		expect(matchupCalls()).toHaveLength(0);
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es-ES']);
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('link', { name: 'Copa' })).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Copa NBA' })).toBeTruthy();
		expect(
			screen.getAllByText('Fase de grupos · 16 de 60 partidos jugados').length
		).toBeGreaterThan(0);
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});
});
