// web/tests/lib/components/NewsTags.test.ts
//
// Tests for the NewsTags component.
//
// Tested:
// - A recap tag is accent and a news tag is muted
// - The team tag, the EN tag only when the card is English, and the date
// - The date can be left out
//
// What is covered:
// - Each tag present and absent
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NewsTags.test.ts
//
// SEE: web/src/lib/components/NewsTags.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NewsTags from '../../../src/lib/components/NewsTags.svelte';
import type { NewsCardView } from '../../../src/lib/news/types';

const card = (change: Partial<NewsCardView> = {}): NewsCardView => ({
	id: 'n1',
	kind: 'recap',
	kindLabel: 'Recap',
	teamTag: 'GSW',
	english: false,
	date: '16 h ago',
	headline: 'H',
	description: null,
	photo: null,
	...change
});

describe('NewsTags', () => {
	it('draws a recap as an accent tag and a news note as a muted one', () => {
		const { unmount } = render(NewsTags, { props: { card: card() } });
		expect(screen.getByText('Recap').className).toContain('accent');
		unmount();
		render(NewsTags, { props: { card: card({ kind: 'news', kindLabel: 'News' }) } });
		expect(screen.getByText('News').className).toContain('muted');
	});

	it('draws the team, EN only for an English note, and the date', () => {
		const { unmount } = render(NewsTags, { props: { card: card({ english: true }) } });
		expect(screen.getByText('GSW')).toBeTruthy();
		expect(screen.getByText('EN')).toBeTruthy();
		expect(screen.getByText('16 h ago')).toBeTruthy();
		unmount();
		render(NewsTags, { props: { card: card({ teamTag: null }) } });
		expect(screen.queryByText('EN')).toBeNull();
		expect(screen.queryByText('GSW')).toBeNull();
	});

	it('leaves the date out when asked', () => {
		render(NewsTags, { props: { card: card(), date: false } });
		expect(screen.queryByText('16 h ago')).toBeNull();
	});
});
