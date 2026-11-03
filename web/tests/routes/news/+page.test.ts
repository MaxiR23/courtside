// web/tests/routes/news/+page.test.ts
//
// Tests for the News route (/news).
//
// Tested:
// - The route turns off server rendering
// - It loads page 1 of the league feed in the active language (English and Spanish)
// - Load more fetches page 2 and drops a repeated note
// - Choosing a team loads that team's page 1 and never shows the previous list
// - The type filter hides the other kind; the empty filter says so
// - A 404 or no URL gives the unavailable row; no search feed means no team select
// - The document title in both languages
//
// What is covered:
// - The page wired end to end: config, fetch, paging, props layer, filters, footer
// - A recorded feed (tests/lib/feed/fixtures/news.json); the fetch mock fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/news/+page.test.ts"
//
// SEE: web/src/routes/news/+page.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/news/+page.svelte';

const config = vi.hoisted(() => ({
	league: undefined as string | undefined,
	team: undefined as string | undefined,
	search: undefined as string | undefined
}));
vi.mock('../../../src/lib/feed/config', () => ({
	get newsFeedUrl() {
		return config.league;
	},
	get newsTeamFeedUrl() {
		return config.team;
	},
	get searchFeedUrl() {
		return config.search;
	}
}));

const fixtures = join(__dirname, '..', '..', 'lib', 'feed', 'fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const league = (lang: string, page: number) =>
	`https://feeds.example.com/news/${lang}/pages/${page}.json`;
const team = (lang: string, code: string, page: number) =>
	`https://feeds.example.com/news/${lang}/teams/${code}/pages/${page}.json`;
const SEARCH = 'https://feeds.example.com/search.json';

type Answer = () => Promise<unknown>;
const json =
	(body: unknown, status = 200): Answer =>
	() =>
		Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
let routes: Record<string, Answer>;
let calls: string[];

function stubRoutes(next: Record<string, Answer>) {
	routes = next;
	calls = [];
	vi.stubGlobal(
		'fetch',
		vi.fn((url: string) => {
			const answer = routes[url];
			if (!answer) throw new Error(`Unexpected URL ${url}`);
			calls.push(url);
			return answer();
		})
	);
}

async function settle() {
	await vi.advanceTimersByTimeAsync(0);
	await tick();
	await vi.advanceTimersByTimeAsync(0);
	await tick();
}

async function renderPage() {
	const result = render(Page);
	await settle();
	return result;
}

const second = () => {
	const feed = read('news.json');
	feed.page = 2;
	feed.hasMore = false;
	feed.notes = feed.notes.slice(0, 2).map((note: { id: string }, i: number) => ({
		...note,
		id: i === 0 ? 'note-12' : 'note-13'
	}));
	return feed;
};

beforeEach(() => {
	document.title = '';
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-11-03T12:00:00Z'));
	config.league = 'https://feeds.example.com/news/{lang}/pages/{page}.json';
	config.team = 'https://feeds.example.com/news/{lang}/teams/{code}/pages/{page}.json';
	config.search = undefined;
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('news route', () => {
	it('turns off server rendering', async () => {
		const options = await import('../../../src/routes/news/+page');
		expect(options.ssr).toBe(false);
	});
});

describe('news page', () => {
	it('loads page 1 of the league in English and draws 12 cards, the filter and the footer', async () => {
		stubRoutes({ [league('en', 1)]: json(read('news.json')) });
		const { container } = await renderPage();
		expect(calls).toEqual([league('en', 1)]);
		expect(screen.getByRole('heading', { level: 1, name: 'News' })).toBeTruthy();
		expect(container.querySelectorAll('.grid li')).toHaveLength(12);
		expect(screen.getByRole('group', { name: 'Type' })).toBeTruthy();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
		expect(document.title).toBe('News · Courtside');
	});

	it('loads the Spanish page in Spanish', async () => {
		preferLanguages(['es']);
		stubRoutes({ [league('es', 1)]: json(read('news.json')) });
		await renderPage();
		expect(calls).toEqual([league('es', 1)]);
		expect(document.title).toBe('Noticias · Courtside');
	});

	it('loads page 2 on Load more, appends and drops a repeated note, then hides the button', async () => {
		stubRoutes({ [league('en', 1)]: json(read('news.json')), [league('en', 2)]: json(second()) });
		const { container } = await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
		await settle();
		expect(calls).toEqual([league('en', 1), league('en', 2)]);
		expect(container.querySelectorAll('.grid li')).toHaveLength(13);
		expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
	});

	it('hides the other kind with the type filter and says so when none is left', async () => {
		const feed = read('news.json');
		feed.notes = feed.notes.map((note: object) => ({ ...note, kind: 'news' }));
		stubRoutes({ [league('en', 1)]: json(feed) });
		const { container } = await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Recaps' }));
		expect(screen.getByRole('button', { name: 'Recaps' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		expect(container.querySelectorAll('.grid li')).toHaveLength(0);
		expect(screen.getByText('No notes.')).toBeTruthy();
		await fireEvent.click(screen.getByRole('button', { name: 'News' }));
		expect(container.querySelectorAll('.grid li')).toHaveLength(12);
	});

	it('keeps only the recaps with the Recaps filter', async () => {
		stubRoutes({ [league('en', 1)]: json(read('news.json')) });
		const { container } = await renderPage();
		await fireEvent.click(screen.getByRole('button', { name: 'Recaps' }));
		const shown = container.querySelectorAll('.grid li').length;
		expect(shown).toBeGreaterThan(0);
		expect(shown).toBeLessThan(12);
	});

	it('draws the team select from the search feed and loads the chosen team', async () => {
		config.search = SEARCH;
		stubRoutes({
			[SEARCH]: json(read('search.json')),
			[league('en', 1)]: json(read('news.json')),
			[team('en', 'atl', 1)]: json({ page: 1, hasMore: false, notes: [read('news.json').notes[0]] })
		});
		const { container } = await renderPage();
		const select = screen.getByRole('combobox', { name: 'Team' }) as HTMLSelectElement;
		expect(select.options[0]?.textContent).toBe('All teams');
		expect(select.options).toHaveLength(31);
		select.value = 'atl';
		select.dispatchEvent(new Event('change', { bubbles: true }));
		await settle();
		expect(calls).toContain(team('en', 'atl', 1));
		expect(container.querySelectorAll('.grid li')).toHaveLength(1);
	});

	it('draws no team select without a search feed', async () => {
		stubRoutes({ [league('en', 1)]: json(read('news.json')) });
		await renderPage();
		expect(screen.queryByRole('combobox', { name: 'Team' })).toBeNull();
	});

	it('shows the unavailable row on a 404 and with no URL', async () => {
		stubRoutes({ [league('en', 1)]: json({}, 404) });
		await renderPage();
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
	});

	it('shows the unavailable row with no URL and requests nothing', async () => {
		config.league = undefined;
		stubRoutes({});
		await renderPage();
		expect(calls).toEqual([]);
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
	});
});
