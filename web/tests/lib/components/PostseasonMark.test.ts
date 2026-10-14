// web/tests/lib/components/PostseasonMark.test.ts
//
// Tests for the PostseasonMark component.
//
// Tested:
// - Draws the tag, then the context line, then the stakes flag
// - Draws no flag when the stakes are null
// - Passes the finals variant to the tag
//
// What is covered:
// - Both states of the mark; the gap and the truncation are CSS and jsdom does no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/PostseasonMark.test.ts
//
// SEE: web/src/lib/components/PostseasonMark.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import PostseasonMark from '../../../src/lib/components/PostseasonMark.svelte';
import type { PostseasonMarkView } from '../../../src/lib/playoffs/types';

const mark: PostseasonMarkView = {
	tag: 'Playoffs',
	finals: false,
	context: 'West finals · Game 7',
	stakes: 'Game 7'
};

describe('PostseasonMark', () => {
	it('draws the tag, the context line and the flag in that order', () => {
		const { container } = render(PostseasonMark, { props: { mark } });
		const parts = [...(container.querySelector('.postseason-mark')?.children ?? [])];
		expect(parts.map((part) => part.className.split(' ')[0])).toEqual([
			'tournament-tag',
			'context',
			'stakes-flag'
		]);
		expect(parts.map((part) => part.textContent)).toEqual([
			'Playoffs',
			'West finals · Game 7',
			'Game 7'
		]);
	});

	it('draws no flag without stakes', () => {
		const { container } = render(PostseasonMark, { props: { mark: { ...mark, stakes: null } } });
		expect(container.querySelector('.stakes-flag')).toBeNull();
		expect(container.querySelector('.postseason-mark')?.children.length).toBe(2);
	});

	it('draws the finals tag for a Finals game', () => {
		const { container } = render(PostseasonMark, {
			props: { mark: { ...mark, tag: 'NBA Finals', finals: true } }
		});
		expect(container.querySelector('.tournament-tag')?.classList.contains('finals')).toBe(true);
	});
});
