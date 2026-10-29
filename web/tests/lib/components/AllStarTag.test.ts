// web/tests/lib/components/AllStarTag.test.ts
//
// Tests for the AllStarTag component.
//
// Tested:
// - Shows the tag text with the context line
// - Shows the tag text without a context line
// - Has the solid class only when solid is set
// - Plain text: no link and no button
//
// What is covered:
// - The states of the tag; the colors, the gap and the ellipsis are CSS and jsdom does no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AllStarTag.test.ts
//
// SEE: web/src/lib/components/AllStarTag.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AllStarTag from '../../../src/lib/components/AllStarTag.svelte';

describe('AllStarTag', () => {
	it('shows the tag text with the context line', () => {
		render(AllStarTag, { props: { text: 'All-Star', context: 'Round Robin' } });
		expect(screen.getByText('All-Star').classList.contains('tag')).toBe(true);
		expect(screen.getByText('Round Robin').classList.contains('context')).toBe(true);
	});

	it('shows no context line without a context', () => {
		const { container } = render(AllStarTag, { props: { text: 'All-Star 2027' } });
		expect(screen.getByText('All-Star 2027')).toBeTruthy();
		expect(container.querySelector('.context')).toBeNull();
	});

	it('has the solid class only when solid is set', () => {
		const { rerender } = render(AllStarTag, { props: { text: 'All-Star' } });
		expect(screen.getByText('All-Star').classList.contains('solid')).toBe(false);
		rerender({ text: 'All-Star', solid: true });
		expect(screen.getByText('All-Star').classList.contains('solid')).toBe(true);
	});

	it('is plain text with no link or button', () => {
		const { container } = render(AllStarTag, {
			props: { text: 'All-Star', context: 'Semifinals' }
		});
		expect(screen.queryByRole('link')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
		expect(container.querySelector('a, button')).toBeNull();
	});
});
