// web/tests/routes/preview/Preview.test.ts
//
// Tests for the development-only component preview content.
//
// Tested:
// - Shows every base component in each of its variants
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
			expect(screen.getByText(label)).toBeTruthy();
		}
		expect(screen.getByText('10:30 PM ET · Chase Center')).toBeTruthy();
		expect(container.querySelectorAll('.team-monogram.large')).toHaveLength(1);
		expect(container.querySelectorAll('.team-monogram.small')).toHaveLength(1);
	});
});
