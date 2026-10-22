// web/tests/lib/components/SiteFooter.test.ts
//
// Tests for the SiteFooter component.
//
// Tested:
// - Shows the brand name and the not-affiliated line
// - Shows the not-affiliated line in Spanish with a Spanish browser preference
//
// What is covered:
// - Its only state, in English and in Spanish
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/SiteFooter.test.ts
//
// SEE: web/src/lib/components/SiteFooter.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../../prefer-languages';

import SiteFooter from '../../../src/lib/components/SiteFooter.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

describe('SiteFooter', () => {
	it('shows the brand name and the not-affiliated line', () => {
		render(SiteFooter);
		expect(screen.getByText('Courtside')).toBeTruthy();
		expect(
			screen.getByText(
				'Unofficial site, not affiliated with the NBA or its teams. Names and logos belong to their owners.'
			)
		).toBeTruthy();
	});

	it('shows the not-affiliated line in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		render(SiteFooter);
		expect(
			screen.getByText(
				'Sitio no oficial. Sin afiliación con la NBA ni sus equipos. Nombres y logos son propiedad de sus dueños.'
			)
		).toBeTruthy();
	});
});
