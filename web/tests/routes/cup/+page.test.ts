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
// - Polls every 60 s, and every 5 minutes once the Cup is complete; pauses while the tab is hidden and loads at once when visible again
// - Keeps the last feed on screen when a later poll fails
// - Opens a node: loads its matchup with a no-cache request, shows the panel, polls it again at 60 s while open and stops after Esc
// - A failed matchup shows the unavailable line inside the panel while the bracket stays
// - Renders in Spanish
// - With ?season: loads the calendar, then only the season Cup feed, once; no polling; the tag; no live badge or current stage; 503 and 404 states
// - A malformed or current ?season loads the current feed and polls it
// - A ?season before 2024 requests its season feed, shows the unavailable row and the select, and does not poll; the select keeps the season on show in its options (ADR 0054)
// - The unavailable state of a past season keeps the Season tag; the current season's has none
// - A season change or an unmount closes the current matchup poller of an open node
// - The select lists the calendar seasons from 2024 and navigates with goto
// - A past matchup loads once from the season URL, shows the path and the current-season-only line, and no roster; Spanish
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
import { SvelteURL } from 'svelte/reactivity';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CupFeed } from '../../../src/lib/contract/cup';
import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/cup/+page.svelte';

const seasonMocks = vi.hoisted(() => ({
	calendar: undefined as string | undefined,
	past: undefined as string | undefined,
	pastMatchup: undefined as string | undefined,
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
	matchup: undefined as string | undefined
}));
vi.mock('../../../src/lib/feed/config', () => ({
	get calendarFeedUrl() {
		return seasonMocks.calendar;
	},
	get seasonCupFeedUrl() {
		return seasonMocks.past;
	},
	get seasonCupMatchupFeedUrl() {
		return seasonMocks.pastMatchup;
	},
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
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
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

	it('polls every 5 minutes once the Cup is complete', async () => {
		stubFetch(answerWith(pastRecorded()));
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
			headers: { accept: 'application/json' },
			signal: expect.anything()
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
		await fireEvent.click(screen.getByRole('button', { name: 'Torneos' }));
		expect(screen.getByRole('link', { name: 'Copa' })).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Copa NBA' })).toBeTruthy();
		expect(
			screen.getAllByText('Fase de grupos · 16 de 60 partidos jugados').length
		).toBeGreaterThan(0);
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});
});

const CAL_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CAL_URL = 'https://feeds.example.com/seasons/current/calendar.json';
const PAST_TEMPLATE = 'https://feeds.example.com/seasons/{season}/cup.json';
const PAST_MATCHUP_TEMPLATE = 'https://feeds.example.com/seasons/{season}/cup/matchups/{slot}.json';
const pastUrl = (season: number) => `https://feeds.example.com/seasons/${season}/cup.json`;
const pastMatchupUrl = (season: number, slot: string) =>
	`https://feeds.example.com/seasons/${season}/cup/matchups/${slot}.json`;
const fixtures = join(__dirname, '..', '..', 'lib', 'feed', 'fixtures');
const calendarFeed = () => JSON.parse(readFileSync(join(fixtures, 'calendar.json'), 'utf8'));
const pastRecorded = (): CupFeed =>
	JSON.parse(readFileSync(join(fixtures, 'cup-complete.json'), 'utf8')) as CupFeed;

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
	seasonMocks.url = new URL(`http://localhost/cup${query}`);
	const result = render(Page);
	await settleAll();
	return result;
}

function choose(value: string) {
	const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
	select.value = value;
	select.dispatchEvent(new Event('change', { bubbles: true }));
}

describe('Cup page season selector', () => {
	beforeEach(() => {
		seasonMocks.calendar = CAL_TEMPLATE;
		seasonMocks.past = PAST_TEMPLATE;
		seasonMocks.pastMatchup = PAST_MATCHUP_TEMPLATE;
		seasonMocks.goto.mockReset();
	});

	afterEach(() => {
		seasonMocks.calendar = undefined;
		seasonMocks.past = undefined;
		seasonMocks.pastMatchup = undefined;
		seasonMocks.url = new URL('http://localhost/');
	});

	it('loads the calendar, then only the season feed, for ?season=2025', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2025)]: [answerJson(pastRecorded())]
		});
		const { container } = await renderSeason('?season=2025');
		expect(calls).toEqual([CAL_URL, pastUrl(2025)]);
		expect(screen.getByText('Season 2026-27')).toBeTruthy();
		expect(container.querySelector('.live-badge')).toBeNull();
		expect(container.querySelector('.stage-strip .current')).toBeNull();
	});

	it('does not poll a past season', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2025)]: [answerJson(pastRecorded())]
		});
		await renderSeason('?season=2025');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(countOf(pastUrl(2025))).toBe(1);
		expect(countOf(CAL_URL)).toBe(1);
	});

	it('shows the loading skeleton and the select while the season feed is pending', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [pastUrl(2025)]: [never] });
		const { container } = await renderSeason('?season=2025');
		expect(container.querySelector('[aria-busy="true"]')).toBeTruthy();
		expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
	});

	it.each([503, 404])(
		'shows the unavailable row and the select on a %s of the season feed',
		async (status) => {
			stubRoutes({
				[CAL_URL]: [answerJson(calendarFeed())],
				[pastUrl(2025)]: [answerStatus(status)]
			});
			await renderSeason('?season=2025');
			expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
			expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
		}
	);

	it.each(['?season=abcd', '?season=2027'])(
		'loads the current feed and polls it for %s',
		async (query) => {
			stubRoutes({
				[CAL_URL]: [answerJson(calendarFeed())],
				[FEED_URL]: [answerJson(recorded())]
			});
			await renderSeason(query);
			expect(calls).toEqual([CAL_URL, FEED_URL]);
			await vi.advanceTimersByTimeAsync(60_000);
			expect(countOf(FEED_URL)).toBe(2);
		}
	);

	it.each([2023, 1999])(
		'requests the season feed and shows the unavailable row for ?season=%i',
		async (season) => {
			stubRoutes({
				[CAL_URL]: [answerJson(calendarFeed())],
				[pastUrl(season)]: [answerStatus(404)],
				[FEED_URL]: [answerJson(recorded())]
			});
			await renderSeason(`?season=${season}`);
			expect(calls).toEqual([CAL_URL, pastUrl(season)]);
			expect(countOf(FEED_URL)).toBe(0);
			expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
			expect(screen.getByRole('combobox', { name: 'Season' })).toBeTruthy();
			await vi.advanceTimersByTimeAsync(10 * 60_000);
			expect(countOf(pastUrl(season))).toBe(1);
		}
	);

	it('keeps 2022-23 in the select next to the unavailable state for ?season=2023 (ADR 0044)', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2023)]: [answerStatus(404)]
		});
		await renderSeason('?season=2023');
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect(select.value).toBe('2023');
		expect([...select.options].map((option) => option.value)).toContain(select.value);
		expect([...select.options].map((option) => option.textContent)).toContain('2022-23');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
	});

	it('keeps the Season tag on the unavailable state of a past season', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2025)]: [answerStatus(503)]
		});
		await renderSeason('?season=2025');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.getByText('Season 2024-25')).toBeTruthy();
	});

	it('shows no Season tag on the unavailable state of the current season', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [FEED_URL]: [answerStatus(503)] });
		await renderSeason('');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.queryByText(/^Season /)).toBeNull();
	});

	it('stops the current matchup poller when the season changes', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[FEED_URL]: [answerJson(recorded())],
			[MATCHUP_URL]: [answerJson(matchupFeed())],
			[pastUrl(2025)]: [answerJson(pastRecorded())]
		});
		const reactive = new SvelteURL('http://localhost/cup');
		seasonMocks.url = reactive;
		render(Page);
		await settleAll();
		await fireEvent.click(screen.getByRole('button', { name: /^Championship ·/ }));
		await settleAll();
		const before = countOf(MATCHUP_URL);
		expect(before).toBeGreaterThan(0);
		reactive.search = '?season=2025';
		await settleAll();
		expect(countOf(pastUrl(2025))).toBe(1);
		await vi.advanceTimersByTimeAsync(180_000);
		expect(countOf(MATCHUP_URL)).toBe(before);
	});

	it('stops the current matchup poller when the page unmounts', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[FEED_URL]: [answerJson(recorded())],
			[MATCHUP_URL]: [answerJson(matchupFeed())]
		});
		const { unmount } = await renderSeason('');
		await fireEvent.click(screen.getByRole('button', { name: /^Championship ·/ }));
		await settleAll();
		const before = countOf(MATCHUP_URL);
		unmount();
		await vi.advanceTimersByTimeAsync(180_000);
		expect(countOf(MATCHUP_URL)).toBe(before);
	});

	it('shows the current season and no select when the calendar answers 503', async () => {
		stubRoutes({ [CAL_URL]: [answerStatus(503)], [FEED_URL]: [answerJson(recorded())] });
		await renderSeason('?season=2025');
		expect(calls).toEqual([CAL_URL, FEED_URL]);
		expect(screen.queryByRole('combobox')).toBeNull();
	});

	it('lists the calendar seasons from 2023-24 only', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [FEED_URL]: [answerJson(recorded())] });
		await renderSeason('');
		const select = screen.getByRole('combobox', { name: 'Season' }) as HTMLSelectElement;
		expect([...select.options].map((option) => option.textContent)).toEqual([
			'2026-27',
			'2025-26',
			'2024-25',
			'2023-24'
		]);
		expect(select.value).toBe('2027');
	});

	it('goes to ?season=2025 when 2025 is chosen and to the bare route for the current season', async () => {
		stubRoutes({ [CAL_URL]: [answerJson(calendarFeed())], [FEED_URL]: [answerJson(recorded())] });
		await renderSeason('');
		choose('2025');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/cup?season=2025');
		choose('2027');
		expect(seasonMocks.goto).toHaveBeenLastCalledWith('/cup');
	});

	it('opens a node of a past season: loads the season matchup once, shows the path and the note, no roster', async () => {
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2025)]: [answerJson(pastRecorded())],
			[pastMatchupUrl(2025, 'final')]: [answerJson(matchupFeed())]
		});
		await renderSeason('?season=2025');
		await fireEvent.click(screen.getByRole('button', { name: /^Championship ·/ }));
		await settleAll();
		expect(countOf(pastMatchupUrl(2025, 'final'))).toBe(1);
		const panel = screen.getByRole('dialog', { name: 'Championship' });
		expect(panel.textContent).toContain('Path');
		expect(panel.textContent).toContain('Rosters are shown for the current season only');
		expect(panel.querySelector('table')).toBeNull();
		await vi.advanceTimersByTimeAsync(180_000);
		expect(countOf(pastMatchupUrl(2025, 'final'))).toBe(1);
	});

	it('renders in Spanish', async () => {
		preferLanguages(['es']);
		stubRoutes({
			[CAL_URL]: [answerJson(calendarFeed())],
			[pastUrl(2025)]: [answerJson(pastRecorded())],
			[pastMatchupUrl(2025, 'final')]: [answerJson(matchupFeed())]
		});
		await renderSeason('?season=2025');
		expect(screen.getByText('Temporada 2026-27')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: /^Final ·/ }));
		await settleAll();
		expect(screen.getByRole('dialog').textContent).toContain(
			'Las plantillas solo se muestran de la temporada actual'
		);
	});
});
