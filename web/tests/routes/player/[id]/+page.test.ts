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
// - With ?season: loads the calendar, then only the season feed, once; no polling; loading, 503 and 404 states
// - An invalid, unlisted or current ?season loads the current feed and polls it; a late calendar does not reload it
// - Calendar 503 or no calendar URL: the current season and no select
// - The select lists the right seasons and navigates with goto; Spanish
// - The unavailable state of a past season keeps the Season tag (ADR 0054)
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, tabs, footer
// - A recorded feed (tests/lib/feed/fixtures/player.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/player/[id]/+page.test.ts"
//
// SEE: web/src/routes/player/[id]/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayerFeed } from '../../../../src/lib/contract/player';
import { preferLanguages } from '../../../prefer-languages';

import Page from '../../../../src/routes/player/[id]/+page.svelte';

const seasonMocks = vi.hoisted(() => ({
	calendar: undefined as string | undefined,
	past: undefined as string | undefined,
	url: new URL('http://localhost/'),
	goto: vi.fn()
}));
vi.mock('$app/state', () => ({
	page: {
		get url() {
			return seasonMocks.url;
		}
	}
}));
vi.mock('$app/navigation', async (importOriginal) => ({
	...(await importOriginal<typeof import('$app/navigation')>()),
	goto: seasonMocks.goto
}));

const config = vi.hoisted(() => ({ url: undefined as string | undefined }));
vi.mock('../../../../src/lib/feed/config', () => ({
	get calendarFeedUrl() {
		return seasonMocks.calendar;
	},
	get seasonPlayerFeedUrl() {
		return seasonMocks.past;
	},
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
		opponent: {
			code: 'DEN',
			name: null,
			city: null,
			guest: false,
			seasonCode: null,
			historical: false,
			logo: null,
			colors: null
		},
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
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
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

const CAL_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CAL_URL = 'https://feeds.example.com/seasons/current/calendar.json';
const CURRENT_URL = feedUrl('p-2');
const PAST_TEMPLATE = 'https://feeds.example.com/seasons/{season}/players/{id}.json';
const pastUrl = (season: number) => `https://feeds.example.com/seasons/${season}/players/p-2.json`;
const fixtures = join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures');
const calendarFeed = () => JSON.parse(readFileSync(join(fixtures, 'calendar.json'), 'utf8'));
const pastRecorded = (): PlayerFeed =>
	JSON.parse(readFileSync(join(fixtures, 'player-past.json'), 'utf8')) as PlayerFeed;

type Routes = Record<string, Answer[]>;
let calls: string[];

// Answers by URL; the last answer of a URL repeats; any other URL throws.
function stubRoutes(routes: Routes) {
	calls = [];
	vi.stubGlobal(
		'fetch',
		vi.fn((url: string) => {
			const list = routes[url];
			if (!list) throw new Error(`Unexpected URL ${url}`);
			calls.push(url);
			const index = Math.min(calls.filter((call) => call === url).length - 1, list.length - 1);
			return (list[index] as Answer)();
		})
	);
}

const answerJson =
	(body: unknown): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
const never: Answer = () => new Promise(() => {});
const countOf = (url: string) => calls.filter((call) => call === url).length;

async function settleAll() {
	for (let i = 0; i < 4; i++) await settle();
}

async function renderSeason(query: string) {
	seasonMocks.url = new URL(`http://localhost/player/p-2${query}`);
	const result = render(Page, { props: { params: { id: 'p-2' }, data: {} } });
	await settleAll();
	return result;
}

function choose(value: string) {
	const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
	select.value = value;
	select.dispatchEvent(new Event('change', { bubbles: true }));
}

const optionLabels = () =>
	[...(screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement).options].map(
		(option) => option.textContent
	);

describe('player page season selector', () => {
	beforeEach(() => {
		seasonMocks.calendar = CAL_TEMPLATE;
		seasonMocks.past = PAST_TEMPLATE;
		seasonMocks.goto.mockReset();
	});

	afterEach(() => {
		seasonMocks.calendar = undefined;
		seasonMocks.past = undefined;
		seasonMocks.url = new URL('http://localhost/');
	});

	it('loads the calendar, then only the season feed, for ?season=2005', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		await renderSeason('?season=2005');
		expect(calls).toEqual([CAL_URL, pastUrl(2005)]);
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
	});

	it('does not poll a past season', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		await renderSeason('?season=2005');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(countOf(pastUrl(2005))).toBe(1);
		expect(countOf(CAL_URL)).toBe(1);
	});

	it('shows the loading skeleton while the calendar is pending', async () => {
		stubRoutes({ [CAL_URL]: [never] });
		const { container } = await renderSeason('?season=2005');
		expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
		expect(calls).toEqual([CAL_URL]);
	});

	it('shows the loading skeleton and the select while the season feed is pending', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [never] });
		const { container } = await renderSeason('?season=2005');
		expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it('keeps the Season tag on the unavailable state of a past season', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [answerStatus(503)] });
		await renderSeason('?season=2005');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
	});

	it('shows the unavailable row on a 503 of the season feed', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [answerStatus(503)] });
		await renderSeason('?season=2005');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
	});

	it('shows Player not found. on a 404 of the season feed', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [answerStatus(404)] });
		await renderSeason('?season=2005');
		expect(screen.getByText('Player not found.')).toBeTruthy();
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it.each(['?season=abcd', '?season=1990', '?season=2027'])(
		'loads the current feed and polls it for %s',
		async (query) => {
			stubRoutes({
				[CAL_URL]: [answerJson(calendarFeed())],
				[CURRENT_URL]: [answerJson(recorded())]
			});
			await renderSeason(query);
			expect(calls).toEqual([CAL_URL, CURRENT_URL]);
			await vi.advanceTimersByTimeAsync(60_000);
			expect(countOf(CURRENT_URL)).toBe(2);
		}
	);

	it('loads the current feed once when the calendar arrives later, then shows the select', async () => {
		let release: () => void = () => {};
		const late: Answer = () =>
			new Promise((resolve) => {
				release = () =>
					resolve({ ok: true, status: 200, json: () => Promise.resolve(calendarFeed()) });
			});
		stubRoutes({ [CAL_URL]: [late], [CURRENT_URL]: [answerJson(recorded())] });
		await renderSeason('');
		expect(countOf(CURRENT_URL)).toBe(1);
		expect(screen.queryByRole('combobox')).toBeNull();
		release();
		await settleAll();
		expect(countOf(CURRENT_URL)).toBe(1);
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it('shows the current season and no select when the calendar answers 503', async () => {
		stubRoutes({ [CAL_URL]: [answerStatus(503)], [CURRENT_URL]: [answerJson(recorded())] });
		await renderSeason('?season=2005');
		expect(calls).toEqual([CAL_URL, CURRENT_URL]);
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('shows the current season and no select with no calendar URL', async () => {
		seasonMocks.calendar = undefined;
		stubRoutes({ [CURRENT_URL]: [answerJson(recorded())] });
		await renderSeason('?season=2005');
		expect(calls).toEqual([CURRENT_URL]);
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('lists the current season and the seasons of the regular-season rows', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[CURRENT_URL]: [answerJson(recorded())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		const first = await renderSeason('');
		expect(optionLabels()).toEqual(['2026-27', '2025-26', '2024-25', '2018-19']);
		first.unmount();
		await renderSeason('?season=2005');
		expect(optionLabels()).toEqual(['2026-27', '2005-06', '2004-05', '2003-04']);
	});

	it('shows the past season with its tag, its team, the game log and no next game', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		const { container } = await renderSeason('?season=2005');
		expect(screen.getByRole('heading', { level: 1, name: 'Rivera' })).toBeTruthy();
		expect(screen.getByText('#2 · Guard · Harbor City Mariners')).toBeTruthy();
		expect(container.querySelector('#game-log')).toBeTruthy();
		expect(container.querySelector('#averages')).toBeTruthy();
		expect(container.querySelector('#seasons .accent')?.textContent).toContain('2004-05');
		expect(screen.queryByText('Season over.')).toBeNull();
		expect(screen.queryByText('Active')).toBeNull();
	});

	it('goes to ?season=2019 when 2019 is chosen and to the bare route for the current season', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[CURRENT_URL]: [answerJson(recorded())]
		});
		await renderSeason('');
		choose('2019');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/player/p-2?season=2019');
		choose('2027');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/player/p-2');
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es']);
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		await renderSeason('?season=2005');
		expect(screen.getByText('Temporada 2004-05')).toBeTruthy();
		expect(screen.getByRole('combobox', { name: 'Temporada' })).toBeTruthy();
	});
});
