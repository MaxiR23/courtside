// web/tests/lib/components/AveragesTable.test.ts
//
// Tests for the AveragesTable component.
//
// Tested:
// - The 12 column headers in spec order
// - Three rows with their season sub-lines
// - A dash in every cell of a null row
// - The Career accent
//
// What is covered:
// - Each case, from the recorded player feed through the props layer
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/AveragesTable.test.ts
//
// SEE: web/src/lib/components/AveragesTable.svelte
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import AveragesTable from '../../../src/lib/components/AveragesTable.svelte';
import type { PlayerFeed } from '../../../src/lib/contract/player';
import { toPlayerView } from '../../../src/lib/feed/player-props';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;
const feed = (): PlayerFeed =>
	JSON.parse(
		readFileSync(join(__dirname, '..', 'feed', 'fixtures', 'player.json'), 'utf8')
	) as PlayerFeed;

const show = (source: PlayerFeed = feed()) =>
	render(AveragesTable, {
		props: {
			averages: toPlayerView(source).sections.averages!,
			gameHref
		}
	});

describe('AveragesTable', () => {
	it('shows the label header and the 12 columns in order', () => {
		show();
		expect(screen.getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
			'Season',
			'GP',
			'MIN',
			'FG%',
			'3P%',
			'FT%',
			'REB',
			'AST',
			'BLK',
			'STL',
			'PF',
			'TOV',
			'PTS'
		]);
	});

	it('shows the three rows with their seasons and values', () => {
		show();
		const headers = screen.getAllByRole('rowheader').map((cell) => cell.textContent?.trim());
		expect(headers[0]).toContain('Regular season');
		expect(headers[0]).toContain('2025-26');
		expect(headers[1]).toContain('Playoffs');
		expect(headers[2]).toBe('Career');
		expect(screen.getByText('47.3%')).toBeTruthy();
		expect(screen.getByText('31.8')).toBeTruthy();
	});

	it('shows a dash in every cell of a null row', () => {
		const source = feed();
		source.averages.playoffs = null;
		const { container } = show(source);
		const row = container.querySelectorAll('.body')[1]!;
		const cells = [...row.querySelectorAll('[role="cell"]')];
		expect(cells).toHaveLength(12);
		expect(cells.every((cell) => cell.textContent?.trim() === '—')).toBe(true);
	});

	it('marks the Career row with the accent', () => {
		const { container } = show();
		expect(
			container.querySelectorAll('.body')[2]!.querySelector('.first')!.classList.contains('accent')
		).toBe(true);
		expect(
			container.querySelectorAll('.body')[0]!.querySelector('.first')!.classList.contains('accent')
		).toBe(false);
	});
});
