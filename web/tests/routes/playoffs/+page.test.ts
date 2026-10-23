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
// - Polls both feeds every 5 minutes once the playoffs are complete, every 60 s in the finals state
// - Pauses polling while the tab is hidden and loads at once when visible again
// - Keeps the last playoffs feed on screen when a later poll fails
// - Renders in Spanish
// - The unavailable state of a past season keeps the Season tag; a calendar that answers 503 shows the current season and no select (ADR 0054)
// - With ?season: loads the calendar, then the season playoffs and finals feeds, once each; no polling; the tag; 503 and 404 states
// - A malformed, unlisted or current ?season loads the current feeds and polls them; the select lists every calendar season and navigates with goto
// - The bracket's Full series link and second tap keep ?season on a past season and have none on the current one
// - A past feed with no play-in, no head to head values, no leaders and no awards closes the sections with no gap; a null seed draws no number
// - The current season keeps the head to head of all-null bars and the dash of a null seed
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, sections, footer
// - Recorded feeds (tests/lib/feed/fixtures/playoffs-*.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/playoffs/+page.test.ts
//
// SEE: web/src/routes/playoffs/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed, PlayoffsState } from '../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../src/lib/contract/playoffs-finals';
import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/playoffs/+page.svelte';

const seasonMocks = vi.hoisted(() => ({
	calendar: undefined as string | undefined,
	past: undefined as string | undefined,
	pastFinals: undefined as string | undefined,
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
	finals: undefined as string | undefined
}));
vi.mock('../../../src/lib/feed/config', () => ({
	get calendarFeedUrl() {
		return seasonMocks.calendar;
	},
	get seasonPlayoffsFeedUrl() {
		return seasonMocks.past;
	},
	get seasonPlayoffsFinalsFeedUrl() {
		return seasonMocks.pastFinals;
	},
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
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
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
		expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Harbor');
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
			expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('Harbor');
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

	it('polls the playoffs and finals feeds every 5 minutes once the playoffs are complete', async () => {
		stubFetch(answerWith(inState('complete')));
		await renderPage();
		const playoffsCalls = () => fetchMock.mock.calls.filter((call) => call[0] === FEED_URL);
		expect(playoffsCalls()).toHaveLength(1);
		expect(finalsCalls()).toHaveLength(1);
		await vi.advanceTimersByTimeAsync(299_999);
		expect(playoffsCalls()).toHaveLength(1);
		expect(finalsCalls()).toHaveLength(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(playoffsCalls()).toHaveLength(2);
		expect(finalsCalls()).toHaveLength(2);
	});

	it('polls both feeds every 60 s in the finals state', async () => {
		stubFetch(answerWith(inState('finals')));
		await renderPage();
		const playoffsCalls = () => fetchMock.mock.calls.filter((call) => call[0] === FEED_URL);
		await vi.advanceTimersByTimeAsync(59_999);
		expect(playoffsCalls()).toHaveLength(1);
		expect(finalsCalls()).toHaveLength(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(playoffsCalls()).toHaveLength(2);
		expect(finalsCalls()).toHaveLength(2);
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

const CAL_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CAL_URL = 'https://feeds.example.com/seasons/current/calendar.json';
const PAST_TEMPLATE = 'https://feeds.example.com/seasons/{season}/playoffs.json';
const PAST_FINALS_TEMPLATE = 'https://feeds.example.com/seasons/{season}/playoffs/finals.json';
const pastUrl = (season: number) => `https://feeds.example.com/seasons/${season}/playoffs.json`;
const pastFinalsUrl = (season: number) =>
	`https://feeds.example.com/seasons/${season}/playoffs/finals.json`;
const calendarFeed = () => fixture<{ seasons: unknown[] }>('calendar.json');
const finalsFeed = () => fixture<PlayoffsFinalsFeed>('playoffs-finals.json');
const emptyBars = (): PlayoffsFinalsFeed => {
	const finals = finalsFeed();
	for (const bar of finals.headToHead.bars) for (const entry of bar.values) entry.value = null;
	return finals;
};
const seedless = (): PlayoffsFeed => {
	const feed = inState('complete');
	const finals = feed.bracket.find((series) => series.id === 'finals')!;
	finals.top.seed = null;
	return feed;
};
const seedTexts = (container: HTMLElement) =>
	[...container.querySelectorAll('.row .seed')].map((seed) => seed.textContent);

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

const never: Answer = () => new Promise(() => {});
const countOf = (url: string) => calls.filter((call) => call === url).length;

async function settleAll() {
	for (let i = 0; i < 4; i++) await settle();
}

async function renderSeason(query: string) {
	seasonMocks.url = new URL(`http://localhost/playoffs${query}`);
	const result = render(Page);
	await settleAll();
	return result;
}

function choose(value: string) {
	const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
	select.value = value;
	select.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('Playoffs page season selector', () => {
	beforeEach(() => {
		seasonMocks.calendar = CAL_TEMPLATE;
		seasonMocks.past = PAST_TEMPLATE;
		seasonMocks.pastFinals = PAST_FINALS_TEMPLATE;
		seasonMocks.goto.mockReset();
	});

	afterEach(() => {
		seasonMocks.calendar = undefined;
		seasonMocks.past = undefined;
		seasonMocks.pastFinals = undefined;
		seasonMocks.url = new URL('http://localhost/');
	});

	it('loads the calendar, then the season feed and its finals once each, for ?season=2005', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(inState('complete'))],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		const { container } = await renderSeason('?season=2005');
		expect(calls).toEqual([CAL_URL, pastUrl(2005), pastFinalsUrl(2005)]);
		expect(screen.getByText('Season 2026-27')).toBeTruthy();
		expect(container.querySelector('.stage-strip .current')).toBeNull();
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(countOf(pastUrl(2005))).toBe(1);
		expect(countOf(pastFinalsUrl(2005))).toBe(1);
		expect(countOf(CAL_URL)).toBe(1);
	});

	it('links the Full series of the bracket with the season of a past season, and without one on the current season', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(inState('complete'))],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		const past = await renderSeason('?season=2005');
		expect(
			past.container.querySelector('#bracket section.result a.full')?.getAttribute('href')
		).toBe('/playoffs/series?id=finals&season=2005');
		past.unmount();
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[FEED_URL]: [answerWith(inState('complete'))],
			[FINALS_URL]: [answerWith(finalsFeed())]
		});
		const current = await renderSeason('');
		expect(
			current.container.querySelector('#bracket section.result a.full')?.getAttribute('href')
		).toBe('/playoffs/series?id=finals');
	});

	it('goes to the full series page on a second tap, keeping the season of a past season', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(inState('complete'))],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		const { container } = await renderSeason('?season=2005');
		await fireEvent.click(container.querySelector('#bracket button.series.selected')!);
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/playoffs/series?id=finals&season=2005');
	});

	it('requests no finals feed of a past season that has not reached the Finals', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(inState('playoffs'))]
		});
		await renderSeason('?season=2005');
		expect(calls).toEqual([CAL_URL, pastUrl(2005)]);
	});

	it('shows the loading skeleton and the select while the season feed is pending', async () => {
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [pastUrl(2005)]: [never] });
		const { container } = await renderSeason('?season=2005');
		expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it.each([503, 404])(
		'shows the unavailable row and the select on a %s of the season feed',
		async (status) => {
			stubRoutes({
				[CAL_URL]: [answerWith(calendarFeed())],
				[pastUrl(2005)]: [answerStatus(status)]
			});
			await renderSeason('?season=2005');
			expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
			expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
		}
	);

	it('keeps the Season tag on the unavailable state of a past season', async () => {
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [pastUrl(2005)]: [answerStatus(503)] });
		await renderSeason('?season=2005');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
	});

	it('shows the current season and no select when the calendar answers 503', async () => {
		stubRoutes({ [CAL_URL]: [answerStatus(503)], [FEED_URL]: [answerWith(picture())] });
		await renderSeason('?season=2005');
		expect(calls).toEqual([CAL_URL, FEED_URL]);
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it.each(['?season=abcd', '?season=1990', '?season=2027'])(
		'loads the current feed and polls it for %s',
		async (query) => {
			stubRoutes({
				[CAL_URL]: [answerWith(calendarFeed())],
				[FEED_URL]: [answerWith(picture())]
			});
			await renderSeason(query);
			expect(calls).toEqual([CAL_URL, FEED_URL]);
			await vi.advanceTimersByTimeAsync(60_000);
			expect(countOf(FEED_URL)).toBe(2);
		}
	);

	it('lists every season of the calendar and navigates with goto', async () => {
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [FEED_URL]: [answerWith(picture())] });
		await renderSeason('');
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect(select.options).toHaveLength(calendarFeed().seasons.length);
		expect(select.options[0]?.textContent).toBe('2026-27');
		expect(select.options[select.options.length - 1]?.textContent).toBe('1993-94');
		choose('2005');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/playoffs?season=2005');
		choose('2027');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/playoffs');
	});

	it('shows no play-in section and no play-in stage for a past feed with no play-in', async () => {
		const feed = inState('complete');
		feed.playIn = null;
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(feed)],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		const { container } = await renderSeason('?season=2005');
		expect(ids(container)).not.toContain('play-in');
		expect(screen.queryByRole('heading', { name: 'Play-In' })).toBeNull();
		expect(container.querySelectorAll('.stage-strip .stage')).toHaveLength(4);
	});

	it('shows no head to head heading for a past finals feed with all-null bars', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(inState('complete'))],
			[pastFinalsUrl(2005)]: [answerWith(emptyBars())]
		});
		await renderSeason('?season=2005');
		expect(screen.queryByRole('heading', { name: 'Head to head' })).toBeNull();
	});

	it('still shows the head to head heading of a current finals feed with all-null bars', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[FEED_URL]: [answerWith(inState('complete'))],
			[FINALS_URL]: [answerWith(emptyBars())]
		});
		await renderSeason('');
		expect(screen.getByRole('heading', { name: 'Head to head' })).toBeTruthy();
	});

	it('shows neither leaders nor awards for a past feed that has none, with no gap', async () => {
		const feed = inState('complete');
		feed.leaders = null;
		feed.awards = null;
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(feed)],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		const { container } = await renderSeason('?season=2005');
		expect(ids(container)).toEqual([
			'finals-mvp',
			'series',
			'road',
			'head-to-head',
			'bracket',
			'play-in'
		]);
		expect(screen.queryByRole('heading', { name: 'Leaders' })).toBeNull();
		expect(screen.queryByRole('heading', { name: 'Awards' })).toBeNull();
	});

	it('draws no seed digit for a null seed of a past season', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(seedless())],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		const { container } = await renderSeason('?season=2005');
		expect(seedTexts(container)).not.toContain('—');
		expect(seedTexts(container)).toContain('');
	});

	it('still draws the dash for a null seed of the current season', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[FEED_URL]: [answerWith(seedless())],
			[FINALS_URL]: [answerWith(finalsFeed())]
		});
		const { container } = await renderSeason('');
		expect(seedTexts(container)).toContain('—');
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es']);
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(inState('complete'))],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		await renderSeason('?season=2005');
		expect(screen.getByText('Temporada 2026-27')).toBeTruthy();
	});
});
