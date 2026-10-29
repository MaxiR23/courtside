// web/tests/routes/day/[date]/+page.test.ts
//
// Tests for the day page.
//
// Tested:
// - The route turns off prerender and server rendering
// - Loads the day in the URL and renders the date, the weekday, the season label and one card per game, each linking to /game/{id}
// - An expanded card shows the highlights block with its search link, plays a highlight in place, and has no stats notice (ADR 0054); with no video platform it has no block
// - A past final card reads its game detail once, on its first expand, and shows its leaders and team stats; a second expand does not read again; a failed read shows neither and no notice; with no game detail URL nothing is read
// - The game list is named "Games on {date}" under a Games kicker
// - A window day of the sheet links to /?day= and a day after today is not a link
// - Shows the empty-day message for a day with no game
// - Shows the loading skeleton until the first load settles
// - Shows the data unavailable row on a 503, in English and in Spanish, and with no day feed URL configured
// - A 404 for a date in the games feed's days goes to /?day=YYYY-MM-DD with replaceState; a 404 for 1993-09-30 shows the unavailable row
// - The arrows link to the previous and next day with games in the calendar, across the gap of the lockout season
// - The arrows are hidden at the season's first and last day, and when the calendar answers 503
// - When the date changes: the loading skeleton at once, then the new day, never the previous one; a 503 for the new date shows the unavailable row
// - The page is not polled: no further request after 120 s
// - The document title is "Games", the long date in the active language, then the site name; without the date while loading; the loading title in English and Spanish
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
import type { GameDetailFeed } from '../../../../src/lib/contract/game-detail';
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
	detail: undefined as string | undefined,
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
	get gameDetailFeedUrl() {
		return config.detail;
	},
	get videoPlatformName() {
		return config.platform;
	}
}));

const DAY_TEMPLATE = 'https://feeds.example.com/days/{date}.json';
const CALENDAR_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const DETAIL_TEMPLATE = 'https://feeds.example.com/games/{id}.json';
const detailUrl = (id: string) => `https://feeds.example.com/games/${id}.json`;
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
	document.title = '';
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-10-15T16:00:00Z'));
	config.day = DAY_TEMPLATE;
	config.calendar = CALENDAR_TEMPLATE;
	config.games = GAMES_URL;
	config.detail = undefined;
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

describe('day page cards read the game detail', () => {
	const detailOf = (): GameDetailFeed => {
		const detail = fixture<GameDetailFeed>('game-detail-past.json');
		detail.teamStats = {
			away: {
				fieldGoalPct: 0.5,
				threePointPct: null,
				freeThrowPct: 0.8,
				rebounds: 40,
				assists: 22,
				turnovers: 11,
				steals: 6,
				blocks: 3
			},
			home: {
				fieldGoalPct: 0.4,
				threePointPct: 0.3,
				freeThrowPct: 0.7,
				rebounds: 35,
				assists: 18,
				turnovers: 14,
				steals: 5,
				blocks: 2
			},
			leaders: {
				fieldGoalPct: 'away',
				threePointPct: null,
				freeThrowPct: 'away',
				rebounds: 'away',
				assists: 'away',
				turnovers: 'away',
				steals: 'away',
				blocks: 'away'
			}
		};
		return detail;
	};
	const base = () => ({
		[dayUrl('1999-02-06')]: answerWith(fixture('day.json')),
		[CALENDAR_URL]: answerWith(fixture('calendar.json'))
	});
	const detailCalls = () =>
		fetchMock.mock.calls.filter(([url]) =>
			String(url).startsWith('https://feeds.example.com/games/')
		);

	beforeEach(() => {
		config.detail = DETAIL_TEMPLATE;
	});

	it('reads the game detail once on the first expand and shows its leaders and team stats', async () => {
		stubFetch({ ...base(), [detailUrl('7001')]: answerWith(detailOf()) });
		const { container } = await renderPage();
		expect(detailCalls()).toHaveLength(0);
		const card = container.querySelector('li') as HTMLElement;
		const toggle = card.querySelector('button.toggle') as HTMLElement;
		await fireEvent.click(toggle);
		await settle();
		expect(detailCalls()).toHaveLength(1);
		const first = within(card);
		expect(first.getByText('Ada Quill')).toBeTruthy();
		expect(first.getByText('Bo Marlowe')).toBeTruthy();
		expect(first.getByText('31 PTS · 9 REB · — AST')).toBeTruthy();
		expect(first.queryByText("Stats aren't available for this game.")).toBeNull();
		await fireEvent.click(toggle);
		await fireEvent.click(toggle);
		await settle();
		expect(detailCalls()).toHaveLength(1);
		expect(first.getByText('Ada Quill')).toBeTruthy();
	});

	it('shows no leaders when the detail has none, and no stats when it has none', async () => {
		const detail = detailOf();
		detail.leaders = null;
		stubFetch({ ...base(), [detailUrl('7001')]: answerWith(detail) });
		const { container } = await renderPage();
		const card = container.querySelector('li') as HTMLElement;
		await fireEvent.click(card.querySelector('button.toggle') as HTMLElement);
		await settle();
		expect(within(card).queryByText('Ada Quill')).toBeNull();
		expect(within(card).getByRole('link', { name: 'Game center' })).toBeTruthy();
	});

	it('shows neither and no notice when the read fails', async () => {
		stubFetch({ ...base(), [detailUrl('7001')]: answerStatus(503) });
		const { container } = await renderPage();
		const card = container.querySelector('li') as HTMLElement;
		await fireEvent.click(card.querySelector('button.toggle') as HTMLElement);
		await settle();
		expect(detailCalls()).toHaveLength(1);
		expect(within(card).queryByText('Ada Quill')).toBeNull();
		expect(within(card).queryByText("Stats aren't available for this game.")).toBeNull();
		expect(within(card).queryByText('Stats will be available soon.')).toBeNull();
	});

	it('reads nothing for a game with no line score, which has no expand button', async () => {
		const feed = fixture<DayFeed>('day.json');
		const game = feed.day.games[0] as unknown as Record<string, unknown>;
		game.lineScore = null;
		stubFetch({ ...base(), [dayUrl('1999-02-06')]: answerWith(feed) });
		const { container } = await renderPage();
		const card = container.querySelector('li') as HTMLElement;
		expect(card.querySelector('button.toggle')).toBeNull();
		expect(detailCalls()).toHaveLength(0);
	});
});

describe('day document title', () => {
	it('is Games, the long date and the site name, in English and Spanish', async () => {
		stubFetch({ [dayUrl('1999-02-06')]: answerWith(dayOf('1999-02-06')) });
		await renderPage();
		expect(document.title).toBe('Games · February 6, 1999 · Courtside');
		preferLanguages(['es']);
		stubFetch({ [dayUrl('1999-02-06')]: answerWith(dayOf('1999-02-06')) });
		await renderPage();
		expect(document.title).toBe('Partidos · 6 de febrero de 1999 · Courtside');
	});

	it('is the section name and the site name while loading', async () => {
		stubFetch({ [dayUrl('1999-02-06')]: () => new Promise(() => {}) });
		await renderPage();
		expect(document.title).toBe('Games · Courtside');
	});

	it('is the section name and the site name while loading, in Spanish', async () => {
		preferLanguages(['es']);
		stubFetch({ [dayUrl('1999-02-06')]: () => new Promise(() => {}) });
		await renderPage();
		expect(document.title).toBe('Partidos · Courtside');
	});
});

describe('day page, when the date changes', () => {
	it('shows the loading skeleton at once, then the new day, and never the previous one', async () => {
		let resolveB: (answer: unknown) => void = () => {};
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(dayOf('1999-02-06')),
			[dayUrl('1999-02-07')]: () => new Promise((resolve) => (resolveB = resolve)),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { container, rerender } = await renderPage('1999-02-06');
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('February 6, 1999');
		await rerender({ params: { date: '1999-02-07' }, data: {} });
		expect(container.querySelector('[aria-busy="true"]')).not.toBeNull();
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
		resolveB({ ok: true, status: 200, json: () => Promise.resolve(dayOf('1999-02-07')) });
		await settle();
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('February 7, 1999');
		expect(fetchMock.mock.calls.some((call) => call[0] === dayUrl('1999-02-07'))).toBe(true);
	});

	it('shows the unavailable row for a 503 on the new date, never the previous day', async () => {
		stubFetch({
			[dayUrl('1999-02-06')]: answerWith(dayOf('1999-02-06')),
			[dayUrl('1999-02-07')]: answerStatus(503),
			[CALENDAR_URL]: answerWith(fixture('calendar.json'))
		});
		const { rerender } = await renderPage('1999-02-06');
		await rerender({ params: { date: '1999-02-07' }, data: {} });
		await settle();
		expect(screen.getByText(UNAVAILABLE)).toBeTruthy();
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
	});
});
