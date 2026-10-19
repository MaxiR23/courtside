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
// - After a 503 (no feed yet) it polls again at 60 s and renders the team when that load succeeds
// - Polls every 5 minutes once a feed is loaded; pauses while the tab is hidden and loads at once when visible again
// - Keeps the last feed on screen when a later poll fails
// - Renders in English and in Spanish
// - With ?season: loads the calendar, then only the season feed, once; no polling; loading, 503 and 404 states
// - An invalid, unlisted or current ?season loads the current feed and polls it; a late calendar does not reload it
// - Calendar 503 or no calendar URL: the current season and no select
// - The select lists the right seasons and navigates with goto; Spanish
// - The unavailable state of a past season keeps the Season tag (ADR 0054)
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
	get seasonTeamFeedUrl() {
		return seasonMocks.past;
	},
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
		const cup = screen.getByRole('link', { name: 'Cup' });
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
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

	it('polls every 5 minutes once a feed is loaded', async () => {
		stubFetch('okc', answerWith(recorded()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(299_999);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(300_000);
		expect(fetchMock).toHaveBeenCalledTimes(3);
	});

	it('pauses while the tab is hidden and loads at once when it is visible again', async () => {
		const state = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
		stubFetch('okc', answerWith(recorded()));
		await renderPage();
		state.mockReturnValue('hidden');
		document.dispatchEvent(new Event('visibilitychange'));
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		state.mockReturnValue('visible');
		document.dispatchEvent(new Event('visibilitychange'));
		await settle();
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('keeps the last feed on screen when a later poll fails', async () => {
		stubFetch('okc', answerWith(recorded()), answerFailing);
		await renderPage();
		await vi.advanceTimersByTimeAsync(300_000);
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

const CAL_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CAL_URL = 'https://feeds.example.com/seasons/current/calendar.json';
const CURRENT_URL = feedUrl('okc');
const PAST_TEMPLATE = 'https://feeds.example.com/seasons/{season}/teams/{code}.json';
const pastUrl = (season: number) => `https://feeds.example.com/seasons/${season}/teams/okc.json`;
const fixtures = join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures');
const calendarFeed = () => JSON.parse(readFileSync(join(fixtures, 'calendar.json'), 'utf8'));
const pastRecorded = (): TeamFeed =>
	JSON.parse(readFileSync(join(fixtures, 'team-past.json'), 'utf8')) as TeamFeed;

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
	seasonMocks.url = new URL(`http://localhost/team/okc${query}`);
	const result = render(Page, { props: { params: { code: 'okc' }, data: {} } });
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

describe('team page season selector', () => {
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

	it('shows No team this season. with the select on a 404 of the season feed', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [answerStatus(404)] });
		await renderSeason('?season=2005');
		expect(screen.getByText('No team this season.')).toBeTruthy();
		expect(screen.queryByText('Team not found.')).toBeNull();
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it('keeps the Season tag on the unavailable state of a past season', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2005)]: [answerStatus(503)] });
		await renderSeason('?season=2005');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
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
			await vi.advanceTimersByTimeAsync(300_000);
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

	it('lists every season when the feed has no names, and the seasons inside the runs otherwise', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[CURRENT_URL]: [answerJson(recorded())],
			[pastUrl(2005)]: [
				answerJson({
					...pastRecorded(),
					names: [
						{ from: 1994, to: 1996, name: 'Pilots', location: 'Lakeview', code: 'LKV' },
						{ from: 2003, to: 2006, name: 'Mariners', location: 'Harbor City', code: 'HCM' }
					]
				})
			]
		});
		const first = await renderSeason('');
		expect(optionLabels()).toHaveLength(calendarFeed().seasons.length);
		first.unmount();
		await renderSeason('?season=2005');
		expect(optionLabels()).toEqual([
			'2005-06',
			'2004-05',
			'2003-04',
			'2002-03',
			'1995-96',
			'1994-95',
			'1993-94'
		]);
	});

	it('draws the names timeline on a past season with a link to the last season of a past run', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		const { container } = await renderSeason('?season=2005');
		expect(screen.getByText('Names')).toBeTruthy();
		expect([...container.querySelectorAll('.runs a')].map((a) => a.getAttribute('href'))).toEqual([
			'/team/okc?season=2001',
			'/team/okc?season=2008',
			'/team/okc?season=2014'
		]);
	});

	it('shows the past season without Overview and Injuries and without the roster status column', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		const { container } = await renderSeason('?season=2005');
		expect([...container.querySelectorAll('.sections > section')].map((s) => s.id)).toEqual([
			'record',
			'leaders',
			'roster',
			'schedule'
		]);
		expect(screen.getByRole('heading', { level: 1, name: 'Mariners' })).toBeTruthy();
		expect(screen.getAllByText('Alex Rivera').length).toBeGreaterThan(0);
		expect(screen.queryByText('Status')).toBeNull();
	});

	it('goes to ?season=2005 when 2005 is chosen and to the bare route for the current season', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[CURRENT_URL]: [answerJson(recorded())]
		});
		await renderSeason('');
		choose('2005');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/team/okc?season=2005');
		choose('2027');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/team/okc');
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es']);
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2005)]: [answerJson(pastRecorded())]
		});
		await renderSeason('?season=2005');
		expect(screen.getByText('Temporada 2004-05')).toBeTruthy();
		expect(screen.getByText('Nombres')).toBeTruthy();
	});
});
