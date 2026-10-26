// web/tests/routes/standings/+page.test.ts
//
// Tests for the standings route.
//
// Tested:
// - Shows the search trigger in the nav
// - The route turns off server rendering and keeps prerender from the layout
// - Loads the standings feed and renders the Conference view, the nav with Standings current
//   and the footer
// - Shows the skeleton until the first load settles
// - Shows the data unavailable row on a 503, a network failure, or with no URL configured
// - After a 503 it polls again at 60 s and renders the standings when that load succeeds
// - Polls every 60 s, and every 5 minutes once the standings are final; pauses while the tab is hidden and loads at once when visible again
// - Keeps the last feed on screen when a later poll fails
// - Renders in Spanish
// - With ?season: loads the calendar, then only the season feed, once; no polling; loading, 503 and 404 states
// - An invalid, unlisted or current ?season loads the current feed and polls it; a late calendar does not reload it
// - Calendar 503 or no calendar URL: the current season and no select
// - Power ranking: current season only, hidden when unavailable, failed, unconfigured or on a past season; polled
// - The select lists the right seasons and navigates with goto; Spanish
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, tables, footer
// - A recorded feed (tests/lib/feed/fixtures/standings.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/standings/+page.test.ts
//
// SEE: web/src/routes/standings/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { StandingsFeed } from '../../../src/lib/contract/standings';
import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/standings/+page.svelte';

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

const config = vi.hoisted(() => ({
	url: undefined as string | undefined,
	powerRanking: undefined as string | undefined
}));
vi.mock('../../../src/lib/feed/config', () => ({
	get calendarFeedUrl() {
		return seasonMocks.calendar;
	},
	get seasonStandingsFeedUrl() {
		return seasonMocks.past;
	},
	get standingsFeedUrl() {
		return config.url;
	},
	get powerRankingFeedUrl() {
		return config.powerRanking;
	}
}));

const FEED_URL = 'https://feeds.example.com/standings.json';
const recorded = (): StandingsFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', 'lib', 'feed', 'fixtures', 'standings.json'), 'utf8')
	) as StandingsFeed;

const UNAVAILABLE = "Data isn't available right now. Check back later.";

type Answer = () => Promise<unknown>;
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(feed: StandingsFeed): Answer =>
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
	const result = render(Page);
	await settle();
	return result;
}

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-10-07T23:30:00Z'));
	config.url = FEED_URL;
	config.powerRanking = undefined;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('standings route', () => {
	it('turns off server rendering and inherits prerender from the layout', async () => {
		const options = await import('../../../src/routes/standings/+page');
		expect(options.ssr).toBe(false);
		expect((options as { prerender?: boolean }).prerender).toBeUndefined();
	});
});

describe('standings page', () => {
	it('loads the feed and renders the Conference view, the nav and the footer', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(fetchMock.mock.calls[0][0]).toBe(FEED_URL);
		expect(screen.getByRole('heading', { level: 1, name: 'Standings' })).toBeTruthy();
		expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)).toEqual([
			'Eastern Conference',
			'Western Conference'
		]);
		const standings = screen.getByRole('link', { name: 'Standings' });
		expect(standings.getAttribute('aria-current')).toBe('page');
		expect(standings.getAttribute('href')).toBe('/standings');
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
		expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
		expect(screen.getByRole('link', { name: /Celtics/ }).getAttribute('href')).toBe('/team/bos');
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
		expect(screen.getByText('Eastern Conference')).toBeTruthy();
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

	it('keeps polling after a 503 and renders the standings when a later load succeeds', async () => {
		stubFetch(answerStatus(503), answerWith(recorded()));
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByText('Eastern Conference')).toBeTruthy();
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

	it('polls every 5 minutes once the standings are final', async () => {
		stubFetch(answerWith({ ...recorded(), state: 'final' }));
		await renderPage();
		await vi.advanceTimersByTimeAsync(299_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
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
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(screen.getByText('Eastern Conference')).toBeTruthy();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es-ES']);
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('link', { name: 'Clasificación' })).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Clasificación' })).toBeTruthy();
		expect(screen.getByText('Conferencia Este')).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});
});

const CAL_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CAL_URL = 'https://feeds.example.com/seasons/current/calendar.json';
const CURRENT_URL = FEED_URL;
const PAST_TEMPLATE = 'https://feeds.example.com/seasons/{season}/standings.json';
const pastUrl = (season: number) => `https://feeds.example.com/seasons/${season}/standings.json`;
const fixtures = join(__dirname, '..', '..', 'lib', 'feed', 'fixtures');
const calendarFeed = () => JSON.parse(readFileSync(join(fixtures, 'calendar.json'), 'utf8'));
const pastRecorded = (): StandingsFeed =>
	JSON.parse(readFileSync(join(fixtures, 'standings-past.json'), 'utf8')) as StandingsFeed;

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
	seasonMocks.url = new URL(`http://localhost/standings${query}`);
	const result = render(Page);
	await settleAll();
	return result;
}

function choose(value: string) {
	const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
	select.value = value;
	select.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('standings page season selector', () => {
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

	it('shows the unavailable row on a 503 of the season feed', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [answerStatus(503)] });
		await renderSeason('?season=2005');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
	});

	it('shows the unavailable row on a 404 of the season feed', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [answerStatus(404)] });
		await renderSeason('?season=2005');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
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

	it('lists every season of the calendar', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[CURRENT_URL]: [answerJson(recorded())]
		});
		await renderSeason('');
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect(select.options).toHaveLength(calendarFeed().seasons.length);
		expect(select.value).toBe('2027');
	});

	it('shows the final standings of a past season and the season on show in the select', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		await renderSeason('?season=2005');
		expect(screen.getByText('Final standings')).toBeTruthy();
		expect(screen.getAllByText('Bosville').length).toBeGreaterThan(0);
		expect((screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement).value).toBe(
			'2005'
		);
	});

	it('goes to ?season=2005 when 2005 is chosen and to the bare route for the current season', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[CURRENT_URL]: [answerJson(recorded())]
		});
		await renderSeason('');
		choose('2005');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/standings?season=2005');
		choose('2027');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/standings');
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es']);
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		await renderSeason('?season=2005');
		expect(screen.getByText('Temporada 2004-05')).toBeTruthy();
		expect(screen.getByText('Clasificación final')).toBeTruthy();
	});
});

const RANKING_URL = 'https://feeds.example.com/power-ranking.json';
const rankingRecorded = () =>
	JSON.parse(readFileSync(join(fixtures, 'power-ranking.json'), 'utf8'));
const sectionOrNull = () => screen.queryByRole('region', { name: 'Power ranking' });
const sectionRows = () => sectionOrNull()?.querySelectorAll('.body, .item').length;

describe('standings page power ranking', () => {
	beforeEach(() => {
		config.powerRanking = RANKING_URL;
	});

	afterEach(() => {
		seasonMocks.calendar = undefined;
		seasonMocks.past = undefined;
		seasonMocks.url = new URL('http://localhost/');
	});

	it('renders the section under the standings with 10 rows for the current season', async () => {
		stubRoutes({
			[FEED_URL]: [answerJson(recorded())],
			[RANKING_URL]: [answerJson(rankingRecorded())]
		});
		await renderSeason('');
		expect(sectionRows()).toBe(10);
		expect(screen.getByText('Eastern Conference')).toBeTruthy();
	});

	it('hides the section when the feed is unavailable and keeps the standings', async () => {
		stubRoutes({
			[FEED_URL]: [answerJson(recorded())],
			[RANKING_URL]: [answerJson({ season: '2026-27', state: 'unavailable', teams: [] })]
		});
		await renderSeason('');
		expect(sectionOrNull()).toBeNull();
		expect(screen.getByText('Eastern Conference')).toBeTruthy();
	});

	it('hides the section on a 503 and on a network failure and keeps the standings', async () => {
		for (const failing of [answerStatus(503), answerFailing]) {
			stubRoutes({ [FEED_URL]: [answerJson(recorded())], [RANKING_URL]: [failing] });
			const { unmount } = await renderSeason('');
			expect(sectionOrNull()).toBeNull();
			expect(screen.getByText('Eastern Conference')).toBeTruthy();
			unmount();
		}
	});

	it('makes no request and shows no section without a URL', async () => {
		config.powerRanking = undefined;
		stubRoutes({ [FEED_URL]: [answerJson(recorded())] });
		await renderSeason('');
		expect(calls).toEqual([FEED_URL]);
		expect(sectionOrNull()).toBeNull();
	});

	it('makes no request and shows no section on a past season', async () => {
		seasonMocks.calendar = CAL_TEMPLATE;
		seasonMocks.past = PAST_TEMPLATE;
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())],
			[RANKING_URL]: [answerJson(rankingRecorded())]
		});
		await renderSeason('?season=2005');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(countOf(RANKING_URL)).toBe(0);
		expect(sectionOrNull()).toBeNull();
	});

	it('polls again after 5 minutes once loaded', async () => {
		stubRoutes({
			[FEED_URL]: [answerJson(recorded())],
			[RANKING_URL]: [answerJson(rankingRecorded())]
		});
		await renderSeason('');
		await vi.advanceTimersByTimeAsync(299_999);
		expect(countOf(RANKING_URL)).toBe(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(countOf(RANKING_URL)).toBe(2);
	});

	it('polls again after 60 seconds when the first load failed, and then shows the section', async () => {
		stubRoutes({
			[FEED_URL]: [answerJson(recorded())],
			[RANKING_URL]: [answerStatus(503), answerJson(rankingRecorded())]
		});
		await renderSeason('');
		expect(sectionOrNull()).toBeNull();
		await vi.advanceTimersByTimeAsync(60_000);
		await settleAll();
		expect(countOf(RANKING_URL)).toBe(2);
		expect(sectionRows()).toBe(10);
	});

	it('keeps the section on screen when a later poll fails', async () => {
		stubRoutes({
			[FEED_URL]: [answerJson(recorded())],
			[RANKING_URL]: [answerJson(rankingRecorded()), answerStatus(503)]
		});
		await renderSeason('');
		await vi.advanceTimersByTimeAsync(300_000);
		await settleAll();
		expect(countOf(RANKING_URL)).toBe(2);
		expect(sectionRows()).toBe(10);
	});
});
