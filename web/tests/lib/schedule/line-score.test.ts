// web/tests/lib/schedule/line-score.test.ts
//
// Tests for the line score layout logic.
//
// Tested:
// - Four quarter columns, plus one column per overtime period played
// - Cells for periods not played yet are null
// - A negative or fractional score throws a RangeError
//
// What is covered:
// - Happy path, edge cases (live game, overtime) and error case
//
// Run with: cd web && pnpm exec vitest run tests/lib/schedule/line-score.test.ts
//
// SEE: web/src/lib/schedule/line-score.ts
import { describe, expect, it } from 'vitest';

import { periodCells, periodColumns } from '../../../src/lib/schedule/line-score';

describe('periodColumns', () => {
	it('has four quarter columns for a game in regulation', () => {
		expect(periodColumns([20, 25, 30, 22], [24, 21, 28, 30])).toEqual([
			{ kind: 'quarter', number: 1 },
			{ kind: 'quarter', number: 2 },
			{ kind: 'quarter', number: 3 },
			{ kind: 'quarter', number: 4 }
		]);
	});

	it('keeps four columns before the fourth quarter is played', () => {
		expect(periodColumns([20], [24])).toHaveLength(4);
		expect(periodColumns([], [])).toHaveLength(4);
	});

	it('adds one overtime column per overtime period played', () => {
		const columns = periodColumns([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6]);
		expect(columns.slice(4)).toEqual([
			{ kind: 'overtime', number: 1 },
			{ kind: 'overtime', number: 2 }
		]);
		expect(periodColumns([1, 2, 3, 4, 5], [1, 2, 3, 4])).toHaveLength(5);
	});
});

describe('periodCells', () => {
	it('fills unplayed periods with null', () => {
		expect(periodCells([20, 25], 4)).toEqual([20, 25, null, null]);
	});

	it('throws a RangeError for a negative or fractional score', () => {
		expect(() => periodCells([-1], 4)).toThrow(RangeError);
		expect(() => periodCells([2.5], 4)).toThrow(RangeError);
	});
});
