// web/tests/lib/components/NewsRows.test.ts
//
// Tests for the NewsRows component.
//
// Tested:
// - One row per card, each a link to its note
// - Two columns only with columns 2
//
// What is covered:
// - Both column counts and an empty list
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NewsRows.test.ts
//
// SEE: web/src/lib/components/NewsRows.svelte
import type { ResolvedPathname } from '$app/types';
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NewsRows from '../../../src/lib/components/NewsRows.svelte';
import type { NewsCardView } from '../../../src/lib/news/types';

const cards = ['a', 'b', 'c'].map((id): NewsCardView => ({
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
const noteHref = (id: string) => `/news/${id}` as ResolvedPathname;

describe('NewsRows', () => {
	it('draws one row per card, linked to its note', () => {
		const { container } = render(NewsRows, {
			props: { cards, columns: 1, rowLayout: 'desktop', noteHref }
		});
		expect([...container.querySelectorAll('a')].map((a) => a.getAttribute('href'))).toEqual([
			'/news/a',
			'/news/b',
			'/news/c'
		]);
		expect(container.querySelector('.rows')?.classList.contains('two')).toBe(false);
	});

	it('draws two columns with columns 2', () => {
		const { container } = render(NewsRows, {
			props: { cards, columns: 2, rowLayout: 'desktop', noteHref }
		});
		expect(container.querySelector('.rows')?.classList.contains('two')).toBe(true);
	});

	it('draws no row for no card', () => {
		const { container } = render(NewsRows, {
			props: { cards: [], columns: 1, rowLayout: 'desktop', noteHref }
		});
		expect(container.querySelectorAll('li')).toHaveLength(0);
	});
});
