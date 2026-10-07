// web/tests/lib/game/win-probability.test.ts
//
// Tests for the win probability chart geometry.
//
// Tested:
// - The x span is the largest elapsed seconds in the feed, never the last point's
// - A single point at zero still has a span of one second
// - The home probability maps to y, top being 100% home; x stays in seconds
// - One segment per pair of points, none for a single point
// - The marker sits on the latest point, as a fraction of the given domain
// - The domain is the period boundaries' end when present, else the span
// - Gridlines sit at each period start after the first; labels are centered on their period
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
	domain,
	gridlines,
	markerPosition,
	periodLabels,
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
		expect(markerPosition(points, span(points))).toEqual({ left: 0.5, top: 0.25 });
	});

	it('places the marker as a fraction of the given domain', () => {
		expect(markerPosition([point(0, 0.5), point(1000, 0.75)], 4000)).toEqual({
			left: 0.25,
			top: 0.25
		});
	});
});

const bounds = (starts: number[], end: number) => ({
	periods: starts.map((start, i) => ({ label: `P${i + 1}`, start })),
	end
});
const regulation = bounds([0, 720, 1440, 2160], 2880);
const overtime = bounds([0, 720, 1440, 2160, 2880, 3180], 3480);

describe('domain', () => {
	it('is the end of the boundaries, not the last point, so a live game keeps the full axis', () => {
		expect(domain([point(0, 0.5), point(1200, 0.6)], regulation)).toBe(2880);
	});

	it('falls back to the span of the points without boundaries', () => {
		const points = [point(0, 0.5), point(3000, 0.6), point(1200, 0.4)];
		expect(domain(points, null)).toBe(span(points));
	});

	it('rejects an end that is not positive, not finite or before the last point', () => {
		const points = [point(0, 0.5), point(100, 0.6)];
		expect(() => domain(points, bounds([0], 0))).toThrow(RangeError);
		expect(() => domain(points, bounds([0], Infinity))).toThrow(RangeError);
		expect(() => domain(points, bounds([0], 50))).toThrow(RangeError);
	});
});

describe('gridlines', () => {
	it('puts one at each start after the first, at 250, 500 and 750 for regulation', () => {
		expect(gridlines(regulation)).toEqual([250, 500, 750]);
	});

	it('adds one per overtime period and moves the regulation lines left', () => {
		const lines = gridlines(overtime);
		expect(lines).toHaveLength(5);
		expect(lines[0]).toBeCloseTo((720 * CHART_WIDTH) / 3480);
		expect(lines[0]).toBeLessThan(250);
		expect(lines[4]).toBeCloseTo((3180 * CHART_WIDTH) / 3480);
	});

	it('draws none for a single period', () => {
		expect(gridlines(bounds([0], 100))).toEqual([]);
	});
});

describe('periodLabels', () => {
	it('centers one label under each period of a regulation game', () => {
		expect(periodLabels(regulation).map((l) => l.center)).toEqual([0.125, 0.375, 0.625, 0.875]);
		expect(periodLabels(regulation).map((l) => l.label)).toEqual(['P1', 'P2', 'P3', 'P4']);
	});

	it('gives a single period one centered label', () => {
		expect(periodLabels(bounds([0], 100))).toEqual([{ label: 'P1', center: 0.5 }]);
	});

	it('rejects starts that do not increase or lie outside the game', () => {
		expect(() => periodLabels(bounds([0, 20, 10], 100))).toThrow(RangeError);
		expect(() => periodLabels(bounds([0, 100], 100))).toThrow(RangeError);
		expect(() => periodLabels(bounds([-1, 10], 100))).toThrow(RangeError);
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
