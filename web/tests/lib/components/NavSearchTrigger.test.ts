// web/tests/lib/components/NavSearchTrigger.test.ts
//
// Tests for the NavSearchTrigger component, the search button at the end of every nav.
//
// Tested:
// - Desktop: a button named Search with the placeholder text
// - Mobile: the mobile class and no placeholder
// - A click opens the search overlay state
// - It registers itself, so closing the overlay focuses it
// - Spanish: the name Buscar and the placeholder Buscar jugador o equipo
//
// What is covered:
// - Both layouts, the click and the focus return; jsdom does not lay out, so the sizes are not asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/NavSearchTrigger.test.ts
//
// SEE: web/src/lib/components/NavSearchTrigger.svelte
import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { searchOverlay } from '../../../src/lib/search/overlay.svelte';
import { preferLanguages } from '../../prefer-languages';

import NavSearchTrigger from '../../../src/lib/components/NavSearchTrigger.svelte';

afterEach(() => {
	searchOverlay.close();
	vi.restoreAllMocks();
});

describe('NavSearchTrigger', () => {
	it('shows the placeholder on desktop', () => {
		render(NavSearchTrigger, { props: { layout: 'desktop' } });
		const button = screen.getByRole('button', { name: 'Search' });
		expect(button.textContent?.trim()).toBe('Search player or team');
		expect(button.classList.contains('mobile')).toBe(false);
	});

	it('shows the icon only on mobile', () => {
		render(NavSearchTrigger, { props: { layout: 'mobile' } });
		const button = screen.getByRole('button', { name: 'Search' });
		expect(button.classList.contains('mobile')).toBe(true);
		expect(button.textContent?.trim()).toBe('');
	});

	it('opens the overlay on click', async () => {
		render(NavSearchTrigger, { props: { layout: 'desktop' } });
		expect(searchOverlay.open).toBe(false);
		await fireEvent.click(screen.getByRole('button', { name: 'Search' }));
		expect(searchOverlay.open).toBe(true);
	});

	it('registers itself, so closing the overlay focuses it', () => {
		render(NavSearchTrigger, { props: { layout: 'desktop' } });
		searchOverlay.show();
		searchOverlay.close();
		expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Search' }));
	});

	it('shows Buscar in Spanish', () => {
		preferLanguages(['es-ES']);
		render(NavSearchTrigger, { props: { layout: 'desktop' } });
		const button = screen.getByRole('button', { name: 'Buscar' });
		expect(button.textContent?.trim()).toBe('Buscar jugador o equipo');
	});
});
