// web/tests/lib/components/RosterTable.test.ts
//
// Tests for the RosterTable component.
//
// Tested:
// - The column headers in order
// - One row per player in feed order, with the player in a sticky row header
// - Values as given, R for a rookie, null cells left empty with the cell count unchanged
// - The status tone classes
// - The mobile class with the mobile layout
//
// What is covered:
// - Structure and classes; jsdom computes no layout, so widths are not asserted
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/RosterTable.test.ts
//
// SEE: web/src/lib/components/RosterTable.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import RosterTable from '../../../src/lib/components/RosterTable.svelte';
import type { RosterRow } from '../../../src/lib/team/types';

const full: RosterRow = {
	id: 'p-sga',
	name: 'Shai Gilgeous-Alexander',
	photo: null,
	number: '2',
	position: 'G',
	height: '6-6',
	weight: '195',
	age: '27',
	born: 'Jul 12, 1998',
	birthplace: 'Toronto, Canada',
	college: 'Kentucky',
	experience: 'R',
	status: { label: 'Out', tone: 'out' }
};

const empty: RosterRow = {
	id: 'p-unknown',
	name: 'Walk On',
	photo: null,
	number: null,
	position: null,
	height: null,
	weight: null,
	age: null,
	born: null,
	birthplace: null,
	college: null,
	experience: null,
	status: { label: 'Active', tone: 'muted' }
};

const questionable: RosterRow = {
	...full,
	id: 'p-q',
	name: 'Q Player',
	status: { label: 'Questionable', tone: 'ink' }
};

const show = (roster: RosterRow[], layout: 'desktop' | 'mobile' = 'desktop') =>
	render(RosterTable, { props: { roster, layout } });

describe('RosterTable', () => {
	it('shows the column headers in order', () => {
		show([full]);
		expect(screen.getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
			'Player',
			'No.',
			'Pos',
			'Ht',
			'Wt',
			'Age',
			'Born',
			'Birthplace',
			'College',
			'Exp',
			'Status'
		]);
	});

	it('shows one row per player in feed order, the player in the row header', () => {
		show([full, empty, questionable]);
		const headers = screen.getAllByRole('rowheader');
		expect(headers.map((cell) => cell.textContent?.trim())).toEqual([
			'SG Shai Gilgeous-Alexander',
			'WO Walk On',
			'QP Q Player'
		]);
	});

	it('shows the values, with R for a rookie', () => {
		show([full]);
		const row = screen.getAllByRole('row')[1]!;
		expect([...row.querySelectorAll('[role="cell"]')].map((cell) => cell.textContent)).toEqual([
			'2',
			'G',
			'6-6',
			'195',
			'27',
			'Jul 12, 1998',
			'Toronto, Canada',
			'Kentucky',
			'R',
			'Out'
		]);
	});

	it('leaves null cells empty and keeps 11 cells in the row', () => {
		show([empty]);
		const row = screen.getAllByRole('row')[1]!;
		const cells = [...row.querySelectorAll('[role="rowheader"], [role="cell"]')];
		expect(cells).toHaveLength(11);
		expect(cells.slice(1, 10).map((cell) => cell.textContent)).toEqual(Array(9).fill(''));
		expect(cells[10]?.textContent).toBe('Active');
	});

	it('marks the status tone', () => {
		const { container } = show([full, questionable, empty]);
		const statuses = [...container.querySelectorAll('.status')];
		expect(statuses.map((cell) => [...cell.classList].find((c) => c.startsWith('tone-')))).toEqual([
			'tone-out',
			'tone-ink',
			'tone-muted'
		]);
	});

	it('uses the mobile class only with the mobile layout', () => {
		const { container, unmount } = show([full]);
		expect(container.querySelector('.table')?.classList.contains('mobile')).toBe(false);
		unmount();
		const mobile = show([full], 'mobile');
		expect(mobile.container.querySelector('.table')?.classList.contains('mobile')).toBe(true);
	});

	it('keeps the first column sticky', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/RosterTable.svelte'),
			'utf8'
		);
		const block = /\.player\s*\{([^}]*)\}/.exec(source)?.[1] ?? '';
		expect(block).toMatch(/position:\s*sticky;/);
		expect(block).toMatch(/left:\s*0;/);
	});
});
