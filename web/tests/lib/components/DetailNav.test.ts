// web/tests/lib/components/DetailNav.test.ts
//
// Tests for the DetailNav component.
//
// Tested:
// - Shows the brand name
// - Shows an All games link pointing at the given address
//
// What is covered:
// - Both items of the nav row shared by the game and team pages
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/DetailNav.test.ts
//
// SEE: web/src/lib/components/DetailNav.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import DetailNav from '../../../src/lib/components/DetailNav.svelte';

describe('DetailNav', () => {
	it('shows the brand name', () => {
		render(DetailNav, { props: { allGamesHref: '/' } });
		expect(screen.getByText('Courtside')).toBeTruthy();
	});

	it('links All games to the given address', () => {
		render(DetailNav, { props: { allGamesHref: '/' } });
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
	});
});
