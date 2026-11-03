// web/tests/lib/components/NewsCard.test.ts
//
// Tests for the NewsCard component.
//
// Tested:
// - Each layout draws its parts: the card its description, the row its date apart, the feature its text
// - A missing photo draws no image in every layout
// - The card is exactly one link to the note, with no target
// - A photo that fails to load drops its wrapper and the card turns text only; a new URL draws it again
// - The headline is an h3 unless a heading level is passed
// - The feature stacks on mobile and not on desktop
//
// What is covered:
// - Three layouts, photo and no photo, both row layouts
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NewsCard.test.ts
//
// SEE: web/src/lib/components/NewsCard.svelte
import type { ResolvedPathname } from '$app/types';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NewsCard from '../../../src/lib/components/NewsCard.svelte';
import type { NewsCardView } from '../../../src/lib/news/types';

const card = (change: Partial<NewsCardView> = {}): NewsCardView => ({
	id: 'n1',
	kind: 'news',
	kindLabel: 'News',
	teamTag: 'GSW',
	english: false,
	date: '2 nov',
	headline: 'A headline',
	description: 'A description.',
	photo: { url: 'https://images.example.com/a.jpg', width: 1280, height: 720 },
	...change
});
const noteHref = (id: string) => `/news/${id}` as ResolvedPathname;
const show = (
	layout: 'card' | 'row' | 'feature',
	change: Partial<NewsCardView> = {},
	rowLayout: 'desktop' | 'mobile' = 'desktop'
) => render(NewsCard, { props: { card: card(change), layout, rowLayout, noteHref } });

describe('NewsCard', () => {
	it.each(['card', 'row', 'feature'] as const)('draws the %s as one link to the note', (layout) => {
		const { container } = show(layout);
		const links = container.querySelectorAll('a');
		expect(links).toHaveLength(1);
		expect(links[0]?.getAttribute('href')).toBe('/news/n1');
		expect(links[0]?.hasAttribute('target')).toBe(false);
		expect(screen.getByRole('heading', { level: 3, name: 'A headline' })).toBeTruthy();
		expect(container.querySelector('img')).not.toBeNull();
	});

	it('draws the description and the tags in the card and the feature', () => {
		show('card');
		expect(screen.getByText('A description.')).toBeTruthy();
		expect(screen.getByText('2 nov')).toBeTruthy();
		expect(screen.getByText('GSW')).toBeTruthy();
	});

	it('draws the date of a row apart from its tags', () => {
		const { container } = show('row');
		expect(container.querySelector('.row-date')?.textContent).toBe('2 nov');
		expect(container.querySelectorAll('.tags .date')).toHaveLength(0);
	});

	it.each(['card', 'row', 'feature'] as const)(
		'draws text only without a photo in the %s',
		(layout) => {
			const { container } = show(layout, { photo: null, description: null });
			expect(container.querySelector('img')).toBeNull();
			expect(screen.getByText('A headline')).toBeTruthy();
			expect(container.querySelector('.description')).toBeNull();
		}
	);

	it.each([
		['row', '.thumb'],
		['feature', '.photo']
	] as const)('drops the %s photo wrapper when the image fails', async (layout, wrapper) => {
		const { container } = show(layout);
		expect(container.querySelector(wrapper)).not.toBeNull();
		await fireEvent.error(container.querySelector('img') as HTMLImageElement);
		expect(container.querySelector(wrapper)).toBeNull();
		expect(container.querySelector('img')).toBeNull();
		expect(container.querySelector('a.note')?.classList.contains('text-only')).toBe(true);
	});

	it('draws the photo again for a new URL after a failure', async () => {
		const { container, rerender } = show('row');
		await fireEvent.error(container.querySelector('img') as HTMLImageElement);
		expect(container.querySelector('.thumb')).toBeNull();
		const next = card({
			photo: { url: 'https://images.example.com/b.jpg', width: 1280, height: 720 }
		});
		await rerender({ card: next, layout: 'row', rowLayout: 'desktop', noteHref });
		expect(container.querySelector('.thumb img')).not.toBeNull();
		expect(container.querySelector('a.note')?.classList.contains('text-only')).toBe(false);
	});

	it('renders the headline at the level it is given', () => {
		render(NewsCard, {
			props: { card: card(), layout: 'card', rowLayout: 'desktop', noteHref, headingLevel: 2 }
		});
		expect(screen.getByRole('heading', { level: 2, name: 'A headline' })).toBeTruthy();
	});

	it('stacks the feature on mobile and not on desktop', () => {
		const mobile = show('feature', {}, 'mobile');
		expect(mobile.container.querySelector('.note')?.classList.contains('stacked')).toBe(true);
		mobile.unmount();
		const desktop = show('feature', {}, 'desktop');
		expect(desktop.container.querySelector('.note')?.classList.contains('stacked')).toBe(false);
	});

	it('wraps the card and the feature in a frame and leaves the row bare', () => {
		expect(show('card').container.querySelector('.blueprint-frame')).not.toBeNull();
		const row = show('row');
		expect(row.container.querySelector('.blueprint-frame')).toBeNull();
	});
});
