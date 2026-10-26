// web/tests/routes/+page.test.ts
//
// Tests for the home page.
//
// Tested:
// - Shows the search trigger in the nav
// - Renders the hero, the schedule with today's games and the footer from a recorded feed
// - Expands a played game's panel with its line score, leaders, stats and highlights
// - Links the hero's team names and the non-expandable cards' team names to /team/{code} in lowercase, and an expanded game's line score codes
// - Renders no link inside a button or another link, before and after expanding a game
// - Toggles spoiler-free mode from the nav row
// - Opens the hero's game in the schedule from Match details, on today
// - Polls again after 30 s while a game is live; pauses while the tab is hidden and loads on return
// - Shows the hero and schedule skeletons until the first feed loads, then the content or the unavailable row
// - Keeps postponed and canceled games out of the hero and in the schedule; with only those, no hero game
// - Shows the data unavailable row when the feed cannot be loaded or no feed URL is configured, in English and Spanish
// - Keeps the last feed on screen when a later poll fails
// - Shows the not-affiliated line in Spanish for es-ES and es-419 and in English for fr-FR
// - Selects the DayStrip day of ?day= after a navigation; a later or malformed day keeps today; a past day outside the feed goes to /day/ with replaceState; a later poll does not move the selection
// - The calendar sheet links a day of the feed to /?day=YYYY-MM-DD and a day outside the feed to /day/YYYY-MM-DD; a day after today is not a link
// - Before the games feed loads, the sheet links no day after the client's US Eastern today and sends the calendar's window days to the home (ADR 0054)
// - A day with games never requests the home feed; a day with only postponed and canceled games keeps the hero with no game and requests nothing
// - A day with no games requests the home feed once, across several games polls, and the hero shows the chip, the title and the Coming up card (a section after the hero on mobile)
// - A failed or unconfigured home feed leaves the date and the title only, with no Coming up, and the schedule still renders; Spanish title
// - Last games after the home feed loads, in the documented order, with links to the game pages; absent when null, failed, not configured or on a day with games
// - The empty-day box on a selected day with no games: next day and count, Go to link to /?day= inside the window, none outside it, the two-weeks message, the old row without the home feed
// - The offseason hides the schedule and Last games takes the schedule anchor; the other scenarios keep it; spoiler-free hides the Last games scores
// - Standings and Leaders after the schedule on a day with no games: the standings feed requested once, never on a day with games; two columns on a wide screen and stacked on a narrow one
// - Each of the two sections hidden when its feed fails, is not configured or its data is null, the rest of the page still rendered; the Finals preview shows the finalists, and nothing without finalsPath; one to four leader rows; Spanish
// - Team logos: a side's feed logo in the game card's large box, the code monogram for a null logo and the initials of a guest side added in memory
//
// What is covered:
// - The page wired end to end: config, fetch, polling, props layer, hero, schedule, footer
// - A recorded feed (tests/lib/feed/fixtures/games.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run tests/routes/+page.test.ts
//
// SEE: web/src/routes/+page.svelte
import { fireEvent, render, screen, within } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CalendarFeed } from '../../src/lib/contract/calendar';
import type { GamesFeed } from '../../src/lib/contract/games';
import type { HomeFeed, HomeLeader } from '../../src/lib/contract/home';
import { IDLE_POLL_MS, SLOW_POLL_MS } from '../../src/lib/feed/poller.svelte';
import { preferLanguages } from '../prefer-languages';

import Page from '../../src/routes/+page.svelte';

const navigation = vi.hoisted(() => ({
	callbacks: [] as Array<(navigation: { to: { url: URL } | null }) => void>,
	goto: vi.fn()
}));
vi.mock('$app/navigation', () => ({
	goto: navigation.goto,
	afterNavigate: (cb: (navigation: { to: { url: URL } | null }) => void) => {
		navigation.callbacks.push(cb);
	}
}));

const config = vi.hoisted(() => ({
	url: undefined as string | undefined,
	calendarUrl: undefined as string | undefined,
	homeUrl: undefined as string | undefined,
	standingsUrl: undefined as string | undefined,
	platform: undefined as string | undefined
}));
vi.mock('../../src/lib/feed/config', () => ({
	get gamesFeedUrl() {
		return config.url;
	},
	get calendarFeedUrl() {
		return config.calendarUrl;
	},
	get homeFeedUrl() {
		return config.homeUrl;
	},
	get standingsFeedUrl() {
		return config.standingsUrl;
	},
	get videoPlatformName() {
		return config.platform;
	}
}));

const FEED_URL = 'https://feeds.example.com/games.json';
const HOME_URL = 'https://feeds.example.com/home.json';
const STANDINGS_URL = 'https://feeds.example.com/standings.json';
const CALENDAR_TEMPLATE = 'https://feeds.example.com/seasons/{season}/calendar.json';
const CALENDAR_URL = 'https://feeds.example.com/seasons/current/calendar.json';
// The current season: two days of the games feed and one day outside it.
const calendar = (): CalendarFeed => ({
	...(JSON.parse(
		readFileSync(join(__dirname, '..', 'lib', 'feed', 'fixtures', 'calendar.json'), 'utf8')
	) as CalendarFeed),
	season: 2027,
	seasonLabel: '2026-27',
	firstDay: '2026-09-30',
	lastDay: '2026-10-20',
	days: ['2026-09-30', '2026-10-04', '2026-10-20'],
	windowDays: ['2026-10-03', '2026-10-04']
});
const recorded = (): GamesFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'lib', 'feed', 'fixtures', 'games.json'), 'utf8')
	) as GamesFeed;

type Answer = () => Promise<unknown>;
let homeAnswers: Answer[] = [];
let standingsAnswers: Answer[] = [];
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(feed: GamesFeed): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(feed) });
const answerFailing: Answer = () => Promise.reject(new TypeError('Failed to fetch'));

const homeFeed = (): HomeFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'lib', 'feed', 'fixtures', 'home.json'), 'utf8')
	) as HomeFeed;
const homeAnswerWith =
	(feed: HomeFeed): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(feed) });
const standingsCalls = () => fetchMock.mock.calls.filter(([url]) => url === STANDINGS_URL).length;
const homeCalls = () => fetchMock.mock.calls.filter(([url]) => url === HOME_URL).length;

/** The recorded feed with no game at all today. */
const withoutGamesToday = (): GamesFeed => {
	const feed = recorded();
	feed.days[3].games = [];
	return feed;
};

/** The recorded feed once it is already past its live game: nothing is live. */
const withoutLive = (): GamesFeed => {
	const feed = recorded();
	for (const day of feed.days) {
		day.games = day.games.filter((game) => game.status !== 'live');
	}
	return feed;
};

function stubFetch(...next: Answer[]) {
	answers = next;
	fetchMock = vi.fn((url: string) => {
		if (url === CALENDAR_URL) {
			return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(calendar()) });
		}
		if (url === HOME_URL) {
			const answer = homeAnswers.length > 1 ? homeAnswers.shift() : homeAnswers[0];
			if (!answer) throw new Error(`Unexpected URL ${url}`);
			return answer();
		}
		if (url === STANDINGS_URL) {
			const answer = standingsAnswers.length > 1 ? standingsAnswers.shift() : standingsAnswers[0];
			if (!answer) throw new Error(`Unexpected URL ${url}`);
			return answer();
		}
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

const card = (container: HTMLElement, id: string) =>
	container.querySelector(`#game-${id}`) as HTMLElement;

beforeEach(() => {
	vi.useFakeTimers();
	// Five minutes after the recorded feed was generated.
	vi.setSystemTime(new Date('2026-10-04T23:05:00Z'));
	config.url = FEED_URL;
	config.calendarUrl = undefined;
	config.homeUrl = undefined;
	config.standingsUrl = undefined;
	homeAnswers = [];
	standingsAnswers = [];
	navigation.callbacks = [];
	navigation.goto.mockReset();
	config.platform = 'Video platform';
	Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
	Reflect.deleteProperty(Element.prototype, 'scrollIntoView');
});

describe('home page with a feed', () => {
	it("renders the hero, the schedule with today's games and the footer from a recorded feed", async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(
			screen.getByRole('heading', { level: 1, name: /^Warriors\s*at\s+Lakers$/ })
		).toBeTruthy();
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe('Sunday, October 4');
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(6);
		expect(screen.getByText('Updated 5 min ago')).toBeTruthy();
		expect(screen.getByText('Delayed', { selector: '.status-line' })).toBeTruthy();
		expect(screen.getByText('Postponed', { selector: '.status-line' })).toBeTruthy();
		expect(screen.getByText('Canceled', { selector: '.status-line' })).toBeTruthy();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners.'
			)
		).toBeTruthy();
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('shows the search trigger in the nav', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(screen.getByRole('button', { name: 'Search' })).toBeTruthy();
	});

	it('keeps postponed and canceled games out of the hero and in the schedule', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(container.querySelector('.hero .position')?.textContent).toBe('01 / 04');
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(6);
		expect(card(container, 'g-postponed')).not.toBeNull();
		expect(card(container, 'g-canceled')).not.toBeNull();
	});

	it("expands a played game's panel with its line score, leaders, stats and highlights", async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const final = card(container, 'g-final');
		await fireEvent.click(final.querySelector('button.toggle') as HTMLElement);
		expect(final.querySelector('button.toggle')?.getAttribute('aria-expanded')).toBe('true');
		expect(within(final).getByText('Team')).toBeTruthy();
		expect(within(final).getByText('Nikola Jokic')).toBeTruthy();
		expect(within(final).getByText('Highlights')).toBeTruthy();
		expect(within(final).getByText('Video platform')).toBeTruthy();
		expect(within(final).getByText('Full game highlights')).toBeTruthy();
	});

	it('links an expanded played game to its detail page', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const final = card(container, 'g-final');
		await fireEvent.click(final.querySelector('button.toggle') as HTMLElement);
		expect(within(final).getByRole('link', { name: 'Game center' }).getAttribute('href')).toBe(
			'/game/g-final'
		);
	});

	it("links the hero's team names to /team/{code} in lowercase", async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const links = [...container.querySelectorAll('.hero h1 a')];
		expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
			['Warriors', '/team/gsw'],
			['Lakers', '/team/lal']
		]);
	});

	it("links the delayed card's team names to /team/{code} in lowercase", async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const delayed = within(card(container, 'g-delayed'));
		expect(delayed.getByRole('link', { name: 'Heat' }).getAttribute('href')).toBe('/team/mia');
		expect(delayed.getByRole('link', { name: 'Bulls' }).getAttribute('href')).toBe('/team/chi');
	});

	it("links an expanded game's line score codes in lowercase", async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const final = card(container, 'g-final');
		await fireEvent.click(final.querySelector('button.toggle') as HTMLElement);
		const hrefs = [...final.querySelectorAll('.line-score a')].map((a) => [
			a.textContent,
			a.getAttribute('href')
		]);
		expect(hrefs).toEqual([
			['DEN', '/team/den'],
			['PHX', '/team/phx']
		]);
	});

	it('renders no link inside a button or another link, before and after expanding a game', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(container.querySelectorAll('button a, a a')).toHaveLength(0);
		await fireEvent.click(card(container, 'g-final').querySelector('button.toggle') as HTMLElement);
		expect(container.querySelectorAll('button a, a a')).toHaveLength(0);
	});

	it('leaves the highlights out when no video platform is configured', async () => {
		config.platform = undefined;
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const final = card(container, 'g-final');
		await fireEvent.click(final.querySelector('button.toggle') as HTMLElement);
		expect(within(final).queryByText('Highlights')).toBeNull();
	});

	it('shows Games current, then Standings, Cup, All-Star, Playoffs under Tournaments, then the date in the nav row', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Tournaments' }));
		const links = container.querySelector('nav .links') as HTMLElement;
		const [games, standings, cup, allStar, playoffs] = [...links.querySelectorAll('a')];
		expect(games.textContent?.trim()).toBe('Games');
		expect(games.getAttribute('aria-current')).toBe('page');
		expect(games.getAttribute('href')).toBe('/#schedule');
		expect(standings.textContent?.trim()).toBe('Standings');
		expect(standings.getAttribute('href')).toBe('/standings');
		expect(standings.getAttribute('aria-current')).toBeNull();
		expect(cup.textContent?.trim()).toBe('Cup');
		expect(cup.getAttribute('href')).toBe('/cup');
		expect(cup.getAttribute('aria-current')).toBeNull();
		expect(allStar.textContent?.trim()).toBe('All-Star');
		expect(allStar.getAttribute('href')).toBe('/all-star');
		expect(allStar.getAttribute('aria-current')).toBeNull();
		expect(playoffs.textContent?.trim()).toBe('Playoffs');
		expect(playoffs.getAttribute('href')).toBe('/playoffs');
		expect(playoffs.getAttribute('aria-current')).toBeNull();
		expect(links.children[3]?.querySelector('time')?.textContent).toBe('Sun, Oct 4, 2026');
	});

	it('toggles spoiler-free mode from the nav row', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		const toggle = screen.getByRole('button', { name: 'Spoiler-free' });
		expect(toggle.getAttribute('aria-pressed')).toBe('false');
		const row = () => card(container, 'g-final').querySelector('button.toggle') as HTMLElement;
		expect(row().textContent).toContain('112');
		await fireEvent.click(toggle);
		expect(toggle.getAttribute('aria-pressed')).toBe('true');
		expect(row().textContent).not.toContain('112');
		expect(within(card(container, 'g-final')).getByText('Tap to reveal')).toBeTruthy();
		localStorage.clear();
	});

	it("opens the hero's game in the schedule from Match details, on today", async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		await fireEvent.click(container.querySelectorAll<HTMLButtonElement>('button.day')[0]);
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe(
			'Thursday, October 1'
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Match details' }));
		await settle();
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe('Sunday, October 4');
		expect(
			card(container, 'g-sched').querySelector('button.toggle')?.getAttribute('aria-expanded')
		).toBe('true');
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'smooth',
			block: 'start'
		});
	});

	it('scrolls without animation when reduced motion is requested', async () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)',
			media: query,
			addEventListener: () => {},
			removeEventListener: () => {}
		}));
		stubFetch(answerWith(recorded()));
		await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Match details' }));
		await settle();
		expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
			behavior: 'auto',
			block: 'start'
		});
	});
});

describe('home page polling', () => {
	it('polls again after 30 s while a game is live', async () => {
		stubFetch(answerWith(recorded()));
		await renderPage();
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(29_000);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1_000);
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('polls every 60 s when no game is live', async () => {
		stubFetch(answerWith(withoutLive()));
		await renderPage();
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('does not poll while the tab is hidden and loads when it is visible again', async () => {
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
		const { container } = await renderPage();
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(6);
		expect(screen.queryByText("Data isn't available right now. Check back later.")).toBeNull();
	});
});

describe('home page without data', () => {
	it('shows the data unavailable row when the feed cannot be loaded', async () => {
		stubFetch(answerFailing);
		const { container } = await renderPage();
		const row = screen.getByText("Data isn't available right now. Check back later.");
		expect(row.closest('.blueprint-frame')).not.toBeNull();
		expect(row.closest('section')?.id).toBe('schedule');
		expect(container.querySelector('ul.games')).toBeNull();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('shows the data unavailable row in Spanish with a Spanish preference', async () => {
		preferLanguages(['es-ES']);
		stubFetch(answerFailing);
		await renderPage();
		expect(
			screen.getByText(
				'Los datos no están disponibles en este momento. Vuelve a consultar más tarde.'
			)
		).toBeTruthy();
	});

	it('shows the data unavailable row when the feed answers an error status', async () => {
		stubFetch(() => Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) }));
		await renderPage();
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
	});

	it('shows the data unavailable row when the feed does not have seven days', async () => {
		const feed = recorded();
		feed.days.pop();
		stubFetch(answerWith(feed));
		await renderPage();
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
	});

	it('shows the data unavailable row when no feed URL is configured', async () => {
		config.url = undefined;
		stubFetch(answerFailing);
		await renderPage();
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('shows the hero and schedule skeletons while the first load is pending', async () => {
		stubFetch(() => new Promise(() => {}));
		const { container } = await renderPage();
		expect(container.querySelector('.hero-skeleton')).not.toBeNull();
		expect(container.querySelector('section#schedule.schedule-skeleton')).not.toBeNull();
		expect(container.querySelector('ul.games')).toBeNull();
		expect(screen.queryByText("Data isn't available right now. Check back later.")).toBeNull();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('replaces the skeletons with the content once the first feed loads', async () => {
		let resolveFetch!: (value: unknown) => void;
		stubFetch(() => new Promise((r) => (resolveFetch = r)));
		const { container } = await renderPage();
		expect(container.querySelector('.hero-skeleton')).not.toBeNull();
		expect(container.querySelector('.schedule-skeleton')).not.toBeNull();
		resolveFetch({ ok: true, status: 200, json: () => Promise.resolve(recorded()) });
		await settle();
		expect(container.querySelector('.hero-skeleton')).toBeNull();
		expect(container.querySelector('.schedule-skeleton')).toBeNull();
		expect(
			screen.getByRole('heading', { level: 1, name: /^Warriors\s*at\s+Lakers$/ })
		).toBeTruthy();
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(6);
	});

	it('replaces the skeletons with the unavailable row when the first load fails', async () => {
		let rejectFetch!: (reason: unknown) => void;
		stubFetch(() => new Promise((_, r) => (rejectFetch = r)));
		const { container } = await renderPage();
		expect(container.querySelector('.hero-skeleton')).not.toBeNull();
		rejectFetch(new TypeError('Failed to fetch'));
		await settle();
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(container.querySelector('.hero-skeleton')).toBeNull();
		expect(container.querySelector('.schedule-skeleton')).toBeNull();
	});

	it('shows no hero game when every game of today is postponed or canceled', async () => {
		const feed = recorded();
		feed.days[3].games = feed.days[3].games.filter(
			(g) => g.id === 'g-postponed' || g.id === 'g-canceled'
		);
		stubFetch(answerWith(feed));
		const { container } = await renderPage();
		expect(screen.queryByRole('heading', { level: 1 })).toBeNull();
		expect(screen.queryByRole('button', { name: 'Match details' })).toBeNull();
		expect(container.querySelector('.hero-skeleton')).toBeNull();
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(2);
	});
});

describe('home page language', () => {
	beforeEach(() => {
		config.url = undefined;
	});

	it('shows the not-affiliated line in English', async () => {
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners.'
			)
		).toBeTruthy();
	});

	it('shows the not-affiliated line in Spanish for es-ES', async () => {
		preferLanguages(['es-ES']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Sitio no oficial. Sin afiliación con la NBA ni sus equipos. Nombres y logos son propiedad de sus dueños.'
			)
		).toBeTruthy();
	});

	it('shows Spanish for a regional tag such as es-419', async () => {
		preferLanguages(['es-419']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Sitio no oficial. Sin afiliación con la NBA ni sus equipos. Nombres y logos son propiedad de sus dueños.'
			)
		).toBeTruthy();
	});

	it('shows English for an unsupported language', async () => {
		preferLanguages(['fr-FR']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners.'
			)
		).toBeTruthy();
	});

	it('shows English when English is preferred over Spanish', async () => {
		preferLanguages(['en-US', 'es']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners.'
			)
		).toBeTruthy();
	});
});

function navigate(search: string) {
	for (const callback of navigation.callbacks) {
		callback({ to: { url: new URL(`https://app.example.com/${search}`) } });
	}
}

const selectedDay = (container: HTMLElement) =>
	[...container.querySelectorAll<HTMLElement>('button.day')].findIndex(
		(day) => day.getAttribute('aria-current') === 'true'
	);

describe('home page with a requested day', () => {
	it('selects the DayStrip day of ?day= after a navigation', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		expect(selectedDay(container)).toBe(3);
		navigate('?day=2026-10-06');
		await settle();
		expect(selectedDay(container)).toBe(5);
	});

	it('goes to /day/ for a past day outside the feed, keeping today selected', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		navigate('?day=1999-02-05');
		await settle();
		expect(selectedDay(container)).toBe(3);
		expect(navigation.goto).toHaveBeenCalledTimes(1);
		expect(navigation.goto).toHaveBeenCalledWith('/day/1999-02-05', { replaceState: true });
	});

	it('keeps today selected, with no redirect, for a later day, a malformed day or a day of the feed', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		navigate('?day=2026-10-20');
		await settle();
		expect(selectedDay(container)).toBe(3);
		navigate('?day=2026-10-06');
		await settle();
		navigate('?day=not-a-day');
		await settle();
		expect(selectedDay(container)).toBe(3);
		navigate('');
		await settle();
		expect(selectedDay(container)).toBe(3);
		expect(navigation.goto).not.toHaveBeenCalled();
	});

	it('does not move the selection on a later poll', async () => {
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		navigate('?day=2026-10-06');
		await settle();
		await vi.advanceTimersByTimeAsync(61_000);
		await settle();
		expect(fetchMock.mock.calls.length).toBeGreaterThan(1);
		expect(selectedDay(container)).toBe(5);
	});
});

describe('home page calendar sheet', () => {
	it('links a day of the feed to /?day= and another day to /day/, and no day after today', async () => {
		config.calendarUrl = CALENDAR_TEMPLATE;
		stubFetch(answerWith(recorded()));
		await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Open calendar' }));
		await settle();
		const dialog = screen.getByRole('dialog', { name: 'Calendar' });
		expect(within(dialog).getByRole('link', { name: 'October 4, 2026' }).getAttribute('href')).toBe(
			'/?day=2026-10-04'
		);
		expect(within(dialog).queryByRole('link', { name: 'October 20, 2026' })).toBeNull();
		await fireEvent.click(within(dialog).getByRole('button', { name: 'Previous month' }));
		expect(
			within(dialog).getByRole('link', { name: 'September 30, 2026' }).getAttribute('href')
		).toBe('/day/2026-09-30');
		expect(fetchMock).toHaveBeenCalledWith(CALENDAR_URL, expect.anything());
	});

	it("before the games feed loads, links no day after the client's Eastern today", async () => {
		config.calendarUrl = CALENDAR_TEMPLATE;
		stubFetch(() => new Promise(() => {}));
		await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Open calendar' }));
		await settle();
		const dialog = screen.getByRole('dialog', { name: 'Calendar' });
		expect(within(dialog).getByRole('link', { name: 'October 4, 2026' }).getAttribute('href')).toBe(
			'/?day=2026-10-04'
		);
		expect(within(dialog).queryByRole('link', { name: 'October 20, 2026' })).toBeNull();
		expect(
			(within(dialog).getByRole('button', { name: 'Next month' }) as HTMLButtonElement).disabled
		).toBe(true);
	});
});

describe('home page team logos', () => {
	it('draws the feed logo of a side, the code for a null logo and the initials of a guest', async () => {
		const feed = recorded();
		const games = feed.days.flatMap((day) => day.games);
		const final = games.find((game) => game.id === 'g-final')!;
		final.away.logo = {
			light: 'https://example.com/a-light.svg',
			dark: 'https://example.com/a-dark.svg'
		};
		final.home = { ...final.home, code: null, name: 'Mariners', city: 'Harbor City', guest: true };
		stubFetch(answerWith(feed));
		const { container } = await renderPage();
		const boxes = [...card(container, 'g-final').querySelectorAll('.row .team-monogram.large')];
		expect(boxes[0]!.querySelector('img')?.getAttribute('src')).toBe(
			'https://example.com/a-dark.svg'
		);
		expect(boxes[1]!.querySelector('img')).toBeNull();
		expect(boxes[1]!.textContent).toBe('HM');
		const other = container.querySelector(
			'ul.games > li:not(:has(#game-g-final)) .team-monogram.large'
		);
		expect(other?.querySelector('img')).toBeNull();
	});
});

describe('home page on a day with no games', () => {
	const mobile = () =>
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: false,
			media: query,
			addEventListener: () => {},
			removeEventListener: () => {}
		}));

	it('never requests the home feed on a day with games', async () => {
		config.homeUrl = HOME_URL;
		homeAnswers = [homeAnswerWith(homeFeed())];
		stubFetch(answerWith(recorded()));
		const { container } = await renderPage();
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
		expect(homeCalls()).toBe(0);
		expect(screen.queryByText('No games today')).toBeNull();
		expect(container.querySelector('.hero .headline')).not.toBeNull();
	});

	it('keeps the hero with no game when every game of today is postponed or canceled', async () => {
		config.homeUrl = HOME_URL;
		homeAnswers = [homeAnswerWith(homeFeed())];
		const feed = recorded();
		feed.days[3].games = feed.days[3].games.filter(
			(g) => g.id === 'g-postponed' || g.id === 'g-canceled'
		);
		stubFetch(answerWith(feed));
		await renderPage();
		expect(homeCalls()).toBe(0);
		expect(screen.queryByText('No games today')).toBeNull();
	});

	it('requests the home feed once and shows the chip, the title and the Coming up card', async () => {
		config.homeUrl = HOME_URL;
		homeAnswers = [homeAnswerWith(homeFeed())];
		stubFetch(answerWith(withoutGamesToday()));
		const { container } = await renderPage();
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS * 2 + SLOW_POLL_MS);
		await settle();
		expect(homeCalls()).toBe(1);
		const hero = container.querySelector('.hero') as HTMLElement;
		expect(within(hero).getByRole('heading', { level: 1 }).textContent).toBe('No games today');
		expect(within(hero).getByText('Off day')).toBeTruthy();
		expect(within(hero).getByText('Sunday, October 4')).toBeTruthy();
		expect(
			within(hero).getByText('Next tip-off: Tue, Oct 6 · 7:00 PM ET', { exact: false })
		).toBeTruthy();
		expect(within(hero).getByText('Courtside TV', { exact: false })).toBeTruthy();
		expect(hero.querySelector('aside.coming-up')).not.toBeNull();
		expect(container.querySelectorAll('.coming-up')).toHaveLength(1);
	});

	it('puts Coming up in a section after the hero on a narrow screen', async () => {
		mobile();
		config.homeUrl = HOME_URL;
		homeAnswers = [homeAnswerWith(homeFeed())];
		stubFetch(answerWith(withoutGamesToday()));
		const { container } = await renderPage();
		const hero = container.querySelector('.hero') as HTMLElement;
		const section = container.querySelector('section.coming-up.mobile') as HTMLElement;
		expect(section).not.toBeNull();
		expect(hero.contains(section)).toBe(false);
		expect(hero.nextElementSibling).toBe(section);
		const last = section.nextElementSibling as HTMLElement;
		expect(last.classList.contains('last-games')).toBe(true);
		expect(last.nextElementSibling?.id).toBe('schedule');
		expect(hero.querySelector('.coming-up')).toBeNull();
	});

	it('shows the date and the title only when the home feed fails', async () => {
		config.homeUrl = HOME_URL;
		homeAnswers = [
			answerFailing,
			() => Promise.resolve({ ok: false, status: 503, json: () => Promise.resolve({}) })
		];
		stubFetch(answerWith(withoutGamesToday()));
		const { container } = await renderPage();
		await settle();
		const hero = container.querySelector('.hero') as HTMLElement;
		expect(within(hero).getByRole('heading', { level: 1 }).textContent).toBe('No games today');
		expect(within(hero).getByText('Sunday, October 4')).toBeTruthy();
		expect(hero.querySelector('.status-tag')).toBeNull();
		expect(hero.querySelector('.paragraph')).toBeNull();
		expect(container.querySelector('.coming-up')).toBeNull();
		expect(container.querySelector('#schedule')).not.toBeNull();
		expect(homeCalls()).toBe(1);
	});

	it('shows the date and the title only, with no request, when the home feed is not configured', async () => {
		stubFetch(answerWith(withoutGamesToday()));
		const { container } = await renderPage();
		expect(homeCalls()).toBe(0);
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('No games today');
		expect(container.querySelector('.coming-up')).toBeNull();
	});

	it('shows the title in Spanish with a Spanish preference', async () => {
		preferLanguages(['es']);
		stubFetch(answerWith(withoutGamesToday()));
		await renderPage();
		expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Hoy no hay partidos');
	});

	describe('with the home feed in', () => {
		const setup = async (edit: (feed: HomeFeed) => void = () => {}) => {
			config.homeUrl = HOME_URL;
			const feed = homeFeed();
			edit(feed);
			homeAnswers = [homeAnswerWith(feed)];
			stubFetch(answerWith(withoutGamesToday()));
			const result = await renderPage();
			await settle();
			return result;
		};
		const links = (container: HTMLElement) =>
			[...container.querySelectorAll<HTMLAnchorElement>('a')].map((a) => a.getAttribute('href'));

		it('shows Last games with its title and two links to the game pages', async () => {
			const { container } = await setup();
			const section = container.querySelector('section.last-games') as HTMLElement;
			expect(within(section).getByRole('heading', { level: 2 }).textContent).toBe('Last night');
			const hrefs = [...section.querySelectorAll('a')].map((a) => a.getAttribute('href'));
			expect(hrefs).toEqual(['/game/g-last-1', '/game/g-last-2']);
		});

		it('orders the hero, Last games and the schedule on a wide screen', async () => {
			const { container } = await setup();
			const hero = container.querySelector('.hero') as HTMLElement;
			const last = container.querySelector('section.last-games') as HTMLElement;
			expect(hero.nextElementSibling).toBe(last);
			expect(last.nextElementSibling?.id).toBe('schedule');
		});

		it('hides Last games when the feed carries none', async () => {
			const { container } = await setup((feed) => {
				feed.lastGames = null;
			});
			expect(container.querySelector('.last-games')).toBeNull();
			expect(container.querySelector('#schedule')).not.toBeNull();
		});

		it('hides Last games when the home feed fails or is not configured', async () => {
			config.homeUrl = HOME_URL;
			homeAnswers = [answerFailing];
			stubFetch(answerWith(withoutGamesToday()));
			const failed = await renderPage();
			await settle();
			expect(failed.container.querySelector('.last-games')).toBeNull();
			failed.unmount();
			config.homeUrl = undefined;
			stubFetch(answerWith(withoutGamesToday()));
			const absent = await renderPage();
			expect(absent.container.querySelector('.last-games')).toBeNull();
		});

		it('hides Last games on a day with games', async () => {
			config.homeUrl = HOME_URL;
			homeAnswers = [homeAnswerWith(homeFeed())];
			stubFetch(answerWith(recorded()));
			const { container } = await renderPage();
			expect(container.querySelector('.last-games')).toBeNull();
		});

		it('hides the scores of Last games with spoiler-free on', async () => {
			const { container } = await setup();
			const section = container.querySelector('section.last-games') as HTMLElement;
			expect(within(section).getByText('104')).toBeTruthy();
			await fireEvent.click(screen.getByRole('button', { name: 'Spoiler-free' }));
			await settle();
			expect(within(section).queryByText('104')).toBeNull();
			expect(within(section).getAllByText('Tap to reveal')).toHaveLength(2);
		});

		it('shows the empty-day box on today with the next games and a Go to link', async () => {
			const { container } = await setup();
			const schedule = container.querySelector('#schedule') as HTMLElement;
			expect(within(schedule).getByText('No games on this day')).toBeTruthy();
			expect(within(schedule).getByText('Next games: Tue, Oct 6 · 5 games')).toBeTruthy();
			expect(within(schedule).queryByText('No games scheduled for this day.')).toBeNull();
			const goTo = within(schedule).getByRole('link', { name: 'Go to Tue, Oct 6 →' });
			expect(goTo.getAttribute('href')).toBe('/?day=2026-10-06');
		});

		it('selects the next game day after the navigation the Go to link makes', async () => {
			const { container } = await setup();
			navigate('?day=2026-10-06');
			await settle();
			const schedule = container.querySelector('#schedule') as HTMLElement;
			expect(within(schedule).getByRole('heading', { level: 2 }).textContent).toBe(
				'Tuesday, October 6'
			);
		});

		it('shows the text and no button outside the games feed window', async () => {
			const { container } = await setup((feed) => {
				if (feed.nextGame) feed.nextGame.inGamesWindow = false;
			});
			const schedule = container.querySelector('#schedule') as HTMLElement;
			expect(within(schedule).getByText('Next games: Tue, Oct 6 · 5 games')).toBeTruthy();
			expect(within(schedule).queryByRole('link', { name: /Go to/ })).toBeNull();
			expect(links(container).some((href) => href?.startsWith('/day/2026-10-0'))).toBe(false);
		});

		it('shows the two-weeks message and no button without a next game', async () => {
			const { container } = await setup((feed) => {
				feed.nextGame = null;
			});
			const schedule = container.querySelector('#schedule') as HTMLElement;
			expect(within(schedule).getByText('No games scheduled in the next two weeks.')).toBeTruthy();
			expect(within(schedule).queryByRole('link', { name: /Go to/ })).toBeNull();
		});

		it('keeps the old row when the home feed failed', async () => {
			config.homeUrl = HOME_URL;
			homeAnswers = [answerFailing];
			stubFetch(answerWith(withoutGamesToday()));
			const { container } = await renderPage();
			await settle();
			const schedule = container.querySelector('#schedule') as HTMLElement;
			expect(within(schedule).getByText('No games scheduled for this day.')).toBeTruthy();
			expect(within(schedule).queryByText('No games on this day')).toBeNull();
		});

		it('hides the schedule in the offseason and keeps Last games', async () => {
			const { container } = await setup((feed) => {
				feed.scenario = 'offseason';
			});
			expect(container.querySelector('.schedule')).toBeNull();
			expect(container.querySelector('.last-games')).not.toBeNull();
		});

		it('gives the schedule anchor to Last games in the offseason', async () => {
			const { container } = await setup((feed) => {
				feed.scenario = 'offseason';
			});
			const anchors = container.querySelectorAll('#schedule');
			expect(anchors).toHaveLength(1);
			expect(anchors[0].querySelector('.last-games')).not.toBeNull();
		});

		it('keeps the schedule anchor on the schedule outside the offseason', async () => {
			const { container } = await setup((feed) => {
				feed.scenario = 'offDay';
			});
			const anchors = container.querySelectorAll('#schedule');
			expect(anchors).toHaveLength(1);
			expect(anchors[0].classList.contains('schedule')).toBe(true);
			expect(anchors[0].querySelector('.last-games')).toBeNull();
		});

		it.each(['offDay', 'allStarBreak', 'finalsPreview'] as const)(
			'keeps the schedule in the %s scenario',
			async (scenario) => {
				const { container } = await setup((feed) => {
					feed.scenario = scenario;
				});
				expect(container.querySelector('#schedule')).not.toBeNull();
			}
		);
	});

	describe('with Standings and Leaders', () => {
		const standingsFeed = () =>
			JSON.parse(
				readFileSync(join(__dirname, '..', 'lib', 'feed', 'fixtures', 'standings.json'), 'utf8')
			);
		const previewFeed = (): HomeFeed =>
			JSON.parse(
				readFileSync(
					join(__dirname, '..', 'lib', 'feed', 'fixtures', 'home-finals-preview.json'),
					'utf8'
				)
			) as HomeFeed;
		const standingsOk: Answer = () =>
			Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(standingsFeed()) });
		const setup = async (
			options: {
				home?: Answer | HomeFeed | null;
				standings?: Answer | null;
				edit?: (feed: HomeFeed) => void;
			} = {}
		) => {
			const { home = homeFeed(), standings = standingsOk, edit = () => {} } = options;
			config.homeUrl = home === null ? undefined : HOME_URL;
			config.standingsUrl = standings === null ? undefined : STANDINGS_URL;
			if (home !== null) {
				if (typeof home === 'function') homeAnswers = [home];
				else {
					edit(home);
					homeAnswers = [homeAnswerWith(home)];
				}
			}
			standingsAnswers = standings === null ? [] : [standings];
			stubFetch(answerWith(withoutGamesToday()));
			const result = await renderPage();
			await settle();
			return result;
		};

		it('shows Standings and Leaders after the schedule and before the footer', async () => {
			const { container } = await setup();
			const wrapper = container.querySelector('.standings-leaders') as HTMLElement;
			expect(wrapper).not.toBeNull();
			expect(container.querySelector('#schedule')?.nextElementSibling).toBe(wrapper);
			expect(wrapper.nextElementSibling?.tagName).toBe('FOOTER');
			const standings = wrapper.querySelector('.home-standings') as HTMLElement;
			expect(within(standings).getByRole('heading', { level: 2 }).textContent).toBe('Standings');
			expect(standings.querySelectorAll('tbody tr')).toHaveLength(6);
			const leaders = wrapper.querySelector('.home-leaders') as HTMLElement;
			expect(within(leaders).getByRole('heading', { level: 2 }).textContent).toBe('This season');
			expect(leaders.querySelectorAll('li.leader')).toHaveLength(4);
		});

		it('requests the standings feed once across several games polls', async () => {
			await setup();
			await vi.advanceTimersByTimeAsync(IDLE_POLL_MS * 2 + SLOW_POLL_MS);
			await settle();
			expect(standingsCalls()).toBe(1);
		});

		it('requests neither feed and renders no section on a day with games', async () => {
			config.homeUrl = HOME_URL;
			config.standingsUrl = STANDINGS_URL;
			homeAnswers = [homeAnswerWith(homeFeed())];
			standingsAnswers = [standingsOk];
			stubFetch(answerWith(recorded()));
			const { container } = await renderPage();
			await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
			expect(homeCalls()).toBe(0);
			expect(standingsCalls()).toBe(0);
			expect(container.querySelector('.standings-leaders')).toBeNull();
		});

		it('puts the sections in two columns on a wide screen', async () => {
			const { container } = await setup();
			const wrapper = container.querySelector('.standings-leaders') as HTMLElement;
			expect(wrapper.classList.contains('columns')).toBe(true);
			const source = readFileSync(
				join(__dirname, '..', '..', 'src', 'routes', '+page.svelte'),
				'utf8'
			);
			expect(source).toMatch(/\.columns\s*\{\s*grid-template-columns:\s*repeat\(auto-fit,/);
		});

		it('stacks Standings then Leaders on a narrow screen', async () => {
			mobile();
			const { container } = await setup();
			const wrapper = container.querySelector('.standings-leaders') as HTMLElement;
			expect(wrapper.classList.contains('columns')).toBe(false);
			expect([...wrapper.children].map((c) => c.className.split(' ')[0])).toEqual([
				'home-standings',
				'home-leaders'
			]);
		});

		it('hides Standings when the standings feed fails and keeps Leaders and the rest', async () => {
			const { container } = await setup({ standings: answerFailing });
			expect(container.querySelector('.home-standings')).toBeNull();
			expect(container.querySelector('.home-leaders')).not.toBeNull();
			expect(container.querySelector('.hero')).not.toBeNull();
			expect(container.querySelector('#schedule')).not.toBeNull();
		});

		it('hides Standings, with no request, when the standings feed is not configured', async () => {
			const { container } = await setup({ standings: null });
			expect(container.querySelector('.home-standings')).toBeNull();
			expect(container.querySelector('.home-leaders')).not.toBeNull();
			expect(standingsCalls()).toBe(0);
		});

		it('hides Leaders when the home feed fails and keeps the compact standings', async () => {
			const { container } = await setup({ home: answerFailing });
			expect(container.querySelector('.home-leaders')).toBeNull();
			expect(container.querySelector('.home-standings')).not.toBeNull();
		});

		it('renders no wrapper when both feeds fail', async () => {
			const { container } = await setup({ home: answerFailing, standings: answerFailing });
			expect(container.querySelector('.standings-leaders')).toBeNull();
			expect(container.querySelector('.hero')).not.toBeNull();
			expect(container.querySelector('#schedule')).not.toBeNull();
		});

		it('hides Leaders when the feed has none and gives the wrapper to Standings', async () => {
			const { container } = await setup({
				edit: (feed) => {
					feed.leaders = null;
				}
			});
			expect(container.querySelector('.home-leaders')).toBeNull();
			expect(container.querySelector('.standings-leaders > .home-standings')).not.toBeNull();
		});

		it('shows one row per leader the feed sends', async () => {
			const { container } = await setup({
				edit: (feed) => {
					const [points, , , blocks] = feed.leaders!.categories as [
						HomeLeader,
						HomeLeader,
						HomeLeader,
						HomeLeader
					];
					feed.leaders!.categories = [points, blocks];
				}
			});
			expect(container.querySelectorAll('.home-leaders li.leader')).toHaveLength(2);
		});

		it('shows the finalists in the Finals preview', async () => {
			const { container } = await setup({ home: previewFeed() });
			const standings = container.querySelector('.home-standings') as HTMLElement;
			expect(within(standings).getByRole('heading', { level: 2 }).textContent).toBe(
				'Road to the Finals'
			);
			expect(within(standings).getByRole('button', { name: /Easterners/ })).toBeTruthy();
			expect(within(standings).queryByRole('button', { name: 'East' })).toBeNull();
		});

		it('hides Standings in the Finals preview without a finals path', async () => {
			const { container } = await setup({
				home: previewFeed(),
				edit: (feed) => {
					feed.finalsPath = null;
				}
			});
			expect(container.querySelector('.home-standings')).toBeNull();
			expect(container.querySelector('.home-leaders')).not.toBeNull();
		});

		it('shows the section titles in Spanish', async () => {
			preferLanguages(['es']);
			const { container } = await setup();
			const headings = [...container.querySelectorAll('.standings-leaders h2')].map(
				(h) => h.textContent
			);
			expect(headings).toEqual(['Clasificación', 'Esta temporada']);
		});
	});
});
