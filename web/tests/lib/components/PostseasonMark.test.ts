// web/tests/lib/components/PostseasonMark.test.ts
//
// Tests for the PostseasonMark component.
//
// Tested:
// - Draws the tag, then the context line, then the stakes flag
// - Draws no flag when the stakes are null
// - Draws no context element when the context is null
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
		expect(parts.map((part) => (part.firstElementChild ?? part).className.split(' ')[0])).toEqual([
			'tag',
			'context',
			'tag'
		]);
		expect(parts.map((part) => part.firstElementChild?.classList.contains('accent'))).toEqual([
			false,
			false,
			true
		]);
		expect(parts.map((part) => part.textContent)).toEqual([
			'Playoffs',
			'West finals · Game 7',
			'Game 7'
		]);
	});

	it('draws no flag without stakes', () => {
		const { container } = render(PostseasonMark, { props: { mark: { ...mark, stakes: null } } });
		expect(container.querySelector('.tag.accent')).toBeNull();
		expect(container.querySelector('.postseason-mark')?.children.length).toBe(2);
	});

	it('draws no context element when the context is null', () => {
		const { container } = render(PostseasonMark, {
			props: { mark: { ...mark, context: null, stakes: null } }
		});
		expect(container.querySelector('.context')).toBeNull();
		expect(container.querySelector('.tag:not(.accent)')?.textContent).toBe('Playoffs');
		expect(container.querySelector('.postseason-mark')?.children.length).toBe(1);
	});

	it('draws the finals tag for a Finals game', () => {
		const { container } = render(PostseasonMark, {
			props: { mark: { ...mark, tag: 'NBA Finals', finals: true } }
		});
		expect(container.querySelector('.tag:not(.accent)')?.classList.contains('solid')).toBe(true);
	});
});
