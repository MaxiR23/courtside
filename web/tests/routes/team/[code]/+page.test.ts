// web/tests/routes/team/[code]/+page.test.ts
//
// Tests for the team page.
//
// Tested:
// - Shows the search trigger in the nav
// - The route turns off prerender and server rendering
// - Loads the feed of the team code in the URL and renders the h1, every section and the tabs
// - Links roster names to /player/{id}
// - Shows the loading skeleton until the first load settles
// - Shows "Team not found." on a 404, for an unknown code and for an uppercase one
// - Shows the data unavailable row on a network failure, a 503, or with no URL configured
// - After a 503 it polls again at 60 s and renders the team when that load succeeds
// - Polls every 60 s; pauses while the tab is hidden and loads at once when visible again
// - Keeps the last feed on screen when a later poll fails
// - Renders in English and in Spanish
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, tabs, footer
// - A recorded feed (tests/lib/feed/fixtures/team.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/team/[code]/+page.test.ts"
//
// SEE: web/src/routes/team/[code]/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { TeamFeed } from '../../../../src/lib/contract/team';
import { preferLanguages } from '../../../prefer-languages';

import Page from '../../../../src/routes/team/[code]/+page.svelte';

const config = vi.hoisted(() => ({ url: undefined as string | undefined }));
vi.mock('../../../../src/lib/feed/config', () => ({
	get teamFeedUrl() {
		return config.url;
	}
}));

const TEMPLATE = 'https://feeds.example.com/teams/{code}.json';
const feedUrl = (code: string) => `https://feeds.example.com/teams/${code}.json`;
const recorded = (): TeamFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures', 'team.json'), 'utf8')
	) as TeamFeed;

const UNAVAILABLE = "Data isn't available right now. Check back later.";

type Answer = () => Promise<unknown>;
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(feed: TeamFeed): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(feed) });
const answerStatus =
	(status: number): Answer =>
	() =>
		Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) });
const answerFailing: Answer = () => Promise.reject(new TypeError('Failed to fetch'));

function stubFetch(code: string, ...next: Answer[]) {
	answers = next;
	fetchMock = vi.fn((url: string) => {
		if (url !== feedUrl(code)) throw new Error(`Unexpected URL ${url}`);
		const answer = answers.length > 1 ? answers.shift() : answers[0];
		return (answer as Answer)();
	});
	vi.stubGlobal('fetch', fetchMock);
}

async function settle() {
	await vi.advanceTimersByTimeAsync(0);
	await tick();
}

async function renderPage(code = 'okc') {
	const result = render(Page, { props: { params: { code }, data: {} } });
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

describe('team route', () => {
	it('turns off prerender and server rendering for this route', async () => {
		const options = await import('../../../../src/routes/team/[code]/+page');
		expect(options.prerender).toBe(false);
		expect(options.ssr).toBe(false);
	});
});

describe('team page', () => {
	it('loads the feed of the team in the URL and renders the header, sections and tabs', async () => {
		stubFetch('okc', answerWith(recorded()));
		const { container } = await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][0]).toBe(feedUrl('okc'));
		expect(screen.getByRole('heading', { level: 1, name: 'Thunder' })).toBeTruthy();
		const nav = screen.getByRole('navigation', { name: 'Sections' });
		expect([...nav.querySelectorAll('a')].map((a) => a.textContent)).toEqual([
			'Overview',
			'Record',
			'Leaders',
			'Roster',
			'Injuries',
			'Schedule'
		]);
		expect([...container.querySelectorAll('.sections > section')].map((s) => s.id)).toEqual([
			'overview',
			'record',
			'leaders',
			'roster',
			'injuries',
			'schedule'
		]);
		expect(container.querySelector('.mini-score')?.textContent).toBe('OKC 57–25');
		expect(screen.getByRole('contentinfo')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Standings' }).getAttribute('href')).toBe('/standings');
		expect(document.querySelector('[aria-current="page"]:not(nav[aria-label] *)')).toBeNull();
	});

	it('links a game only where the feed has its detail', async () => {
		stubFetch('okc', answerWith(recorded()));
		await renderPage();
		const links = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
		expect(links).not.toContain('/game/g-next');
		const source = recorded();
		source.nextGame!.detailAvailable = true;
		stubFetch('okc', answerWith(source));
		await renderPage();
		expect(screen.getAllByRole('link').map((a) => a.getAttribute('href'))).toContain(
			'/game/g-next'
		);
	});

	it('links a roster name to its player page', async () => {
		stubFetch('okc', answerWith(recorded()));
		await renderPage();
		const hrefs = screen.getAllByRole('link').map((a) => a.getAttribute('href'));
		expect(hrefs).toContain('/player/p-holmgren');
		expect(hrefs).toContain('/player/p-sga');
	});

	it('shows the search trigger in the nav', async () => {
		stubFetch('okc', answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
	});

	it('shows the loading skeleton until the first load settles', async () => {
		let finish: (answer: unknown) => void = () => {};
		stubFetch('okc', () => new Promise((resolve) => (finish = resolve)));
		const { container } = await renderPage();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.section-skeleton')).not.toBeNull();
		finish({ ok: true, status: 200, json: () => Promise.resolve(recorded()) });
		await settle();
		expect(container.querySelector('.section-skeleton')).toBeNull();
		expect(container.querySelector('header')?.getAttribute('aria-busy')).toBeNull();
		expect(screen.getByRole('heading', { level: 1, name: 'Thunder' })).toBeTruthy();
	});

	it('shows "Team not found." on a 404, for an unknown code and an uppercase one', async () => {
		stubFetch('xyz', answerStatus(404));
		const unknown = await renderPage('xyz');
		expect(fetchMock.mock.calls[0][0]).toBe(feedUrl('xyz'));
		expect(screen.getByText('Team not found.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: 'All games' })).toHaveLength(2);
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
		unknown.unmount();

		stubFetch('OKC', answerStatus(404));
		await renderPage('OKC');
		expect(fetchMock.mock.calls[0][0]).toBe(feedUrl('OKC'));
		expect(screen.getByText('Team not found.')).toBeTruthy();
	});

	it('shows the data unavailable row on a network failure, a 503, or with no URL configured', async () => {
		stubFetch('okc', answerFailing);
		const network = await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		network.unmount();

		stubFetch('okc', answerStatus(503));
		const status = await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.queryByText('Team not found.')).toBeNull();
		status.unmount();

		config.url = undefined;
		stubFetch('okc', answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
		expect(screen.getByRole('link', { name: 'All games' })).toBeTruthy();
	});

	it('keeps polling after a 503 and renders the team when a later load succeeds', async () => {
		stubFetch('okc', answerStatus(503), answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByRole('heading', { level: 1, name: 'Thunder' })).toBeTruthy();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('polls every 60 s', async () => {
		stubFetch('okc', answerWith(recorded()));
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
		stubFetch('okc', answerWith(recorded()));
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
		stubFetch('okc', answerWith(recorded()), answerFailing);
		await renderPage();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByRole('heading', { level: 1, name: 'Thunder' })).toBeTruthy();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('renders in Spanish with a Spanish browser preference', async () => {
		preferLanguages(['es']);
		const source = recorded();
		source.nextGame = null;
		stubFetch('okc', answerWith(source));
		await renderPage();
		const nav = screen.getByRole('navigation', { name: 'Secciones' });
		expect(nav.textContent).toContain('Resumen');
		expect(screen.getByText('Temporada terminada.')).toBeTruthy();
		expect(screen.getByText('Conferencia Oeste · División Northwest')).toBeTruthy();
	});
});
