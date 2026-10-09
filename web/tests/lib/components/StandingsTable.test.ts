// web/tests/lib/components/StandingsTable.test.ts
//
// Tests for the StandingsTable component.
//
// Tested:
// - The h2 and the meta; the 16 header labels; every cell of a row
// - One link per row, to the team page with the lowercase code
// - The playoff and play-in lines only after the rows the view marks
// - A clinch tag only for rows with a clinch; an eliminated row is muted
// - Accents on a win streak, Diff and Tot; a plain tile for null colors
// - The mobile layout hides the city; the team cell is the sticky rowheader
// - Spanish copy
//
// What is covered:
// - The groups of the recorded feed (tests/lib/feed/fixtures/standings.json) through the props layer
// - jsdom does not lay out: classes and attributes are asserted, not pixels
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/StandingsTable.test.ts
//
// SEE: web/src/lib/components/StandingsTable.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import StandingsTable from '../../../src/lib/components/StandingsTable.svelte';
import type { StandingsFeed } from '../../../src/lib/contract/standings';
import { toStandingsView } from '../../../src/lib/feed/standings-props';
import type { StandingsGroupView } from '../../../src/lib/standings/types';
import { preferLanguages } from '../../prefer-languages';

const view = () =>
	toStandingsView(
		JSON.parse(
			readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'standings.json'), 'utf8')
		) as StandingsFeed
	);
const east = (): StandingsGroupView => view().conference[0]!;
const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

const show = (group: StandingsGroupView, layout: 'desktop' | 'mobile' = 'desktop') =>
	render(StandingsTable, { props: { group, layout, teamHref } });

const bodyRows = (container: HTMLElement) => [
	...container.querySelectorAll<HTMLElement>('.row.body')
];

afterEach(() => {
	vi.restoreAllMocks();
});

describe('StandingsTable', () => {
	it('renders the h2 and the meta', () => {
		show(east());
		expect(screen.getByRole('heading', { level: 2, name: 'Eastern Conference' })).toBeTruthy();
		expect(screen.getByText('11 teams · GB vs conference leader')).toBeTruthy();
	});

	it('renders the 16 header labels', () => {
		const { container } = show(east());
		const labels = [
			...container.querySelectorAll(
				'.head [role="columnheader"] span, .head > span.cell:not(.team)'
			)
		].map((el) => el.textContent);
		expect(labels).toEqual([
			'Seed',
			'Team',
			'W',
			'L',
			'Pct',
			'GB',
			'Strk',
			'Home',
			'Away',
			'L10',
			'Div',
			'Conf',
			'PPG',
			'Opp',
			'Diff',
			'Tot'
		]);
	});

	it('renders every cell of a row', () => {
		const { container } = show(east());
		const row = bodyRows(container)[1]!;
		expect(row.querySelector('.seed')?.textContent).toBe('2');
		expect(row.querySelector('.city')?.textContent).toBe('New York');
		expect(row.querySelector('.name')?.textContent).toBe('Knicks');
		expect([...row.querySelectorAll('[role="cell"]')].map((c) => c.textContent)).toEqual([
			'56',
			'26',
			'.682',
			'1.0',
			'L2',
			'29-13',
			'27-14',
			'6-4',
			'14-6',
			'37-17',
			'117.3',
			'112.5',
			'+4.5',
			'+369'
		]);
	});

	it('links every row to its team page', () => {
		const group = east();
		const { container } = show(group);
		const hrefs = [...container.querySelectorAll('a')].map((a) => a.getAttribute('href'));
		expect(hrefs).toEqual(group.rows.map((r) => `/team/${r.code.toLowerCase()}`));
	});

	it('draws the playoff and play-in lines only after the rows the view marks', () => {
		const { container } = show(east());
		const rows = bodyRows(container);
		expect(rows[5]!.nextElementSibling?.classList.contains('playoff')).toBe(true);
		expect(rows[9]!.nextElementSibling?.classList.contains('play-in')).toBe(true);
		expect(container.querySelectorAll('.line')).toHaveLength(2);
		const division = show(view().division[0]!);
		expect(division.container.querySelectorAll('.line')).toHaveLength(0);
	});

	it('draws a ClinchTag only for rows with a clinch', () => {
		const { container } = show(east());
		const counts = bodyRows(container).map((r) => r.querySelectorAll('.clinch-tag').length);
		expect(counts).toEqual([1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0]);
	});

	it('mutes an eliminated row', () => {
		const { container } = show(east());
		expect(bodyRows(container).map((r) => r.classList.contains('eliminated'))).toEqual([
			false,
			false,
			false,
			false,
			false,
			false,
			true,
			false,
			false,
			false,
			false
		]);
	});

	it('accents a win streak, a non-negative Diff and Tot', () => {
		const { container } = show(east());
		const rows = bodyRows(container);
		const accents = (row: HTMLElement) =>
			[...row.querySelectorAll('[role="cell"]')].map((c) => c.classList.contains('accent'));
		const first = accents(rows[0]!);
		expect([first[4], first[12], first[13]]).toEqual([true, true, true]);
		const loser = accents(rows[7]!);
		expect(loser[4]).toBe(false);
		const down = accents(rows[6]!);
		expect([down[4], down[12], down[13]]).toEqual([true, false, false]);
	});

	it('draws a plain tile without a strip for null colors', () => {
		const { container } = show(east());
		const rows = bodyRows(container);
		const tile = rows[8]!.querySelector('.tile')!;
		expect(tile.classList.contains('plain')).toBe(true);
		expect(tile.querySelector('.strip')).toBeNull();
		const colored = rows[0]!.querySelector('.tile')!;
		expect(colored.classList.contains('plain')).toBe(false);
		expect(colored.querySelectorAll('.half')).toHaveLength(2);
	});

	it('hides the city and marks the table mobile in the mobile layout', () => {
		const { container } = show(east(), 'mobile');
		expect(container.querySelector('.table')?.classList.contains('mobile')).toBe(true);
		expect(container.querySelector('.city')).toBeNull();
	});

	it('keeps the team cell as the sticky rowheader', () => {
		const { container } = show(east());
		const headers = container.querySelectorAll('.row.body [role="rowheader"]');
		expect(headers).toHaveLength(11);
		for (const cell of headers) expect(cell.classList.contains('team')).toBe(true);
	});

	it('renders in Spanish', () => {
		preferLanguages(['es-ES']);
		const { container } = show(view().conference[0]!);
		expect(screen.getByRole('heading', { level: 2, name: 'Conferencia Este' })).toBeTruthy();
		expect(screen.getByText('Racha')).toBeTruthy();
		expect(screen.getByText('Puesto')).toBeTruthy();
		expect(container.querySelector('.row.body .cell.accent')?.textContent).toBe('G3');
	});
});
