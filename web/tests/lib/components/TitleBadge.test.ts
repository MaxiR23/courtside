// web/tests/lib/components/TitleBadge.test.ts
//
// Tests for the TitleBadge component.
//
// Tested:
// - Shows the title text; the solid class only for the NBA title
// - Plain text: no link and no button
//
// What is covered:
// - Both tones of the badge; the colors and the wrapping are CSS and jsdom does no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TitleBadge.test.ts
//
// SEE: web/src/lib/components/TitleBadge.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TitleBadge from '../../../src/lib/components/TitleBadge.svelte';

describe('TitleBadge', () => {
	it('shows a solid badge for the NBA title', () => {
		render(TitleBadge, { props: { title: { text: '2027 NBA Champions', solid: true } } });
		expect(screen.getByText('2027 NBA Champions').classList.contains('solid')).toBe(true);
	});

	it('shows an outline badge for any other title', () => {
		render(TitleBadge, { props: { title: { text: 'West Champions', solid: false } } });
		const badge = screen.getByText('West Champions');
		expect(badge.classList.contains('title-badge')).toBe(true);
		expect(badge.classList.contains('solid')).toBe(false);
	});

	it('is plain text with no link or button', () => {
		const { container } = render(TitleBadge, { props: { title: { text: 'x', solid: false } } });
		expect(container.querySelector('a, button')).toBeNull();
	});
});
