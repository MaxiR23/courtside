// web/tests/routes/day/[date]/+page.test.ts
//
// Tests for the day page.
//
// Tested:
// - The route turns off prerender and server rendering
// - Loads the day in the URL and renders the date, the weekday, the season label and one card per game, each linking to /game/{id}
// - An expanded card shows the highlights block with its search link, plays a highlight in place, and has no stats notice (ADR 0054); with no video platform it has no block
// - The game list is named "Games on {date}" under a Games kicker
// - A window day of the sheet links to /?day= and a day after today is not a link
// - Shows the empty-day message for a day with no game
// - Shows the loading skeleton until the first load settles
// - Shows the data unavailable row on a 503, in English and in Spanish, and with no day feed URL configured
// - A 404 for a date in the games feed's days goes to /?day=YYYY-MM-DD with replaceState; a 404 for 1993-09-30 shows the unavailable row
// - The arrows link to the previous and next day with games in the calendar, across the gap of the lockout season
// - The arrows are hidden at the season's first and last day, and when the calendar answers 503
// - The page is not polled: no further request after 120 s
//
// What is covered:
// - The page wired end to end: config, fetch, loader, props layer, header, cards, footer
// - Recorded feeds (tests/lib/feed/fixtures/day.json, calendar.json, games.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/day/[date]/+page.test.ts"
//
// SEE: web/src/routes/day/[date]/+page.svelte
import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { DayFeed } from '../../../../src/lib/contract/days';
import { preferLanguages } from '../../../prefer-languages';

import Page from '../../../../src/routes/day/[date]/+page.svelte';

const navigation = vi.hoisted(() => ({ goto: vi.fn() }));
vi.mock('$app/navigation', () => ({
	goto: navigation.goto,
	afterNavigate: () => {}
}));

const config = vi.hoisted(() => ({
	day: undefined as string | undefined,
	calendar: undefined as string | undefined,
	games: undefined as string | undefined,
	platform: 'Video platform' as string | undefined
}));
vi.mock('../../../../src/lib/feed/config', () => ({
	get dayFeedUrl() {
		return config.day;
	},
	get calendarFeedUrl() {
		return config.calendar;
	},
	get gamesFeedUrl() {
		return config.games;
	},
	get videoPlatformName() {
		return config.platform;
	}
}));

const DAY_TEMPLATE = 'https://feeds.example.com/days/{date}.json';
const CALENDAR_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const GAMES_URL = 'https://feeds.example.com/games.json';
const dayUrl = (date: string) => `https://feeds.example.com/days/${date}.json`;
const CALENDAR_URL = 'https://feeds.example.com/seasons/1999/calendar.json';
const UNAVAILABLE = "Data isn't available right now. Check back later.";

const fixture = <T>(name: string): T =>
	JSON.parse(
		readFileSync(join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures', name), 'utf8')
	) as T;

type Answer = () => Promise<unknown>;
const answerWith =
	(body: unknown): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
const answerStatus =
	(status: number): Answer =>
	() =>
		Promise.resolve({ ok: false, status, json: () => Promise.resolve({}) });

let answers: Record<string, Answer>;
let fetchMock: ReturnType<typeof vi.fn>;

function stubFetch(next: Record<string, Answer>) {
	answers = next;
	fetchMock = vi.fn((url: string) => {
		const answer = answers[url];
		if (!answer) throw new Error(`Unexpected URL ${url}`);
		return answer();
	});
	vi.stubGlobal('fetch', fetchMock);
}

const dayOf = (date: string): DayFeed => {
	const feed = fixture<DayFeed>('day.json');
	feed.day.date = date;
	return feed;
};

async function settle() {
	await vi.advanceTimersByTimeAsync(0);
	await tick();
}

async function renderPage(date = '1999-02-06') {
	const result = render(Page, { props: { params: { date }, data: {} } });
	await settle();
	return result;
}

beforeEach(() => {
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-10-15T16:00:00Z'));
	config.day = DAY_TEMPLATE;
	config.calendar = CALENDAR_TEMPLATE;
	config.games = GAMES_URL;
	config.platform = 'Video platform';
	navigation.goto.mockReset();
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('day route', () => {
	it('turns off prerender and server rendering for this route', async () => {
		const options = await import('../../../../src/routes/day/[date]/+page');
		expect(options.prerender).toBe(false);
		expect(options.ssr).toBe(false);
	});
});

describe('day page', () => {
	it('renders the date, the weekday, the season label and one card per game', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container } = await renderPage();
		expect(fetchMock.mock.calls[0][0]).toBe(dayUrl('1999-02-06'));
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('February 6, 1999');
		expect(container.querySelector('.meta')?.textContent).toBe('1998-99 · Saturday');
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(2);
		expect(screen.getByRole('button', { name: 'Open calendar' })).toBeTruthy();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('links each card to its game page', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container } = await renderPage();
		const hrefs = [...container.querySelectorAll('a[href^="/game/"]')].map((a) =>
			a.getAttribute('href')
		);
		expect(hrefs).toEqual(['/game/7001', '/game/7002']);
	});

	it('names the game list under a Games kicker and draws the season code of a historical side', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container } = await renderPage();
		expect(screen.getByRole('list', { name: 'Games on February 6, 1999' })).toBeTruthy();
		expect(container.querySelector('.page-section .kicker')?.textContent).toBe('Games');
		const away = container.querySelector('a[href="/team/den"]');
		expect(away?.textContent).toBe('SEA');
	});

	it('shows the highlights block with its search link and no stats notice in an expanded card', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container } = await renderPage();
		const card = container.querySelector('li') as HTMLElement;
		await fireEvent.click(card.querySelector('button.toggle') as HTMLElement);
		const first = within(card);
		expect(first.getByText('Highlights')).toBeTruthy();
		expect(first.getByText('Video platform')).toBeTruthy();
		expect(first.getByText('Full game highlights')).toBeTruthy();
		expect(first.queryByText("Stats aren't available for this game.")).toBeNull();
		expect(first.queryByText('Stats will be available soon.')).toBeNull();
		expect(first.getByRole('link', { name: 'Game center' }).getAttribute('href')).toBe(
			'/game/7001'
		);
	});

	it('plays a highlight in place', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container } = await renderPage();
		const card = container.querySelector('li') as HTMLElement;
		await fireEvent.click(card.querySelector('button.toggle') as HTMLElement);
		await fireEvent.click(within(card).getByRole('button', { name: /Full game highlights/ }));
		expect(card.querySelector('iframe')?.getAttribute('src')).toBe(
			'https://example.com/embed/1?autoplay=1'
		);
	});

	it('leaves the highlights out when no video platform is configured', async () => {
		config.platform = undefined;
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container } = await renderPage();
		const card = container.querySelector('li') as HTMLElement;
		await fireEvent.click(card.querySelector('button.toggle') as HTMLElement);
		expect(within(card).queryByText('Highlights')).toBeNull();
	});

	it('shows the empty-day message for a day with no game', async () => {
		const feed = fixture<DayFeed>('day.json');
		feed.day.games = [];
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(feed),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		await renderPage();
		expect(screen.getByText('No games scheduled for this day.')).toBeTruthy();
	});

	it('shows the loading skeleton until the first load settles', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: () => new Promise(() => {}),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container } = await renderPage();
		expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
	});

	it('shows the data unavailable row on a 503 and asks for no calendar', async () => {
		stubFetch({ [dayUrl('1999-02-06')]: answerStatus(503) });
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('shows the data unavailable row in Spanish for a Spanish browser', async () => {
		preferLanguages(['es-ES']);
		stubFetch({ [dayUrl('1999-02-06')]: answerStatus(503) });
		await renderPage();
		expect(screen.queryByText(UNAVAILABLE)).toBeNull();
		expect(
			screen.getByText(
				'Los datos no están disponibles en este momento. Vuelve a consultar más tarde.'
			)
		).toBeTruthy();
	});

	it('shows the data unavailable row with no day feed URL configured', async () => {
		config.day = undefined;
		stubFetch({});
		await renderPage();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it("goes to the home with the day when a 404 date is one of the games feed's days", async () => {
		stubFetch({
			[dayUrl('2026-10-03')]: answerStatus(404),
			[GAMES_URL]: answerWith(fixture('games.json'))
		});
		await renderPage('2026-10-03');
		expect(navigation.goto).toHaveBeenCalledTimes(1);
		expect(navigation.goto).toHaveBeenCalledWith('/?day=2026-10-03', { replaceState: true });
	});

	it('shows the data unavailable row for a 404 date outside the games feed days', async () => {
		stubFetch({
			[dayUrl('1993-09-30')]: answerStatus(404),
			[GAMES_URL]: answerWith(fixture('games.json'))
		});
		await renderPage('1993-09-30');
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(navigation.goto).not.toHaveBeenCalled();
	});
});

describe('day page arrows', () => {
	const arrows = () => ({
		previous: screen.queryByRole('link', { name: 'Previous day' }),
		next: screen.queryByRole('link', { name: 'Next day' })
	});

	it('link to the previous and next day with games', async () => {
		stubFetch({
			[dayUrl('1999-02-09')]: answerWith(dayOf('1999-02-09')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		await renderPage('1999-02-09');
		expect(arrows().previous?.getAttribute('href')).toBe('/day/1999-02-07');
		expect(arrows().next?.getAttribute('href')).toBe('/day/1999-03-01');
	});

	it('cross the gap of the lockout season', async () => {
		stubFetch({
			[dayUrl('1999-03-01')]: answerWith(dayOf('1999-03-01')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		await renderPage('1999-03-01');
		expect(arrows().previous?.getAttribute('href')).toBe('/day/1999-02-09');
		expect(arrows().next?.getAttribute('href')).toBe('/day/1999-05-05');
	});

	it('hide the previous arrow at the first day of the season', async () => {
		stubFetch({
			[dayUrl('1999-02-05')]: answerWith(dayOf('1999-02-05')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		await renderPage('1999-02-05');
		expect(arrows().previous).toBeNull();
		expect(arrows().next?.getAttribute('href')).toBe('/day/1999-02-06');
	});

	it('hide the next arrow at the last day of the season', async () => {
		stubFetch({
			[dayUrl('1999-05-05')]: answerWith(dayOf('1999-05-05')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		await renderPage('1999-05-05');
		expect(arrows().next).toBeNull();
		expect(arrows().previous?.getAttribute('href')).toBe('/day/1999-03-01');
	});

	it('are hidden when the calendar answers 503', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerStatus(503)
		});
		await renderPage();
		expect(screen.getByRole('heading', { level: 1 })).toBeTruthy();
		expect(arrows().previous).toBeNull();
		expect(arrows().next).toBeNull();
	});
});

describe('day page calendar sheet', () => {
	const CURRENT_URL = 'https://feeds.example.com/seasons/2027/calendar.json';
	const currentDay = (date: string): DayFeed => ({ ...dayOf(date), season: 2027 });

	async function openSheet(date: string) {
		stubFetch({
			[dayUrl(date)]: answerWith(currentDay(date)),
			[CURRENT_URL]: answerWith(fixture('calendar-current.json'))
		});
		await renderPage(date);
		await fireEvent.click(screen.getByRole('button', { name: 'Open calendar' }));
		await settle();
		return screen.getByRole('dialog', { name: 'Calendar' });
	}

	it('links a window day of the sheet to /?day= and requests no day feed for it', async () => {
		const dialog = await openSheet('2026-10-14');
		const link = within(dialog).getByRole('link', { name: 'October 3, 2026' });
		expect(link.getAttribute('href')).toBe('/?day=2026-10-03');
		await fireEvent.click(link);
		expect(fetchMock.mock.calls.map((call) => call[0])).not.toContain(dayUrl('2026-10-03'));
	});

	it('links another day with games to its page', async () => {
		const dialog = await openSheet('2026-10-14');
		expect(
			within(dialog).getByRole('link', { name: 'October 15, 2026' }).getAttribute('href')
		).toBe('/day/2026-10-15');
	});

	it('does not link a day after today', async () => {
		const dialog = await openSheet('2026-10-14');
		expect(within(dialog).queryByRole('link', { name: 'October 20, 2026' })).toBeNull();
		expect(
			(within(dialog).getByRole('button', { name: 'Next month' }) as HTMLButtonElement).disabled
		).toBe(true);
	});
});

describe('day page polling', () => {
	it('makes no further request after 120 s', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(120_000);
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});
});
