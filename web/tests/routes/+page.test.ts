// web/tests/routes/+page.test.ts
//
// Tests for the home page.
//
// Tested:
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

import type { GamesFeed } from '../../src/lib/contract/games';
import { preferLanguages } from '../prefer-languages';

import Page from '../../src/routes/+page.svelte';

const config = vi.hoisted(() => ({
	url: undefined as string | undefined,
	platform: undefined as string | undefined
}));
vi.mock('../../src/lib/feed/config', () => ({
	get gamesFeedUrl() {
		return config.url;
	},
	get videoPlatformName() {
		return config.platform;
	}
}));

const FEED_URL = 'https://feeds.example.com/games.json';
const recorded = (): GamesFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'lib', 'feed', 'fixtures', 'games.json'), 'utf8')
	) as GamesFeed;

type Answer = () => Promise<unknown>;
let answers: Answer[];
let fetchMock: ReturnType<typeof vi.fn>;
const answerWith =
	(feed: GamesFeed): Answer =>
	() =>
		Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(feed) });
const answerFailing: Answer = () => Promise.reject(new TypeError('Failed to fetch'));

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
		expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/Warriors\s*at\s+Lakers/);
		expect(screen.getByRole('heading', { level: 2 }).textContent?.trim()).toBe('Sunday, October 4');
		expect(container.querySelectorAll('ul.games > li')).toHaveLength(6);
		expect(screen.getByText('Updated 5 min ago')).toBeTruthy();
		expect(screen.getByText('Delayed', { selector: '.status-line' })).toBeTruthy();
		expect(screen.getByText('Postponed', { selector: '.status-line' })).toBeTruthy();
		expect(screen.getByText('Canceled', { selector: '.status-line' })).toBeTruthy();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Personal project. Not affiliated with the NBA.'
			)
		).toBeTruthy();
		expect(fetchMock).toHaveBeenCalledTimes(1);
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
		expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/Warriors\s*at\s+Lakers/);
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
				'Personal project. Not affiliated with the NBA.'
			)
		).toBeTruthy();
	});

	it('shows the not-affiliated line in Spanish for es-ES', async () => {
		preferLanguages(['es-ES']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Proyecto personal. Sin afiliación con la NBA.'
			)
		).toBeTruthy();
	});

	it('shows Spanish for a regional tag such as es-419', async () => {
		preferLanguages(['es-419']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Proyecto personal. Sin afiliación con la NBA.'
			)
		).toBeTruthy();
	});

	it('shows English for an unsupported language', async () => {
		preferLanguages(['fr-FR']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Personal project. Not affiliated with the NBA.'
			)
		).toBeTruthy();
	});

	it('shows English when English is preferred over Spanish', async () => {
		preferLanguages(['en-US', 'es']);
		await renderPage();
		expect(
			within(screen.getByRole('contentinfo')).getByText(
				'Personal project. Not affiliated with the NBA.'
			)
		).toBeTruthy();
	});
});
