// web/tests/routes/+layout.test.ts
//
// Tests for the root layout.
//
// Tested:
// - Renders the page content
// - Loads only the font weights the design spec names
// - Sets the document language to es with a Spanish browser preference, en otherwise
//
// What is covered:
// - The only state the layout has (renders its children, no interaction)
//
// Run with: cd web && pnpm exec vitest run tests/routes/+layout.test.ts
//
// SEE: web/src/routes/+layout.svelte
import { render, screen } from '@testing-library/svelte';
import { createRawSnippet, tick } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { preferLanguages } from '../prefer-languages';

import Layout from '../../src/routes/+layout.svelte';

function renderLayout() {
	return render(Layout, {
		props: {
			params: {},
			data: {},
			children: createRawSnippet(() => ({ render: () => '<p>Page content</p>' }))
		}
	});
}

afterEach(() => {
	vi.restoreAllMocks();
	document.documentElement.lang = '';
});

describe('root layout', () => {
	it('renders the page content inside the layout', () => {
		renderLayout();
		expect(screen.getByText('Page content')).toBeTruthy();
	});

	it('loads only Barlow 400 and 500 and Barlow Condensed 400 and 600', () => {
		renderLayout();
		const links = [
			...document.head.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')
		].filter((l) => l.href.startsWith('https://fonts.googleapis.com/'));
		expect(links).toHaveLength(1);
		expect(new URL(links[0].href).searchParams.getAll('family')).toEqual([
			'Barlow:wght@400;500',
			'Barlow Condensed:wght@400;600'
		]);
	});

	it('sets the document language to es with a Spanish browser preference', async () => {
		preferLanguages(['es-ES']);
		renderLayout();
		await tick();
		expect(document.documentElement.lang).toBe('es');
	});

	it('sets the document language to en otherwise', async () => {
		preferLanguages(['fr-FR']);
		renderLayout();
		await tick();
		expect(document.documentElement.lang).toBe('en');
	});
});
