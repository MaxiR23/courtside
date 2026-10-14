// web/tests/lib/bracket/camera.test.ts
//
// Tests for the camera math shared by the brackets.
//
// Tested:
// - fitRect centers the rect, is limited by width or by height, and stops at maxK
// - fitRect stays finite for a viewport with no size
// - fitView, flyFrames, transformOf and isAtFit export from the shared module
// - clamp handles a value below, inside and above its range
//
// What is covered:
// - Happy path, edge cases and the degenerate viewport
//
// Run with: cd web && pnpm exec vitest run tests/lib/bracket/camera.test.ts
//
// SEE: web/src/lib/bracket/camera.ts
import { describe, expect, it } from 'vitest';

import {
	clamp,
	fitRect,
	fitView,
	flyFrames,
	isAtFit,
	isMeasured,
	transformOf
} from '../../../src/lib/bracket/camera';

describe('fitRect', () => {
	it('centers the rect in the viewport', () => {
		const view = fitRect(
			{ x: 100, y: 50, width: 200, height: 100 },
			{ width: 400, height: 200 },
			0,
			10
		);
		expect(view.k).toBeCloseTo(2);
		expect(view.x + 200 * view.k).toBeCloseTo(200);
		expect(view.y + 100 * view.k).toBeCloseTo(100);
	});

	it('is limited by the width when the rect is wide', () => {
		const view = fitRect(
			{ x: 0, y: 0, width: 400, height: 10 },
			{ width: 200, height: 200 },
			0,
			10
		);
		expect(view.k).toBeCloseTo(0.5);
	});

	it('is limited by the height when the rect is tall', () => {
		const view = fitRect(
			{ x: 0, y: 0, width: 10, height: 400 },
			{ width: 200, height: 200 },
			0,
			10
		);
		expect(view.k).toBeCloseTo(0.5);
	});

	it('keeps a margin of world units around the rect', () => {
		const view = fitRect(
			{ x: 0, y: 0, width: 80, height: 80 },
			{ width: 120, height: 120 },
			20,
			10
		);
		expect(view.k).toBeCloseTo(1);
	});

	it('stops at maxK for a small rect', () => {
		const view = fitRect(
			{ x: 0, y: 0, width: 10, height: 10 },
			{ width: 1000, height: 1000 },
			0,
			4.4
		);
		expect(view.k).toBe(4.4);
	});

	it('stays finite for a viewport with no size', () => {
		const view = fitRect({ x: 0, y: 0, width: 10, height: 10 }, { width: 0, height: 0 }, 5, 4.4);
		expect(Number.isFinite(view.x)).toBe(true);
		expect(Number.isFinite(view.y)).toBe(true);
		expect(view.k).toBeGreaterThan(0);
	});
});

describe('the moved math', () => {
	const viewport = { width: 400, height: 200 };

	it('fits a world with its margin, centered', () => {
		const view = fitView({ width: 1000, height: 400 }, viewport, 0);
		expect(view.k).toBeCloseTo(0.4);
		expect(view.x).toBeCloseTo(0);
		expect(view.y).toBeCloseTo(20);
	});

	it('samples the frames from the first view to the last', () => {
		const from = { x: 0, y: 0, k: 1 };
		const to = { x: -100, y: -50, k: 2 };
		const frames = flyFrames(from, to, viewport, 4);
		expect(frames).toHaveLength(5);
		expect(frames[0]).toEqual(from);
		expect(frames[4]).toEqual(to);
	});

	it('writes a view as a translate and a scale', () => {
		expect(transformOf({ x: 1, y: 2, k: 3 })).toBe('translate(1px, 2px) scale(3)');
	});

	it('tells the fit scale from another one, and a measured viewport from none', () => {
		expect(isAtFit({ x: 0, y: 0, k: 0.5 }, 0.5)).toBe(true);
		expect(isAtFit({ x: 0, y: 0, k: 0.6 }, 0.5)).toBe(false);
		expect(isMeasured(viewport)).toBe(true);
		expect(isMeasured({ width: 0, height: 10 })).toBe(false);
	});
});

describe('clamp', () => {
	it('limits a value below, inside and above its range', () => {
		expect(clamp(-1, 0, 10)).toBe(0);
		expect(clamp(5, 0, 10)).toBe(5);
		expect(clamp(11, 0, 10)).toBe(10);
	});
});
