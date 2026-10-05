// web/tests/routes/+page.test.ts
//
// Tests for the home page.
//
// Tested:
// - Shows the site name as the page heading
// - Shows the not-affiliated line in the footer
//
// What is covered:
// - The only state the page has (static content, no data, no interaction)
//
// Run with: cd web && pnpm exec vitest run tests/routes/+page.test.ts
//
// SEE: web/src/routes/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Page from '../../src/routes/+page.svelte';

describe('home page', () => {
	it('shows the site name as the page heading', () => {
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Courtside' })).toBeTruthy();
	});

	it('shows the not-affiliated line in the footer', () => {
		render(Page);
		expect(screen.getByRole('contentinfo').textContent?.trim()).toBe(
			'Personal project. Not affiliated with the NBA.'
		);
	});
});
