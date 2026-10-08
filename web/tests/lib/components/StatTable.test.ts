// web/tests/lib/components/StatTable.test.ts
//
// Tests for the StatTable component.
//
// Tested:
// - The column headers in order after the label header
// - One row per entry with a sticky row header holding the label and sub-line
// - The muted and points classes, the result cell's win mark, the accent row
// - A link only on a linked row, with the href from gameHref
//
// What is covered:
// - Structure and classes from props; jsdom computes no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StatTable.test.ts
//
// SEE: web/src/lib/components/StatTable.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import StatTable from '../../../src/lib/components/StatTable.svelte';
import type { StatTableView } from '../../../src/lib/player/types';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const table: StatTableView = {
	columns: [
		{ key: 'result', label: 'Result', wide: true },
		{ key: 'min', label: 'MIN', muted: true },
		{ key: 'pts', label: 'PTS', points: true }
	],
	rows: [
		{
			key: 'a',
			label: 'Apr 29 · @ MEM',
			sub: 'NBA Cup',
			link: { gameId: 'g-1', linked: true },
			cells: [{ mark: 'W', win: true, text: '118–104' }, '34', '31']
		},
		{
			key: 'b',
			label: 'Apr 26 · vs MEM',
			sub: null,
			link: { gameId: 'g-2', linked: false },
			cells: [{ mark: 'L', win: false, text: '101–108' }, '30', '24']
		},
		{ key: 'c', label: 'Career', sub: null, accent: true, cells: ['x', 'y', 'z'] }
	]
};

const show = () => render(StatTable, { props: { table, labelHeader: 'Game', gameHref } });

describe('StatTable', () => {
	it('shows the label header and the column headers in order', () => {
		show();
		expect(screen.getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
			'Game',
			'Result',
			'MIN',
			'PTS'
		]);
	});

	it('shows one row per entry, the label and sub-line in the row header', () => {
		show();
		expect(screen.getAllByRole('row')).toHaveLength(4);
		const headers = screen.getAllByRole('rowheader').map((cell) => cell.textContent?.trim());
		expect(headers[0]).toContain('Apr 29 · @ MEM');
		expect(headers[0]).toContain('NBA Cup');
		expect(headers[2]).toBe('Career');
	});

	it('marks the muted and points cells and the win mark', () => {
		const { container } = show();
		const row = container.querySelectorAll('.body')[0]!;
		const cells = row.querySelectorAll('[role="cell"]');
		expect(cells[1]?.classList.contains('muted')).toBe(true);
		expect(cells[2]?.classList.contains('points')).toBe(true);
		expect(cells[0]?.querySelector('.win')?.textContent).toBe('W');
		expect(cells[0]?.textContent?.replace(/\s+/g, ' ').trim()).toBe('W 118–104');
		const loss = container.querySelectorAll('.body')[1]!.querySelector('[role="cell"]')!;
		expect(loss.querySelector('.win')).toBeNull();
	});

	it('marks the accent row', () => {
		const { container } = show();
		const header = container.querySelectorAll('.body')[2]!.querySelector('[role="rowheader"]')!;
		expect(header.classList.contains('accent')).toBe(true);
	});

	it('links only a linked row, with the href from gameHref', () => {
		const { container } = show();
		const links = screen.getAllByRole('link');
		expect(links).toHaveLength(1);
		expect(links[0]?.getAttribute('href')).toBe('/game/g-1');
		expect(links[0]?.textContent).toBe('Apr 29 · @ MEM');
		const rows = container.querySelectorAll('.body');
		expect(rows[0]?.classList.contains('linked')).toBe(true);
		expect(rows[1]?.classList.contains('linked')).toBe(false);
		expect(rows[1]?.querySelector('a')).toBeNull();
	});

	it('gives every row the same column template', () => {
		const { container } = show();
		const templates = [...container.querySelectorAll('.row')].map(
			(row) => (row as HTMLElement).style.gridTemplateColumns
		);
		expect(new Set(templates).size).toBe(1);
		expect(templates[0]).toContain('var(--player-shooting-column-min)');
	});
});
