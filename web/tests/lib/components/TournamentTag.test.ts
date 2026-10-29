// web/tests/lib/components/TournamentTag.test.ts
//
// Tests for the TournamentTag component.
//
// Tested:
// - Shows the text it is given, in its own class
// - The finals tag gets the finals class and the others do not
// - Plain text: no link and no button
//
// What is covered:
// - Both variants of the tag; the colors and the ellipsis are CSS and jsdom does no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/TournamentTag.test.ts
//
// SEE: web/src/lib/components/TournamentTag.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import TournamentTag from '../../../src/lib/components/TournamentTag.svelte';

describe('TournamentTag', () => {
	it('shows the text', () => {
		render(TournamentTag, { props: { text: 'Play-In', finals: false } });
		const tag = screen.getByText('Play-In');
		expect(tag.classList.contains('tag')).toBe(true);
		expect(tag.classList.contains('outline')).toBe(true);
		expect(tag.classList.contains('solid')).toBe(false);
		expect(tag.style.getPropertyValue('--tag-border')).toBe('var(--playoffs-tag-border)');
		expect(tag.style.getPropertyValue('--tag-color')).toBe('var(--color-ink)');
		expect(tag.classList.contains('truncate')).toBe(true);
	});

	it('marks the finals tag', () => {
		render(TournamentTag, { props: { text: 'NBA Finals', finals: true } });
		const tag = screen.getByText('NBA Finals');
		expect(tag.classList.contains('solid')).toBe(true);
		expect(tag.style.getPropertyValue('--tag-border')).toBe('');
		expect(tag.style.getPropertyValue('--tag-color')).toBe('');
	});

	it('is plain text with no link or button', () => {
		const { container } = render(TournamentTag, { props: { text: 'Playoffs', finals: false } });
		expect(container.querySelector('a, button')).toBeNull();
	});
});
