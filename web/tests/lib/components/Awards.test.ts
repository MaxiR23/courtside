// web/tests/lib/components/Awards.test.ts
//
// Tests for the Awards component.
//
// Tested:
// - The count, the name and the seasons of each award
//
// What is covered:
// - Each case, from props
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/Awards.test.ts
//
// SEE: web/src/lib/components/Awards.svelte
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import Awards from '../../../src/lib/components/Awards.svelte';

describe('Awards', () => {
	it('shows the count, name and seasons of each award', () => {
		render(Awards, {
			props: {
				awards: [
					{ count: '2×', name: 'NBA Most Valuable Player', seasons: '2024-25 · 2025-26' },
					{ count: '3×', name: 'All-NBA First Team', seasons: '2022-23 · 2023-24 · 2024-25' }
				]
			}
		});
		expect(screen.getAllByRole('listitem')).toHaveLength(2);
		for (const text of [
			'2×',
			'NBA Most Valuable Player',
			'2024-25 · 2025-26',
			'3×',
			'All-NBA First Team',
			'2022-23 · 2023-24 · 2024-25'
		]) {
			expect(screen.getByText(text)).toBeTruthy();
		}
	});
});
