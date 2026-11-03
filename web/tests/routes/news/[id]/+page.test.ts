// web/tests/routes/news/[id]/+page.test.ts
//
// Tests for the note route (/news/{id}).
//
// Tested:
// - The route turns off prerender and server rendering
// - It loads the article path of the id in the active language and renders the note
// - The game button shows the score alone until the game detail feed is in, then the game's US
//   Eastern day from its tip-off (not the note's published day), and the score alone if that feed fails
// - A 404 and a note of null give the not found row; a 503 gives the unavailable row
// - The document title is the headline
//
// What is covered:
// - The page wired end to end: config, fetches, props layer, footer
// - Recorded feeds (tests/lib/feed/fixtures/news-article.json, game-detail.json); the fetch mock
//   fails for any other URL
// - Fake timers and a fixed system time, no real clock, no real network
//
// Run with: cd web && pnpm exec vitest run "tests/routes/news/[id]/+page.test.ts"
//
// SEE: web/src/routes/news/[id]/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { tick } from 'svelte';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../../prefer-languages';

import Page from '../../../../src/routes/news/[id]/+page.svelte';

const config = vi.hoisted(() => ({
	article: undefined as string | undefined,
	detail: undefined as string | undefined
}));
vi.mock('../../../../src/lib/feed/config', () => ({
	get newsArticleFeedUrl() {
		return config.article;
	},
	get gameDetailFeedUrl() {
		return config.detail;
	}
}));

const fixtures = join(__dirname, '..', '..', '..', 'lib', 'feed', 'fixtures');
const read = (name: string) => JSON.parse(readFileSync(join(fixtures, name), 'utf8'));
const articleUrl = (lang: string) => `https://feeds.example.com/news/${lang}/articles/note-01.json`;
const GAME_URL = 'https://feeds.example.com/games/0022600001.json';

type Answer = () => Promise<unknown>;
const json =
	(body: unknown, status = 200): Answer =>
	() =>
		Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });
const never: Answer = () => new Promise(() => {});
let calls: string[];

function stubRoutes(routes: Record<string, Answer>) {
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

async function renderPage() {
	const result = render(Page, { props: { params: { id: 'note-01' }, data: {} } });
	for (let i = 0; i < 3; i++) {
		await vi.advanceTimersByTimeAsync(0);
		await tick();
	}
	return result;
}

// The game starts at 02:30 UTC on Oct 29: still Oct 28 in New York. The note was published a day
// later, so the two days differ.
const detail = () => ({
	...read('game-detail.json'),
	id: '0022600001',
	startTime: '2026-10-29T02:30:00Z'
});
const article = () => {
	const feed = read('news-article.json');
	feed.note.published = '2026-10-30T15:00:00Z';
	return feed;
};
const gameButton = () => screen.getByRole('link', { name: /GSW 119 – 114 MIN/ });

beforeEach(() => {
	document.title = '';
	vi.useFakeTimers();
	vi.setSystemTime(new Date('2026-11-03T12:00:00Z'));
	config.article = 'https://feeds.example.com/news/{lang}/articles/{id}.json';
	config.detail = 'https://feeds.example.com/games/{id}.json';
});

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllGlobals();
	vi.useRealTimers();
});

describe('news article route', () => {
	it('turns off prerender and server rendering', async () => {
		const options = await import('../../../../src/routes/news/[id]/+page');
		expect(options.prerender).toBe(false);
		expect(options.ssr).toBe(false);
	});
});

describe('news article page', () => {
	it('loads the article of the id in English and renders the note, its related buttons and the title', async () => {
		stubRoutes({ [articleUrl('en')]: json(article()), [GAME_URL]: json(detail()) });
		await renderPage();
		expect(screen.getByRole('heading', { level: 1, name: 'Warriors beat Minnesota' })).toBeTruthy();
		expect(screen.getByRole('link', { name: '← News' }).getAttribute('href')).toBe('/news');
		expect(screen.getByRole('link', { name: 'Ana Lopez' }).getAttribute('href')).toBe(
			'/player/1001'
		);
		expect(screen.getByRole('link', { name: 'GSW' }).getAttribute('href')).toBe('/team/gsw');
		expect(document.title).toBe('Warriors beat Minnesota · Courtside');
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it("dates the game button with the game's own US Eastern day, not the note's published day", async () => {
		stubRoutes({ [articleUrl('en')]: json(article()), [GAME_URL]: json(detail()) });
		await renderPage();
		expect(calls).toEqual([articleUrl('en'), GAME_URL]);
		expect(gameButton().textContent).toContain('GSW 119 – 114 MIN · Oct 28');
		expect(gameButton().getAttribute('href')).toBe('/game/0022600001');
	});

	it('shows the score without a date until the game detail feed is in', async () => {
		stubRoutes({ [articleUrl('en')]: json(article()), [GAME_URL]: never });
		await renderPage();
		expect(gameButton().textContent?.trim()).toBe('GSW 119 – 114 MIN');
	});

	it('shows the score without a date when the game detail feed fails', async () => {
		stubRoutes({ [articleUrl('en')]: json(article()), [GAME_URL]: json({}, 503) });
		await renderPage();
		expect(gameButton().textContent?.trim()).toBe('GSW 119 – 114 MIN');
	});

	it('shows the score without a date and asks for no game feed with no game detail URL', async () => {
		config.detail = undefined;
		stubRoutes({ [articleUrl('en')]: json(article()) });
		await renderPage();
		expect(calls).toEqual([articleUrl('en')]);
		expect(gameButton().textContent?.trim()).toBe('GSW 119 – 114 MIN');
	});

	it('asks for no game feed when the note has no game', async () => {
		stubRoutes({ [articleUrl('en')]: json({ ...article(), game: null }) });
		await renderPage();
		expect(calls).toEqual([articleUrl('en')]);
		expect(screen.queryByRole('link', { name: /119/ })).toBeNull();
	});

	it('loads the Spanish article in Spanish', async () => {
		preferLanguages(['es']);
		stubRoutes({ [articleUrl('es')]: json(article()), [GAME_URL]: json(detail()) });
		await renderPage();
		expect(calls[0]).toBe(articleUrl('es'));
		expect(gameButton().textContent).toContain('· 28 oct');
	});

	it('shows the not found row on a 404 and on a note of null', async () => {
		stubRoutes({ [articleUrl('en')]: json({}, 404) });
		await renderPage();
		expect(screen.getByText('Note not found.')).toBeTruthy();
		stubRoutes({ [articleUrl('en')]: json({ note: null, game: null }) });
		await renderPage();
		expect(screen.getAllByText('Note not found.').length).toBeGreaterThan(0);
	});

	it('shows the unavailable row on a 503', async () => {
		stubRoutes({ [articleUrl('en')]: json({}, 503) });
		await renderPage();
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
	});
});
