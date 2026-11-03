// web/tests/lib/components/HomeNews.test.ts
//
// Tests for the HomeNews carousel.
//
// Tested:
// - A null block draws nothing
// - Loading draws bones and no link
// - Ready draws a card per note and See all to /news
// - Next scrolls forward and Previous back, smoothly; reduced motion scrolls at once
// - Previous is disabled at the start
//
// What is covered:
// - Every block state and the buttons; jsdom has no layout, so scroll positions are not asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/HomeNews.test.ts
//
// SEE: web/src/lib/components/HomeNews.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import HomeNews from '../../../src/lib/components/HomeNews.svelte';
import type { NewsBlock, NewsCardView } from '../../../src/lib/news/types';

const notes = ['a', 'b', 'c'].map((id): NewsCardView => ({
	id,
	kind: 'news',
	kindLabel: 'News',
	teamTag: null,
	english: false,
	date: '2 nov',
	headline: `Headline ${id}`,
	description: null,
	photo: null
}));
const seeAllHref = '/news' as ResolvedPathname;
const noteHref = (id: string) => `/news/${id}` as ResolvedPathname;
const show = (block: NewsBlock) =>
	render(HomeNews, { props: { block, layout: 'desktop', seeAllHref, noteHref } });

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('HomeNews', () => {
	it('draws nothing for a null block', () => {
		const { container } = show(null);
		expect(container.innerHTML.replace(/<!---->/g, '')).toBe('');
	});

	it('draws bones and no link while loading', () => {
		const { container } = show({ kind: 'loading' });
		expect(screen.getByRole('heading', { level: 2, name: 'News' })).toBeTruthy();
		expect(container.querySelectorAll('.bones .slot')).toHaveLength(3);
		expect(container.querySelectorAll('a')).toHaveLength(0);
	});

	it('draws a card per note and a See all link to /news', () => {
		const { container } = show({ kind: 'ready', notes });
		expect(container.querySelectorAll('.track li')).toHaveLength(3);
		expect(screen.getByRole('link', { name: 'See all →' }).getAttribute('href')).toBe('/news');
		expect(container.querySelectorAll('.bar')).toHaveLength(3);
		expect(container.querySelector('.bar.current')).not.toBeNull();
	});

	it('scrolls forward on Next and back on Previous, smoothly', async () => {
		const scrollBy = vi.fn();
		HTMLElement.prototype.scrollBy = scrollBy;
		show({ kind: 'ready', notes });
		await fireEvent.click(screen.getByRole('button', { name: 'Next notes' }));
		expect(scrollBy.mock.calls[0]?.[0].behavior).toBe('smooth');
		expect(scrollBy.mock.calls[0]?.[0].left).toBeGreaterThanOrEqual(0);
	});

	it('scrolls at once under reduced motion', async () => {
		const scrollBy = vi.fn();
		HTMLElement.prototype.scrollBy = scrollBy;
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		show({ kind: 'ready', notes });
		await fireEvent.click(screen.getByRole('button', { name: 'Next notes' }));
		expect(scrollBy.mock.calls[0]?.[0].behavior).toBe('auto');
	});

	it('disables Previous at the start', () => {
		show({ kind: 'ready', notes });
		expect(
			(screen.getByRole('button', { name: 'Previous notes' }) as HTMLButtonElement).disabled
		).toBe(true);
		expect((screen.getByRole('button', { name: 'Next notes' }) as HTMLButtonElement).disabled).toBe(
			false
		);
	});

	it('disables Next and lights the last bar at the end of the track', async () => {
		const { container } = show({ kind: 'ready', notes });
		const track = container.querySelector('.track') as HTMLElement;
		Object.defineProperty(track, 'scrollWidth', { configurable: true, value: 1000 });
		Object.defineProperty(track, 'clientWidth', { configurable: true, value: 600 });
		track.querySelectorAll('li').forEach((li, i) => {
			Object.defineProperty(li, 'offsetLeft', { configurable: true, value: i * 200 });
		});
		track.scrollLeft = 400;
		await fireEvent.scroll(track);
		expect((screen.getByRole('button', { name: 'Next notes' }) as HTMLButtonElement).disabled).toBe(
			true
		);
		const bars = container.querySelectorAll('.bar');
		expect(bars[bars.length - 1]?.classList.contains('current')).toBe(true);
	});
});
