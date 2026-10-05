// web/tests/routes/+page.test.ts
//
// Tests for the home page.
//
// Tested:
// - Shows the site name as the page heading
// - Shows the not-affiliated line in the footer
// - Shows both in Spanish for es-ES and for a regional tag such as es-419
// - Stays English for an unsupported language, or when English is preferred over Spanish
//
// What is covered:
// - The only state the page has (static content, no data, no interaction)
// - Language selection from the browser preference
//
// Run with: cd web && pnpm exec vitest run tests/routes/+page.test.ts
//
// SEE: web/src/routes/+page.svelte
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../prefer-languages';

import Page from '../../src/routes/+page.svelte';

afterEach(() => {
	vi.restoreAllMocks();
});

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

	it('shows the page in Spanish with an es-ES preference', () => {
		preferLanguages(['es-ES']);
		render(Page);
		expect(screen.getByRole('heading', { level: 1, name: 'Courtside' })).toBeTruthy();
		expect(screen.getByRole('contentinfo').textContent?.trim()).toBe(
			'Proyecto personal. Sin afiliación con la NBA.'
		);
	});

	it('shows Spanish for a regional tag such as es-419', () => {
		preferLanguages(['es-419']);
		render(Page);
		expect(screen.getByRole('contentinfo').textContent?.trim()).toBe(
			'Proyecto personal. Sin afiliación con la NBA.'
		);
	});

	it('shows English for an unsupported language', () => {
		preferLanguages(['fr-FR']);
		render(Page);
		expect(screen.getByRole('contentinfo').textContent?.trim()).toBe(
			'Personal project. Not affiliated with the NBA.'
		);
	});

	it('shows English when English is preferred over Spanish', () => {
		preferLanguages(['en-US', 'es']);
		render(Page);
		expect(screen.getByRole('contentinfo').textContent?.trim()).toBe(
			'Personal project. Not affiliated with the NBA.'
		);
	});
});
