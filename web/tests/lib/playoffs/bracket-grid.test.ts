// web/tests/lib/playoffs/bracket-grid.test.ts
//
// Tests for the order and the tree spans of the playoffs bracket's seven groups.
//
// Tested:
// - Seven groups in the design's order, 15 distinct ids, only the Finals flagged
// - The tree's grid-column of each series
// - The ids follow the order of SeriesId, so none is missing
//
// What is covered:
// - Happy path, edge spans and the completeness of the id list
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/bracket-grid.test.ts
//
// SEE: web/src/lib/playoffs/bracket-grid.ts
import { describe, expect, it } from 'vitest';

import type { SeriesId } from '../../../src/lib/contract/playoffs';
import { BRACKET_GROUPS, treeSpan } from '../../../src/lib/playoffs/bracket-grid';

const SERIES_IDS: SeriesId[] = [
	'east-r1-1',
	'east-r1-2',
	'east-r1-3',
	'east-r1-4',
	'east-r2-1',
	'east-r2-2',
	'east-r3',
	'finals',
	'west-r3',
	'west-r2-1',
	'west-r2-2',
	'west-r1-1',
	'west-r1-2',
	'west-r1-3',
	'west-r1-4'
];

describe('BRACKET_GROUPS', () => {
	it('has seven groups from East round 1 to West round 1', () => {
		expect(BRACKET_GROUPS.map((group) => group.key)).toEqual([
			'east-r1',
			'east-r2',
			'east-r3',
			'finals',
			'west-r3',
			'west-r2',
			'west-r1'
		]);
		expect(BRACKET_GROUPS.map((group) => group.title())).toEqual([
			'East R1',
			'East Semis',
			'East Finals',
			'NBA Finals',
			'West Finals',
			'West Semis',
			'West R1'
		]);
	});

	it('holds 15 different ids', () => {
		const ids = BRACKET_GROUPS.flatMap((group) => group.ids);
		expect(ids).toHaveLength(15);
		expect(new Set(ids).size).toBe(15);
	});

	it('flags only the Finals group', () => {
		expect(BRACKET_GROUPS.filter((group) => group.finals).map((group) => group.key)).toEqual([
			'finals'
		]);
	});

	it('lists the ids in the order of SeriesId, so none is missing', () => {
		expect(BRACKET_GROUPS.flatMap((group) => group.ids)).toEqual(SERIES_IDS);
	});
});

describe('treeSpan', () => {
	it.each([
		['east-r1-1', '1 / 3'],
		['east-r1-4', '7 / 9'],
		['west-r1-2', '3 / 5'],
		['east-r2-1', '2 / 4'],
		['west-r2-2', '6 / 8'],
		['east-r3', '4 / 6'],
		['west-r3', '4 / 6'],
		['finals', '3 / 7']
	] as const)('puts %s at %s', (id, span) => {
		expect(treeSpan(id)).toBe(span);
	});

	it('gives every id a span inside the 8 columns', () => {
		for (const id of SERIES_IDS) {
			const [start, end] = treeSpan(id).split(' / ').map(Number);
			expect(start).toBeGreaterThanOrEqual(1);
			expect(end).toBeLessThanOrEqual(9);
			expect(end).toBeGreaterThan(start);
		}
	});
});
