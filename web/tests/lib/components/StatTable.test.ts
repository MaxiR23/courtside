// web/tests/lib/components/StatTable.test.ts
//
// Tests for the StatTable component.
//
// Tested:
// - The column headers in order after the label header
// - One row per entry with a sticky row header holding the label and sub-line
// - The muted and points classes, the result cell's win mark, the accent row
// - A link only on a linked row, with the href from gameHref
// - A row with teams draws an inline mark before each code, joined by " · ", hidden from assistive technology; a row with only a sub draws it as before; a row with neither draws no mark (ADR 0070)
// - A row with an opponent draws it after the label ("Apr 29 · @ MEM"), inside the link of a linked row; a row without one is unchanged
//
// - Three teams draw three marks, and the teams line wraps inside the first column with each team kept whole
//
// What is covered:
// - Structure and classes from props; jsdom computes no layout
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StatTable.test.ts
//
// SEE: web/src/lib/components/StatTable.svelte
import type { ResolvedPathname } from '$app/types';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
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
			label: 'Apr 29',
			opponent: { team: { code: 'MEM', name: null, city: null, guest: false }, isHome: false },
			sub: 'NBA Cup',
			link: { gameId: 'g-1', linked: true },
			cells: [{ mark: 'W', win: true, text: '118–104' }, '34', '31']
		},
		{
			key: 'b',
			label: 'Apr 26',
			opponent: { team: { code: 'MEM', name: null, city: null, guest: false }, isHome: true },
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

describe('StatTable opponent', () => {
	it('draws the opponent after the label, inside the link of a linked row', () => {
		show();
		const link = screen.getByRole('link', { name: /Apr 29/ });
		expect(link.textContent?.replace(/\s+/g, ' ').trim()).toBe('Apr 29 · @ MEM');
		expect(link.getAttribute('href')).toBe('/game/g-1');
	});

	it('draws a home opponent with vs on an unlinked row, and leaves a row without one unchanged', () => {
		const { container } = show();
		const labels = [...container.querySelectorAll('.label')].map((l) =>
			l.textContent?.replace(/\s+/g, ' ').trim()
		);
		expect(labels).toEqual(['Apr 29 · @ MEM', 'Apr 26 · vs MEM', 'Career']);
	});

	it('names a guest opponent without a code by its name, unlinked', () => {
		const guest = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };
		const guestTable: StatTableView = {
			...table,
			rows: [{ ...table.rows[1], opponent: { team: guest, isHome: false } }]
		};
		const { container } = render(StatTable, {
			props: { table: guestTable, labelHeader: 'Game', gameHref }
		});
		expect(container.querySelector('.label')?.textContent?.replace(/\s+/g, ' ').trim()).toBe(
			'Apr 26 · @ Mariners'
		);
	});
});

describe('StatTable teams', () => {
	const team = (code: string, logo?: { light: string; dark: string | null }) => ({
		code,
		name: null,
		city: null,
		guest: false,
		...(logo ? { logo } : {})
	});
	const teamsTable: StatTableView = {
		...table,
		rows: [
			{
				key: 'a',
				label: '2024-25',
				sub: null,
				teams: [
					team('LAC', {
						light: 'https://example.com/lac.svg',
						dark: 'https://example.com/lac-dark.svg'
					}),
					team('OKC')
				],
				cells: ['x', 'y', 'z']
			},
			{ key: 'b', label: '2023-24', sub: 'Only sub', cells: ['x', 'y', 'z'] },
			{ key: 'c', label: 'Career', sub: null, cells: ['x', 'y', 'z'] }
		]
	};
	const showTeams = () =>
		render(StatTable, { props: { table: teamsTable, labelHeader: 'Season', gameHref } });

	it('draws an inline mark before each code, the first with the logo and the second a monogram', () => {
		const { container } = showTeams();
		const marks = [
			...container.querySelectorAll('.body')[0]!.querySelectorAll('.team-monogram.inline')
		];
		expect(marks).toHaveLength(2);
		const image = marks[0]!.querySelector('img')!;
		expect(image.getAttribute('src')).toBe('https://example.com/lac-dark.svg');
		expect(image.getAttribute('aria-hidden')).toBe('true');
		expect(image.getAttribute('alt')).toBe('');
		expect(marks[0]!.getAttribute('aria-hidden')).toBe('true');
		expect(marks[1]!.querySelector('img')).toBeNull();
		expect(marks[1]!.textContent).toBe('OKC');
		expect(marks[1]!.getAttribute('aria-hidden')).toBe('true');
	});

	it('writes the codes after the marks joined by a dot', () => {
		const { container } = showTeams();
		const sub = container.querySelector('.body .sub.teams')!;
		expect(sub.textContent?.replace(/\s+/g, ' ').trim()).toContain('LAC · OKC');
	});

	it('draws a sub as text when there are no teams, and no mark on a row with neither', () => {
		const { container } = showTeams();
		const rows = container.querySelectorAll('.body');
		expect(rows[1]!.querySelector('.sub')?.textContent).toBe('Only sub');
		expect(rows[1]!.querySelector('.team-monogram')).toBeNull();
		expect(rows[2]!.querySelector('.team-monogram')).toBeNull();
		expect(rows[2]!.querySelector('.sub')).toBeNull();
	});

	it('draws three marks for a row with three teams', () => {
		const three: StatTableView = {
			...table,
			rows: [
				{
					key: 'a',
					label: '2024-25',
					sub: null,
					teams: [team('LAC'), team('OKC'), team('MEM')],
					cells: ['x', 'y', 'z']
				}
			]
		};
		const { container } = render(StatTable, {
			props: { table: three, labelHeader: 'Season', gameHref }
		});
		expect(container.querySelectorAll('.body .team .team-monogram.inline')).toHaveLength(3);
		expect(container.querySelectorAll('.body .team')).toHaveLength(3);
	});

	it('wraps the teams line and keeps each team unit unbroken', () => {
		const source = readFileSync(
			join(import.meta.dirname, '../../../src/lib/components/StatTable.svelte'),
			'utf8'
		);
		const rule = (selector: string) =>
			new RegExp(`\\n\\t${selector} \\{([^}]*)\\}`).exec(source)?.[1] ?? '';
		expect(rule('\\.teams')).toContain('flex-wrap: wrap');
		expect(rule('\\.team')).toContain('white-space: nowrap');
	});
});
