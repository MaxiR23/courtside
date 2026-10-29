// web/tests/lib/components/SeasonTag.test.ts
//
// Tests for the SeasonTag component.
//
// Tested:
// - Renders the text it is given
// - The size, letter spacing, border and color come from tokens in its source
//
// What is covered:
// - The tag drawn from props; jsdom does no layout, so styles are asserted in the source
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SeasonTag.test.ts
//
// SEE: web/src/lib/components/SeasonTag.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import SeasonTag from '../../../src/lib/components/SeasonTag.svelte';

describe('SeasonTag', () => {
	it('renders the text', () => {
		render(SeasonTag, { props: { text: 'Season 2004-05' } });
		expect(screen.getByText('Season 2004-05')).toBeTruthy();
	});

	it('takes its size and letter spacing from tokens, in the accent look on one line', () => {
		render(SeasonTag, { props: { text: 'Season 2004-05' } });
		const tag = screen.getByText('Season 2004-05');
		expect(tag.classList.contains('accent')).toBe(true);
		expect(tag.classList.contains('heading')).toBe(true);
		expect(tag.classList.contains('nowrap')).toBe(true);
		expect(tag.style.getPropertyValue('--tag-size')).toBe('var(--past-tag-size)');
		expect(tag.style.getPropertyValue('--tag-tracking')).toBe('var(--past-tag-letter-spacing)');
	});
});
