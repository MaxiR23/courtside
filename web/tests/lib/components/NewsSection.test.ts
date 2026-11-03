// web/tests/lib/components/NewsSection.test.ts
//
// Tests for the NewsSection component of the team, player and game pages.
//
// Tested:
// - Loading draws a busy section with bones and no link
// - The team shape draws the newest note as a feature and the rest as rows
// - The rows shape draws rows only, in the given columns; the feature shape draws one note
//
// What is covered:
// - The three shapes and the loading state
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NewsSection.test.ts
//
// SEE: web/src/lib/components/NewsSection.svelte
import type { ResolvedPathname } from '$app/types';
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NewsSection from '../../../src/lib/components/NewsSection.svelte';
import type { NewsCardView } from '../../../src/lib/news/types';

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
const noteHref = (id: string) => `/news/${id}` as ResolvedPathname;
const show = (
	shape: 'feature-rows' | 'rows' | 'feature',
	block: Parameters<typeof NewsSection>[1]['block'] = { kind: 'ready', notes },
	columns: 1 | 2 = 1
) =>
	render(NewsSection, {
		props: { id: 'news', title: 'News', block, shape, columns, layout: 'desktop', noteHref }
	});

describe('NewsSection', () => {
	it('is busy with bones and no link while loading', () => {
		const { container } = show('feature-rows', { kind: 'loading' });
		expect(container.querySelector('section')?.getAttribute('aria-busy')).toBe('true');
		expect(container.querySelector('.bones')).not.toBeNull();
		expect(container.querySelectorAll('a')).toHaveLength(0);
	});

	it('draws the newest note as a feature and the rest as rows', () => {
		const { container } = show('feature-rows');
		expect(container.querySelectorAll('.feature')).toHaveLength(1);
		expect(container.querySelectorAll('.row')).toHaveLength(2);
	});

	it('draws rows only, in two columns when asked', () => {
		const { container } = show('rows', { kind: 'ready', notes }, 2);
		expect(container.querySelectorAll('.feature')).toHaveLength(0);
		expect(container.querySelectorAll('.row')).toHaveLength(3);
		expect(container.querySelector('.rows.two')).not.toBeNull();
	});

	it('draws one feature for the game shape', () => {
		const { container } = show('feature');
		expect(container.querySelectorAll('a')).toHaveLength(1);
		expect(container.querySelector('#news')).not.toBeNull();
	});
});
