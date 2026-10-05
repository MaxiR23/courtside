// web/tests/lib/schedule/stats.test.ts
//
// Tests for the team stat comparison logic.
//
// Tested:
// - The leading side of a stat, with turnovers where lower is better
// - A tie leads no side
// - Each bar's share of its half
// - A negative or non-finite value throws a RangeError
//
// What is covered:
// - Happy path, edge cases (tie, zeros) and error cases
//
// Run with: cd web && pnpm exec vitest run tests/lib/schedule/stats.test.ts
//
// SEE: web/src/lib/schedule/stats.ts
import { describe, expect, it } from 'vitest';

import { barShares, leadingSide } from '../../../src/lib/schedule/stats';

describe('leadingSide', () => {
	it('leads with the higher value for field goals, rebounds and assists', () => {
		expect(leadingSide(0.5, 0.4, false)).toBe('away');
		expect(leadingSide(40, 45, false)).toBe('home');
	});

	it('leads with the lower value for turnovers', () => {
		expect(leadingSide(9, 14, true)).toBe('away');
		expect(leadingSide(15, 11, true)).toBe('home');
	});

	it('leads no side on a tie', () => {
		expect(leadingSide(10, 10, false)).toBeNull();
		expect(leadingSide(10, 10, true)).toBeNull();
	});

	it('throws a RangeError for a negative or non-finite value', () => {
		expect(() => leadingSide(-1, 2, false)).toThrow(RangeError);
		expect(() => leadingSide(1, Number.NaN, false)).toThrow(RangeError);
	});
});

describe('barShares', () => {
	it('gives the larger value a full half and the other its proportion', () => {
		expect(barShares(50, 25)).toEqual({ away: 1, home: 0.5 });
		expect(barShares(10, 40)).toEqual({ away: 0.25, home: 1 });
	});

	it('gives both bars no length when both values are zero', () => {
		expect(barShares(0, 0)).toEqual({ away: 0, home: 0 });
	});

	it('throws a RangeError for a negative or non-finite value', () => {
		expect(() => barShares(1, -2)).toThrow(RangeError);
		expect(() => barShares(Number.POSITIVE_INFINITY, 2)).toThrow(RangeError);
	});
});
