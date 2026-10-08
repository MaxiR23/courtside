// web/tests/lib/components/ProfileCells.test.ts
//
// Tests for the ProfileCells component.
//
// Tested:
// - The cells in order with their sub-lines
// - No sub-line element when sub is null
// - Nothing rendered for an empty list
//
// What is covered:
// - Each case, from props
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ProfileCells.test.ts
//
// SEE: web/src/lib/components/ProfileCells.svelte
import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import ProfileCells from '../../../src/lib/components/ProfileCells.svelte';

describe('ProfileCells', () => {
	it('shows the cells in order with their sub-lines', () => {
		const { container } = render(ProfileCells, {
			props: {
				cells: [
					{ label: 'Height', value: '6\'6"', sub: '198 cm' },
					{ label: 'College', value: 'Kentucky', sub: null }
				]
			}
		});
		const cells = [...container.querySelectorAll('.cell')];
		expect(cells.map((c) => c.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			'Height 6\'6" 198 cm',
			'College Kentucky'
		]);
		expect(cells[1]?.querySelector('.sub')).toBeNull();
	});

	it('renders nothing for an empty list', () => {
		const { container } = render(ProfileCells, { props: { cells: [] } });
		expect(container.querySelector('.cells')).toBeNull();
	});
});
