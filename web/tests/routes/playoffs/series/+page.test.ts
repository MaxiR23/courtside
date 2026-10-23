// web/tests/routes/playoffs/series/+page.test.ts
//
// Tests for the full series route.
//
// Tested:
// - The route turns off server rendering and keeps prerender from the layout
// - ?id=east-r1-1 loads the playoffs feed only and renders the series, its game cards and the back link
// - ?id=finals loads the finals feed when the Finals are on and shows the leader line; no finals request before that
// - With ?season: loads the calendar, then the season feed once, no polling; the back link keeps the season
// - A past ?id=finals loads the season finals feed once
// - An unknown id, an undecided series and a missing id show the not-available message and the back link
// - A 503 or no configured URL shows the data unavailable row; the skeleton shows until the first load settles
// - The current season polls again at 60 s, and a later success replaces a failed state
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, component, footer
// - Recorded feeds (tests/lib/feed/fixtures/playoffs-*.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/playoffs/series/+page.test.ts
//
// SEE: web/src/routes/playoffs/series/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { PlayoffsFeed, PlayoffsState } from '../../../../src/lib/contract/playoffs';
import type { PlayoffsFinalsFeed } from '../../../../src/lib/contract/playoffs-finals';

import Page from '../../../../src/routes/playoffs/series/+page.svelte';

const mocks = vi.hoisted(() => ({
	calendar: undefined as string | undefined,
	past: undefined as string | undefined,
	pastFinals: undefined as string | undefined,
	url: new URL('http://localhost/playoffs/series'),
	feed: undefined as string | undefined,
	finals: undefined as string | undefined
}));
vi.mock('$app/state', () => ({
	page: {
		get url() {
			return mocks.url;
		}
	}
}));
vi.mock('../../../../src/lib/feed/config', () => ({
	get calendarFeedUrl() {
		return mocks.calendar;
	},
	get seasonPlayoffsFeedUrl() {
		return mocks.past;
	},
	get seasonPlayoffsFinalsFeedUrl() {
		return mocks.pastFinals;
	},
	get playoffsFeedUrl() {
		return mocks.feed;
	},
	get playoffsFinalsFeedUrl() {
		return mocks.finals;
	}
}));

const FEED_URL = 'https://feeds.example.com/playoffs.json';
const FINALS_URL = 'https://feeds.example.com/playoffs/finals.json';
const CAL_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CAL_URL = 'https://feeds.example.com/seasons/current/calendar.json';
const PAST_TEMPLATE = 'https://feeds.example.com/seasons/{season}/playoffs.json';
const PAST_FINALS_TEMPLATE = 'https://feeds.example.com/seasons/{season}/playoffs/finals.json';
const pastUrl = (season: number) => `https://feeds.example.com/seasons/${season}/playoffs.json`;
const pastFinalsUrl = (season: number) =>
	`https://feeds.example.com/seasons/${season}/playoffs/finals.json`;

const fixture = <T>(file: string): T =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures', file), 'utf8')
	) as T;
const bracket = () => fixture<PlayoffsFeed>('playoffs-bracket.json');
const inState = (state: PlayoffsState): PlayoffsFeed => {
	const feed = fixture<PlayoffsFeed>('playoffs-complete.json');
	feed.state = state;
	if (state !== 'complete') feed.champion = null;
	if (state === 'playoffs') feed.currentRound = 1;
	return feed;
};
const finalsFeed = () => fixture<PlayoffsFinalsFeed>('playoffs-finals.json');
const calendarFeed = () => fixture<{ seasons: unknown[] }>('calendar.json');

const UNAVAILABLE = "Data isn't available right now. Check back later.";
const NOT_FOUND = "This series isn't available.";

type Answer = () => Promise<unknown>;
const answerWith =
	(body: unknown): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
const answerStatus =
	(status: number): Answer =>
	() =>
		Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) });
const never: Answer = () => new Promise(() => {});

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
const countOf = (url: string) => calls.filter((call) => call === url).length;

async function settle() {
	await vi.advanceTimersByTimeAsync(0);
	await tick();
}

async function renderAt(query: string) {
	mocks.url = new URL(`http://localhost/playoffs/series${query}`);
	const result = render(Page);
	for (let i = 0; i < 4; i++) await settle();
	return result;
}

const backHrefs = () =>
	screen.getAllByRole('link', { name: '← Bracket' }).map((link) => link.getAttribute('href'));
const backHref = () => backHrefs()[0];

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2027-06-20T23:30:00Z'));
	vi.stubGlobal(
		'matchMedia',
		vi.fn(() => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }))
	);
	mocks.feed = FEED_URL;
	mocks.finals = FINALS_URL;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
	mocks.calendar = undefined;
	mocks.past = undefined;
	mocks.pastFinals = undefined;
	mocks.url = new URL('http://localhost/playoffs/series');
});

describe('Series route', () => {
	it('turns off server rendering and inherits prerender from the layout', async () => {
		const options = await import('../../../../src/routes/playoffs/series/+page');
		expect(options.ssr).toBe(false);
		expect((options as { prerender?: boolean }).prerender).toBeUndefined();
	});
});

describe('Series page', () => {
	it('renders a series from the playoffs feed alone, with its cards and the back link', async () => {
		stubRoutes({ [FEED_URL]: [answerWith(bracket())] });
		const { container } = await renderAt('?id=east-r1-1');
		expect(calls).toEqual([FEED_URL]);
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('East · Round 1');
		expect(container.textContent).toContain('QXA');
		expect(container.textContent).toContain('QXH');
		expect(container.querySelectorAll('ol > li')).toHaveLength(5);
		expect(backHref()).toBe('/playoffs#bracket');
		expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
	});

	it('loads the finals feed for the Finals when they are on and shows the leader line', async () => {
		stubRoutes({
			[FEED_URL]: [answerWith(inState('complete'))],
			[FINALS_URL]: [answerWith(finalsFeed())]
		});
		const { container } = await renderAt('?id=finals');
		expect(countOf(FINALS_URL)).toBe(1);
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('NBA Finals');
		expect(container.querySelector('.leaders')?.textContent).toContain('PTS');
	});

	it('requests no finals feed before the Finals, or for another series', async () => {
		stubRoutes({ [FEED_URL]: [answerWith(inState('playoffs'))] });
		await renderAt('?id=finals');
		expect(countOf(FINALS_URL)).toBe(0);
		stubRoutes({ [FEED_URL]: [answerWith(inState('complete'))] });
		await renderAt('?id=east-r1-1');
		expect(countOf(FINALS_URL)).toBe(0);
	});

	it('keeps the series on screen when the finals feed fails', async () => {
		stubRoutes({
			[FEED_URL]: [answerWith(inState('complete'))],
			[FINALS_URL]: [answerStatus(503)]
		});
		const { container } = await renderAt('?id=finals');
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('NBA Finals');
		expect(container.querySelector('.leaders')).toBeNull();
	});

	it('loads a past season once, keeps the season on the back link and does not poll', async () => {
		mocks.calendar = CAL_TEMPLATE;
		mocks.past = PAST_TEMPLATE;
		mocks.pastFinals = PAST_FINALS_TEMPLATE;
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(bracket())]
		});
		const { container } = await renderAt('?id=east-r1-1&season=2005');
		expect(calls).toEqual([CAL_URL, pastUrl(2005)]);
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(countOf(pastUrl(2005))).toBe(1);
		expect(container.querySelectorAll('ol > li')).toHaveLength(5);
		expect(backHref()).toBe('/playoffs?season=2005#bracket');
	});

	it('loads the season finals feed once for a past Finals', async () => {
		mocks.calendar = CAL_TEMPLATE;
		mocks.past = PAST_TEMPLATE;
		mocks.pastFinals = PAST_FINALS_TEMPLATE;
		stubRoutes({
			[CAL_URL]: [answerWith(calendarFeed())],
			[pastUrl(2005)]: [answerWith(inState('complete'))],
			[pastFinalsUrl(2005)]: [answerWith(finalsFeed())]
		});
		await renderAt('?id=finals&season=2005');
		expect(calls).toEqual([CAL_URL, pastUrl(2005), pastFinalsUrl(2005)]);
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(countOf(pastFinalsUrl(2005))).toBe(1);
	});

	it.each(['?id=nope', '?id=east-r2-1', ''])(
		'says the series is not available for %s, with the back link',
		async (query) => {
			stubRoutes({ [FEED_URL]: [answerWith(bracket())] });
			await renderAt(query);
			expect(screen.getByText(NOT_FOUND)).toBeTruthy();
			expect(backHrefs().every((href) => href === '/playoffs#bracket')).toBe(true);
		}
	);

	it('shows the data unavailable row on a 503 and with no URL configured', async () => {
		stubRoutes({ [FEED_URL]: [answerStatus(503)] });
		const first = await renderAt('?id=east-r1-1');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		first.unmount();
		mocks.feed = undefined;
		stubRoutes({});
		await renderAt('?id=east-r1-1');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(calls).toEqual([]);
	});

	it('shows the skeleton until the first load settles', async () => {
		let finish: (answer: unknown) => void = () => {};
		stubRoutes({ [FEED_URL]: [() => new Promise((resolve) => (finish = resolve))] });
		const { container } = await renderAt('?id=east-r1-1');
		expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
		finish({ ok: true, status: 200, json: () => Promise.resolve(bracket()) });
		await settle();
		expect(container.querySelector('[aria-busy="true"]')).toBeNull();
		expect(container.querySelectorAll('ol > li')).toHaveLength(5);
	});

	it('shows the skeleton while a past season is pending', async () => {
		mocks.calendar = CAL_TEMPLATE;
		mocks.past = PAST_TEMPLATE;
		stubRoutes({ [CAL_URL]: [answerWith(calendarFeed())], [pastUrl(2005)]: [never] });
		const { container } = await renderAt('?id=east-r1-1&season=2005');
		expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
	});

	it('polls the current season at 60 s and replaces a failed state with a later success', async () => {
		stubRoutes({ [FEED_URL]: [answerStatus(503), answerWith(bracket())] });
		await renderAt('?id=east-r1-1');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		await vi.advanceTimersByTimeAsync(60_000);
		await tick();
		expect(countOf(FEED_URL)).toBe(2);
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('East · Round 1');
	});
});
