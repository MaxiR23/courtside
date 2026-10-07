// web/tests/lib/game/win-probability.test.ts
//
// Tests for the win probability chart geometry.
//
// Tested:
// - The x span is the largest elapsed seconds in the feed, never the last point's
// - A single point at zero still has a span of one second
// - The home probability maps to y, top being 100% home; x stays in seconds
// - One segment per pair of points, none for a single point
// - The marker sits on the latest point, as a fraction of the span
// - Invalid input throws a RangeError
//
// What is covered:
// - Happy path, edge cases and error cases of pure logic
//
// Run with: cd web && pnpm exec vitest run tests/lib/game/win-probability.test.ts
//
// SEE: web/src/lib/game/win-probability.ts
import { describe, expect, it } from 'vitest';

import {
	CHART_WIDTH,
	markerPosition,
	segments,
	span,
	toPoint,
	xScale
} from '../../../src/lib/game/win-probability';

const point = (elapsedSeconds: number, homeWinProbability: number) => ({
	elapsedSeconds,
	homeWinProbability
});

describe('span and xScale', () => {
	it('takes the x span from the largest elapsed seconds in the feed, not the last point', () => {
		const points = [point(0, 0.5), point(3000, 0.6), point(1200, 0.4)];
		expect(span(points)).toBe(3000);
		expect(xScale(span(points))).toBeCloseTo(CHART_WIDTH / 3000);
	});

	it('uses a span of one second when the only point is at zero', () => {
		expect(span([point(0, 0.5)])).toBe(1);
		expect(xScale(1)).toBe(CHART_WIDTH);
	});
});

describe('toPoint', () => {
	it('maps the home probability to y, top being 100% home, and keeps x in seconds', () => {
		expect(toPoint(point(900, 1))).toEqual({ x: 900, y: 0 });
		expect(toPoint(point(900, 0.5))).toEqual({ x: 900, y: 100 });
		expect(toPoint(point(900, 0))).toEqual({ x: 900, y: 200 });
	});
});

describe('segments', () => {
	it('returns no segment for a single point and n-1 segments for n points', () => {
		expect(segments([point(0, 0.5)])).toEqual([]);
		const three = segments([point(0, 0.5), point(60, 0.75), point(120, 0.25)]);
		expect(three).toEqual([
			{ x0: 0, y0: 100, x1: 60, y1: 50 },
			{ x0: 60, y0: 50, x1: 120, y1: 150 }
		]);
	});
});

describe('markerPosition', () => {
	it('places the marker on the latest point as a fraction of the span', () => {
		const points = [point(0, 0.5), point(2000, 0.5), point(1000, 0.75)];
		expect(markerPosition(points)).toEqual({ left: 0.5, top: 0.25 });
	});
});

describe('errors', () => {
	it('rejects an empty list, negative seconds and a probability outside 0 to 1', () => {
		expect(() => span([])).toThrow(RangeError);
		expect(() => span([point(-1, 0.5)])).toThrow(RangeError);
		expect(() => toPoint(point(10, 1.1))).toThrow(RangeError);
		expect(() => toPoint(point(10, -0.1))).toThrow(RangeError);
		expect(() => xScale(0)).toThrow(RangeError);
	});
});
