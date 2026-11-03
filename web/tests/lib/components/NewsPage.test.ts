// web/tests/lib/components/NewsPage.test.ts
//
// Tests for the NewsPage component.
//
// Tested:
// - Loading draws bones; unavailable draws the unavailable row
// - The headings go h1 then h2, with no level skipped
// - The grid is capped at three columns
// - Ready draws the grid of cards; the empty filter says so
// - Clicking Recaps calls onFilter and shows aria-pressed
// - The team select lists All teams and the options and calls onTeam; none when teams is null
// - Load more shows only with hasMore and calls onLoadMore
//
// What is covered:
// - Every list state and every interaction
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NewsPage.test.ts
//
// SEE: web/src/lib/components/NewsPage.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import type { ComponentProps } from 'svelte';
import { describe, expect, it, vi } from 'vitest';

import NewsPage from '../../../src/lib/components/NewsPage.svelte';
import type { NewsCardView, NewsListState } from '../../../src/lib/news/types';

const cards = (kinds: Array<'news' | 'recap'>): NewsCardView[] =>
	kinds.map((kind, i) => ({
		id: `n${i}`,
		kind,
		kindLabel: kind,
		teamTag: null,
		english: false,
		date: '2 nov',
		headline: `Headline ${i}`,
		description: null,
		photo: null
	}));
const ready = (kinds: Array<'news' | 'recap'>, hasMore = false): NewsListState => ({
	kind: 'ready',
	cards: cards(kinds),
	hasMore,
	loadingMore: false
});
const show = (list: NewsListState, change: Partial<ComponentProps<typeof NewsPage>> = {}) => {
	const props: ComponentProps<typeof NewsPage> = {
		layout: 'desktop',
		list,
		filter: 'all',
		onFilter: vi.fn(),
		teams: null,
		team: 'all',
		onTeam: vi.fn(),
		onLoadMore: vi.fn(),
		allGamesHref: '/' as ResolvedPathname,
		standingsHref: '/standings' as ResolvedPathname,
		noteHref: (id: string) => `/news/${id}` as ResolvedPathname,
		...change
	};
	return { ...render(NewsPage, { props }), props };
};

describe('NewsPage', () => {
	it('draws bones while loading', () => {
		const { container } = show({ kind: 'loading' });
		expect(container.querySelectorAll('.grid .skeleton, .grid .blueprint-frame')).toHaveLength(3);
	});

	it('draws the unavailable row and no filter when unavailable', () => {
		show({ kind: 'unavailable' });
		expect(screen.getByText("Data isn't available right now. Check back later.")).toBeTruthy();
		expect(screen.queryByRole('group', { name: 'Type' })).toBeNull();
	});

	it('draws a card per note in the grid', () => {
		const { container } = show(ready(['news', 'recap']));
		expect(container.querySelectorAll('.grid li')).toHaveLength(2);
		expect(screen.getByRole('heading', { level: 1, name: 'News' })).toBeTruthy();
		expect(screen.getByRole('contentinfo')).toBeTruthy();
	});

	it('calls onFilter and shows the pressed filter', async () => {
		const { props } = show(ready(['news', 'recap']), { filter: 'recap' });
		expect(screen.getByRole('button', { name: 'Recaps' }).getAttribute('aria-pressed')).toBe(
			'true'
		);
		await fireEvent.click(screen.getByRole('button', { name: 'Recaps' }));
		expect(props.onFilter).toHaveBeenCalledWith('recap');
	});

	it('shows only the filtered kind and the empty message when none is left', () => {
		const { container } = show(ready(['news']), { filter: 'recap' });
		expect(container.querySelectorAll('.grid li')).toHaveLength(0);
		expect(screen.getByText('No notes.')).toBeTruthy();
	});

	it('lists the teams in a select and calls onTeam; none when teams is null', async () => {
		const teams = [
			{ code: 'atl', label: 'Atlanta Hawks' },
			{ code: 'bos', label: 'Boston Celtics' }
		];
		const { props, unmount } = show(ready(['news']), { teams });
		const select = screen.getByRole('combobox', { name: 'Team' }) as HTMLSelectElement;
		expect([...select.options].map((o) => o.textContent)).toEqual([
			'All teams',
			'Atlanta Hawks',
			'Boston Celtics'
		]);
		select.value = 'bos';
		await fireEvent.change(select);
		expect(props.onTeam).toHaveBeenCalledWith('bos');
		unmount();
		show(ready(['news']));
		expect(screen.queryByRole('combobox', { name: 'Team' })).toBeNull();
	});

	it('shows Load more only with hasMore and calls onLoadMore', async () => {
		const { props, unmount } = show(ready(['news'], true));
		await fireEvent.click(screen.getByRole('button', { name: 'Load more' }));
		expect(props.onLoadMore).toHaveBeenCalledTimes(1);
		unmount();
		show(ready(['news'], false));
		expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
	});

	it('goes from the h1 to h2 headlines without skipping a level', () => {
		show(ready(['news', 'recap']));
		const levels = screen.getAllByRole('heading').map((h) => h.tagName);
		expect(levels).toEqual(['H1', 'H2', 'H2']);
	});

	it('caps the grid at three columns', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/NewsPage.svelte'),
			'utf8'
		);
		const rule = source.match(/\.grid\s*\{([^}]*)\}/)?.[1] ?? '';
		expect(rule).toMatch(/calc\(\(100% - 2 \* var\(--news-carousel-gap\)\) \/ 3\)/);
		expect(rule).toContain('var(--news-card-min)');
	});
});
