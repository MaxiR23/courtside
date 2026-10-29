// web/tests/lib/components/ProfileCells.test.ts
//
// Tests for the ProfileCells component.
//
// Tested:
// - The cells in order with their sub-lines
// - No sub-line element when sub is null
// - Nothing rendered for an empty list
// - The column minimum, a fixed column count, the dl form and the forwarded value variants
//
// What is covered:
// - Each case, from props
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/ProfileCells.test.ts
//
// SEE: web/src/lib/components/ProfileCells.svelte
import { render, screen } from '@testing-library/svelte';
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

	it('renders the empty grid element for an empty list when asked to keep it', () => {
		const { container } = render(ProfileCells, { props: { cells: [], keepEmpty: true } });
		const grid = container.querySelector('.cells');
		expect(grid).not.toBeNull();
		expect(grid?.children).toHaveLength(0);
	});

	const two = [
		{ label: 'A', value: '1', sub: null },
		{ label: 'B', value: '2', sub: null }
	];

	it('sets the column minimum from min, the profile minimum by default', () => {
		const byDefault = render(ProfileCells, { props: { cells: two } });
		const grid = byDefault.container.querySelector<HTMLElement>('.cells')!;
		expect(grid.style.getPropertyValue('--cells-min')).toBe('var(--player-profile-cell-min)');
		byDefault.unmount();
		const custom = render(ProfileCells, {
			props: { cells: two, min: 'var(--team-header-cell-min)' }
		});
		expect(
			custom.container.querySelector<HTMLElement>('.cells')!.style.getPropertyValue('--cells-min')
		).toBe('var(--team-header-cell-min)');
	});

	it('uses a fixed column count only when columns is given', () => {
		const auto = render(ProfileCells, { props: { cells: two } });
		const autoGrid = auto.container.querySelector<HTMLElement>('.cells')!;
		expect(autoGrid.classList.contains('fixed')).toBe(false);
		expect(autoGrid.style.getPropertyValue('--cells-columns')).toBe('');
		auto.unmount();
		const fixed = render(ProfileCells, { props: { cells: two, columns: 5 } });
		const fixedGrid = fixed.container.querySelector<HTMLElement>('.cells')!;
		expect(fixedGrid.classList.contains('fixed')).toBe(true);
		expect(fixedGrid.style.getPropertyValue('--cells-columns')).toBe('5');
	});

	it('renders a dl of terms and definitions with list, and a div without it', () => {
		const list = render(ProfileCells, { props: { cells: two, list: true } });
		expect(list.container.querySelector('.cells')?.tagName).toBe('DL');
		expect(screen.getAllByRole('term').map((t) => t.textContent)).toEqual(['A', 'B']);
		expect(screen.getAllByRole('definition').map((t) => t.textContent)).toEqual(['1', '2']);
		list.unmount();
		const plain = render(ProfileCells, { props: { cells: two } });
		expect(plain.container.querySelector('.cells')?.tagName).toBe('DIV');
	});

	it('forwards size, strong and numeric to every cell', () => {
		const { container } = render(ProfileCells, {
			props: { cells: two, size: 'hero', strong: true, numeric: true }
		});
		const values = [...container.querySelectorAll('.value')];
		expect(values).toHaveLength(2);
		for (const value of values) {
			for (const name of ['hero', 'strong', 'numeric']) {
				expect(value.classList.contains(name)).toBe(true);
			}
		}
	});
});
