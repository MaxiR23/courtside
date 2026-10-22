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
// - With ?season: loads the calendar, then only the season All-Star feed, once; no polling; the tag from the calendar's label; no live dot; 503 and 404 states
// - A past season whose feed answers 503 or 404 keeps its Season tag, in English and in Spanish; a past feed with no edition video shows the unavailable placeholder
// - A calendar that answers 503 shows the current season and no select; a past season on a 390px layout renders the mobile classes (ADR 0054)
// - A malformed, unlisted or current ?season loads the current feed and polls it; the select lists every calendar season and navigates with goto
// - The edition frame with its caption when the feed carries an edition video (past and current after), the placeholder when not
// - The Last time champion card linked when the previous edition has a video, not linked otherwise
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, header, sections, footer
// - Recorded feeds (tests/lib/feed/fixtures/all-star-*.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/all-star/+page.test.ts
//
// SEE: web/src/routes/all-star/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { AllStarFeed } from '../../../src/lib/contract/all-star';
import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/all-star/+page.svelte';

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
vi.mock('../../../src/lib/feed/config', () => ({
	get calendarFeedUrl() {
		return seasonMocks.calendar;
	},
	get seasonAllStarFeedUrl() {
		return seasonMocks.past;
	},
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
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
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

const CAL_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CAL_URL = 'https://feeds.example.com/seasons/current/calendar.json';
const PAST_TEMPLATE = 'https://feeds.example.com/seasons/{season}/all-star.json';
const pastUrl = (season: number) => `https://feeds.example.com/seasons/${season}/all-star.json`;
const calendarFeed = () =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', 'lib', 'feed', 'fixtures', 'calendar.json'), 'utf8')
	);
const highlight = {
	title: 'Edition recap',
	channel: 'Example Channel',
	thumbnailUrl: 'https://video.example.com/thumb/edition.jpg',
	embedUrl: 'https://video.example.com/embed/edition'
};

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
	seasonMocks.url = new URL(`http://localhost/all-star${query}`);
	const result = render(Page);
	await settleAll();
	return result;
}

function choose(value: string) {
	const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
	select.value = value;
	select.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('All-Star page season selector', () => {
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

	it('loads the calendar, then only the season feed, for ?season=2005, and tags it from the calendar', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(fixture('after'))]
		});
		const { container } = await renderSeason('?season=2005');
		expect(calls).toEqual([CAL_URL, pastUrl(2005)]);
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
		expect(container.querySelector('.live-dot')).toBeNull();
		expect((screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement).value).toBe(
			'2005'
		);
	});

	it('does not poll a past season', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(fixture('after'))]
		});
		await renderSeason('?season=2005');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(countOf(pastUrl(2005))).toBe(1);
		expect(countOf(CAL_URL)).toBe(1);
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
			expect(screen.getByText('Season 2004-05')).toBeTruthy();
		}
	);

	it.each([503, 404])(
		'keeps the Season tag in Spanish on a %s of the season feed',
		async (status) => {
			preferLanguages(['es']);
			stubRoutes({
				[CAL_URL]: [answerWith(calendarFeed())],
				[pastUrl(2005)]: [answerStatus(status)]
			});
			await renderSeason('?season=2005');
			expect(screen.getByText('Temporada 2004-05')).toBeTruthy();
		}
	);

	it.each(['?season=abcd', '?season=1990', '?season=2027'])(
		'loads the current feed and polls it for %s',
		async (query) => {
			stubRoutes({
				[CAL_URL]: [answerWith(calendarFeed())],
				[FEED_URL]: [answerWith(fixture('after'))]
			});
			const { container } = await renderSeason(query);
			expect(calls).toEqual([CAL_URL, FEED_URL]);
			expect(container.textContent).not.toContain('Season 20');
			await vi.advanceTimersByTimeAsync(60_000);
			expect(countOf(FEED_URL)).toBe(2);
		}
	);

	it('shows the current season and no select when the calendar answers 503', async () => {
		stubRoutes({ [CAL_URL]: [answerStatus(503)], [FEED_URL]: [answerWith(fixture('after'))] });
		await renderSeason('?season=2005');
		expect(calls).toEqual([CAL_URL, FEED_URL]);
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('renders the mobile classes for ?season=2005 on a 390px layout', async () => {
		vi.stubGlobal(
			'matchMedia',
			vi.fn(() => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }))
		);
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(fixture('after'))]
		});
		const { container } = await renderSeason('?season=2005');
		expect(container.querySelector('.sections.mobile')).not.toBeNull();
		expect(container.querySelector('.all-star-games.mobile .cards')).not.toBeNull();
	});

	it('lists every season of the calendar and navigates with goto', async () => {
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[FEED_URL]: [answerWith(fixture('after'))]
		});
		await renderSeason('');
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect(select.options).toHaveLength(calendarFeed().seasons.length);
		choose('2005');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/all-star?season=2005');
		choose('2027');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/all-star');
	});

	it('shows the edition frame with its caption on a past season that has an edition video', async () => {
		const feed = fixture('after');
		feed.edition.editionHighlight = highlight;
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [pastUrl(2005)]: [answerWith(feed)] });
		await renderSeason('?season=2005');
		expect(screen.getByText('Edition highlights')).toBeTruthy();
		expect(screen.getByRole('button', { name: 'Play Edition recap' })).toBeTruthy();
	});

	it('shows the placeholder and no caption on a past season with no edition video', async () => {
		const feed = fixture('after');
		feed.edition.editionHighlight = null;
		for (const game of feed.edition.games) game.highlights = null;
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [pastUrl(2005)]: [answerWith(feed)] });
		await renderSeason('?season=2005');
		expect(screen.queryByText('Edition highlights')).toBeNull();
		expect(screen.getByText('Highlights not available')).toBeTruthy();
	});

	it('shows the edition frame on the current after state', async () => {
		const feed = fixture('after');
		feed.edition.editionHighlight = highlight;
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [FEED_URL]: [answerWith(feed)] });
		await renderSeason('');
		expect(screen.getByText('Edition highlights')).toBeTruthy();
	});

	it('links the Last time champion card when the previous edition has a video, not otherwise', async () => {
		const feed = fixture('before');
		feed.previous!.editionHighlight = highlight;
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [FEED_URL]: [answerWith(feed)] });
		const linked = await renderSeason('');
		const card = linked.container.querySelector('a.champion-card');
		expect(card?.getAttribute('href')).toBe(highlight.embedUrl);
		expect(card?.getAttribute('target')).toBe('_blank');
		linked.unmount();

		feed.previous!.editionHighlight = null;
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [FEED_URL]: [answerWith(feed)] });
		const plain = await renderSeason('');
		expect(plain.container.querySelector('a.champion-card')).toBeNull();
		expect(plain.container.querySelector('.champion-card')).not.toBeNull();
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es']);
		const feed = fixture('after');
		feed.edition.editionHighlight = highlight;
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [pastUrl(2005)]: [answerWith(feed)] });
		await renderSeason('?season=2005');
		expect(screen.getByText('Temporada 2004-05')).toBeTruthy();
		expect(screen.getByText('Resumen de la edición')).toBeTruthy();
	});
});
