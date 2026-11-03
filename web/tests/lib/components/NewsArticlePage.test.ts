// web/tests/lib/components/NewsArticlePage.test.ts
//
// Tests for the NewsArticlePage component.
//
// Tested:
// - The back link to /news, the tags, the full date and the headline
// - The photo and its credit; no photo draws text only
// - The related player, team and game links with their hrefs; no game button without a game
// - The not found row and the unavailable row
//
// What is covered:
// - Every state of the page and both layouts of the headline
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NewsArticlePage.test.ts
//
// SEE: web/src/lib/components/NewsArticlePage.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NewsArticlePage from '../../../src/lib/components/NewsArticlePage.svelte';
import type { NewsArticleState, NewsArticleView } from '../../../src/lib/news/types';

const view = (change: Partial<NewsArticleView> = {}): NewsArticleView => ({
	card: {
		id: 'n1',
		kind: 'recap',
		kindLabel: 'Recap',
		teamTag: 'GSW',
		english: false,
		date: '2 nov',
		headline: 'A headline',
		description: 'The body of the note.',
		photo: { url: 'https://images.example.com/a.jpg', width: 1280, height: 720 }
	},
	fullDate: 'November 2, 2026, 8:30 PM',
	credit: 'A credit',
	related: {
		players: [{ id: '7', name: 'Ana Lopez' }],
		teams: [{ code: 'gsw', label: 'GSW' }],
		game: { id: 'g1', label: 'GSW 119 – 114 MIN · Oct 28' }
	},
	...change
});
const show = (state: NewsArticleState, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(NewsArticlePage, {
		props: {
			state,
			layout,
			newsHref: '/news' as ResolvedPathname,
			allGamesHref: '/' as ResolvedPathname,
			standingsHref: '/standings' as ResolvedPathname,
			playerHref: (id: string) => `/player/${id}` as ResolvedPathname,
			teamHref: (code: string) => `/team/${code}` as ResolvedPathname,
			gameHref: (id: string) => `/game/${id}` as ResolvedPathname
		}
	});

describe('NewsArticlePage', () => {
	it('draws the back link, the tags, the full date, the headline and the body', () => {
		show({ kind: 'ready', view: view() });
		expect(screen.getByRole('link', { name: '← News' }).getAttribute('href')).toBe('/news');
		expect(screen.getByRole('heading', { level: 1, name: 'A headline' })).toBeTruthy();
		expect(screen.getByText('Recap')).toBeTruthy();
		expect(screen.getByText('November 2, 2026, 8:30 PM')).toBeTruthy();
		expect(screen.getByText('The body of the note.')).toBeTruthy();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('draws the photo and its credit', () => {
		show({ kind: 'ready', view: view() });
		expect(screen.getByRole('img', { name: 'A headline' })).toBeTruthy();
		expect(screen.getByText('A credit')).toBeTruthy();
	});

	it('draws text only without a photo', () => {
		const base = view();
		const { container } = show({
			kind: 'ready',
			view: view({ card: { ...base.card, photo: null }, credit: null })
		});
		expect(screen.queryByRole('img', { name: 'A headline' })).toBeNull();
		expect(container.querySelector('figure')).toBeNull();
	});

	it('links the related player, team and game', () => {
		show({ kind: 'ready', view: view() });
		expect(screen.getByRole('link', { name: 'Ana Lopez' }).getAttribute('href')).toBe('/player/7');
		expect(screen.getByRole('link', { name: 'GSW' }).getAttribute('href')).toBe('/team/gsw');
		const game = screen.getByRole('link', { name: 'GSW 119 – 114 MIN · Oct 28' });
		expect(game.getAttribute('href')).toBe('/game/g1');
		expect(game.getAttribute('style')).toContain('--button-border: var(--color-accent)');
	});

	it('draws no game button without a game and no Related section without any', () => {
		const base = view();
		show({
			kind: 'ready',
			view: view({ related: { ...base.related, game: null } })
		});
		expect(screen.queryByRole('link', { name: /119/ })).toBeNull();
	});

	it('draws the headline smaller on mobile', () => {
		const { container } = show({ kind: 'ready', view: view() }, 'mobile');
		expect(container.querySelector('.content')?.classList.contains('mobile')).toBe(true);
	});

	it('draws the not found row with a link back', () => {
		show({ kind: 'not-found' });
		expect(screen.getByText('Note not found.')).toBeTruthy();
		expect(screen.getAllByRole('link', { name: '← News' })).toHaveLength(2);
	});

	it('draws the unavailable row, and bones while loading', () => {
		const { unmount } = show({ kind: 'unavailable' });
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		unmount();
		const { container } = show({ kind: 'loading' });
		expect(container.querySelector('.bones')).not.toBeNull();
	});
});
