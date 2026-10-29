// web/tests/lib/components/CupMarkTag.test.ts
//
// Tests for the CupMarkTag component.
//
// Tested:
// - Shows the tag text it is given, in its own class
// - Plain text: no link and no button
//
// What is covered:
// - Both states of the tag; the accent color and the ellipsis are CSS and jsdom does no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/CupMarkTag.test.ts
//
// SEE: web/src/lib/components/CupMarkTag.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import CupMarkTag from '../../../src/lib/components/CupMarkTag.svelte';

describe('CupMarkTag', () => {
	it('shows the tag text', () => {
		render(CupMarkTag, { props: { text: 'NBA Cup · Semifinal' } });
		const tag = screen.getByText('NBA Cup · Semifinal');
		expect(tag.classList.contains('tag')).toBe(true);
		expect(tag.classList.contains('accent')).toBe(true);
		expect(tag.classList.contains('truncate')).toBe(true);
	});

	it('is plain text with no link or button', () => {
		const { container } = render(CupMarkTag, { props: { text: 'NBA Cup · Group play' } });
		expect(screen.queryByRole('link')).toBeNull();
		expect(screen.queryByRole('button')).toBeNull();
		expect(container.querySelector('a, button')).toBeNull();
	});
});
