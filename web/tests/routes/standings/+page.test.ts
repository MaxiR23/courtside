// web/tests/routes/standings/+page.test.ts
//
// Tests for the standings route.
//
// Tested:
// - The route turns off server rendering and keeps prerender from the layout
// - Renders the nav with Standings current and All games linking to the home
// - Renders the h1 Standings and the footer
// - Renders in Spanish
//
// What is covered:
// - The page in its one state, in two languages
//
// Run with: cd web && pnpm exec vitest run tests/routes/standings/+page.test.ts
//
// SEE: web/src/routes/standings/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import Page from '../../../src/routes/standings/+page.svelte';

describe('standings route', () => {
	it('turns off server rendering and inherits prerender from the layout', async () => {
		const options = await import('../../../src/routes/standings/+page');
		expect(options.ssr).toBe(false);
		expect((options as { prerender?: boolean }).prerender).toBeUndefined();
	});
});

describe('standings page', () => {
	it('renders the nav with Standings current and All games linking to the home', () => {
		render(Page);
		const standings = screen.getByRole('link', { name: 'Standings' });
		expect(standings.getAttribute('aria-current')).toBe('page');
		expect(standings.getAttribute('href')).toBe('/standings');
		expect(screen.getByRole('link', { name: 'All games' }).getAttribute('href')).toBe('/');
	});

	it('renders the h1 and the footer', () => {
		const { container } = render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Standings' })).toBeTruthy();
		expect(container.ownerDocument.querySelector('footer')).toBeTruthy();
	});

	it('renders in Spanish', () => {
		preferLanguages(['es-ES']);
		render(Page);
		expect(screen.getByRole('link', { name: 'Clasificación' })).toBeTruthy();
		expect(screen.getByRole('heading', { level: 1, name: 'Clasificación' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Todos los partidos' })).toBeTruthy();
	});
});
