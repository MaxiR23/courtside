// web/tests/routes/preview/Preview.test.ts
//
// Tests for the development-only component preview content.
//
// Tested:
// - Shows every base component in each of its variants
// - Shows the hero in its three states and the footer
// - Uses no external image URL
//
// What is covered:
// - The only state it has (static sample content)
//
// Run with: cd web && pnpm exec vitest run tests/routes/preview/Preview.test.ts
//
// SEE: web/src/routes/preview/Preview.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Preview from '../../../src/routes/preview/Preview.svelte';

describe('component preview', () => {
	it('shows every base component in each of its variants', () => {
		const { container } = render(Preview);
		for (const name of [
			'BlueprintFrame',
			'Button',
			'LiveBadge',
			'StatusTag',
			'Kicker',
			'TeamMonogram'
		]) {
			expect(screen.getByRole('heading', { level: 2, name })).toBeTruthy();
		}
		expect(screen.getByRole('button', { name: 'Primary action' })).toBeTruthy();
		expect(screen.getByRole('link', { name: 'Secondary link' })).toBeTruthy();
		expect(screen.getByText('LIVE')).toBeTruthy();
		for (const label of ['Tonight', 'Live now', 'Final']) {
			expect(screen.getAllByText(label).length).toBeGreaterThanOrEqual(1);
		}
		expect(screen.getAllByText('10:30 PM ET · Chase Center').length).toBeTruthy();
		expect(container.querySelectorAll('.team-monogram.large')).toHaveLength(1);
		expect(container.querySelectorAll('.team-monogram.small')).toHaveLength(1);
	});

	it('shows the hero in its Tonight, Live now and Final states', () => {
		const { container } = render(Preview);
		for (const name of ['Hero: Tonight', 'Hero: Live now', 'Hero: Final']) {
			expect(screen.getByRole('heading', { level: 2, name })).toBeTruthy();
		}
		expect(container.querySelectorAll('.hero')).toHaveLength(3);
	});

	it('shows the footer', () => {
		render(Preview);
		expect(screen.getByRole('heading', { level: 2, name: 'SiteFooter' })).toBeTruthy();
		expect(screen.getByText('Personal project. Not affiliated with the NBA.')).toBeTruthy();
	});

	it('uses no external image URL', () => {
		const { container } = render(Preview);
		const images = container.querySelectorAll('img');
		expect(images.length).toBeGreaterThan(0);
		for (const img of images) {
			expect(img.getAttribute('src') ?? '').not.toMatch(/^(https?:)?\/\//);
		}
	});
});
