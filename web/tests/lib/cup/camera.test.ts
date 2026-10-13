// web/tests/lib/cup/camera.test.ts
//
// Tests for the camera math of the Cup bracket.
//
// Tested:
// - The fit centers the whole world, for a wide and a tall viewport, and stays finite for a viewport with no size
// - Zoom around a point keeps the world point under it and clamps from 0.75 times the fit to 4
// - Pan keeps the viewport center inside the world
// - The wheel: ctrl zooms, a mouse wheel zooms, a trackpad pans, a vertical scroll at fit goes to the page
// - Level 1 below 0.36 and level 2 from 0.36, and the level targets
// - The drag starts past 6px
// - The fly: endpoints, monotonic scale, geometric mean at the midpoint, frame count, easing
// - The transform text
// - The constants match the --bracket-* tokens
//
// What is covered:
// - Pure logic: happy path, edge cases and the zero-size error case
//
// Run with: cd web && pnpm exec vitest run tests/lib/cup/camera.test.ts
//
// SEE: web/src/lib/cup/camera.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
	cubicInOut,
	DRAG_THRESHOLD_PX,
	dragStarted,
	fitView,
	FLY_MS,
	flyFrames,
	isAtFit,
	isMeasured,
	LEVEL_THRESHOLD,
	levelOf,
	levelTarget,
	panBy,
	transformOf,
	wheelFactor,
	wheelIntent,
	ZOOM_MAX,
	ZOOM_MIN_OF_FIT,
	zoomAt,
	zoomBounds
} from '../../../src/lib/cup/camera';

const WORLD = { width: 6300, height: 1320 };
const VIEWPORT = { width: 1200, height: 500 };
const MARGIN = 160;
const tokensCss = readFileSync(join(process.cwd(), 'src/lib/styles/tokens.css'), 'utf8');
const tokenValue = (name: string): string => {
	const match = tokensCss.match(new RegExp(`${name}:\\s*([^;]+);`));
	if (!match) throw new Error(`${name} is missing`);
	return match[1].trim();
};

const wheel = (deltaX: number, deltaY: number, deltaMode = 0, ctrlKey = false) => ({
	deltaX,
	deltaY,
	deltaMode,
	ctrlKey
});

describe('fitView', () => {
	it('fits a wide viewport by width and centers vertically', () => {
		const view = fitView(WORLD, VIEWPORT, MARGIN);
		expect(view.k).toBeCloseTo(1200 / 6620, 10);
		expect(view.x + WORLD.width * view.k).toBeCloseTo(1200 - view.x, 6);
		expect(view.y).toBeGreaterThan(0);
		expect(view.y + WORLD.height * view.k).toBeCloseTo(500 - view.y, 6);
	});

	it('fits a tall viewport by height and centers horizontally', () => {
		const tall = { width: 800, height: 900 };
		const world = { width: 2400, height: 3600 };
		const view = fitView(world, tall, MARGIN);
		expect(view.k).toBeCloseTo(900 / 3920, 10);
		expect(view.x).toBeCloseTo((800 - 2400 * view.k) / 2, 10);
		expect(view.y).toBeCloseTo((900 - 3600 * view.k) / 2, 10);
	});

	it('stays finite and positive for a viewport with no size', () => {
		const view = fitView(WORLD, { width: 0, height: 0 }, MARGIN);
		expect(Number.isFinite(view.k) && view.k > 0).toBe(true);
		expect(Number.isFinite(view.x) && Number.isFinite(view.y)).toBe(true);
		expect(isMeasured({ width: 0, height: 0 })).toBe(false);
		expect(isMeasured(VIEWPORT)).toBe(true);
	});
});

describe('zoomAt', () => {
	const fit = fitView(WORLD, VIEWPORT, MARGIN);
	const bounds = zoomBounds(fit.k);

	it('bounds the scale from 0.75 times the fit to 4', () => {
		expect(bounds).toEqual({ min: 0.75 * fit.k, max: 4 });
	});

	it('keeps the world point under the cursor', () => {
		const point = { x: 300, y: 200 };
		const before = { x: (point.x - fit.x) / fit.k, y: (point.y - fit.y) / fit.k };
		const next = zoomAt(fit, point, 2, bounds);
		expect(next.k).toBeCloseTo(fit.k * 2, 10);
		expect((point.x - next.x) / next.k).toBeCloseTo(before.x, 6);
		expect((point.y - next.y) / next.k).toBeCloseTo(before.y, 6);
	});

	it('clamps at 0.75 times the fit and at 4', () => {
		expect(zoomAt(fit, { x: 0, y: 0 }, 0.01, bounds).k).toBeCloseTo(bounds.min, 10);
		expect(zoomAt(fit, { x: 0, y: 0 }, 1000, bounds).k).toBe(4);
	});
});

describe('panBy', () => {
	const view = { x: 0, y: 0, k: 1 };

	it('moves by the delta inside the world', () => {
		const moved = panBy({ x: -100, y: -100, k: 1 }, 30, -20, WORLD, VIEWPORT);
		expect(moved).toEqual({ x: -70, y: -120, k: 1 });
	});

	it('keeps the viewport center inside the world', () => {
		const right = panBy(view, 5000, 5000, WORLD, VIEWPORT);
		expect(right.x).toBe(600);
		expect(right.y).toBe(250);
		const left = panBy(view, -99999, -99999, WORLD, VIEWPORT);
		expect(left.x).toBe(600 - 6300);
		expect(left.y).toBe(250 - 1320);
	});
});

describe('isAtFit', () => {
	it('is true within a millionth of the fit scale only', () => {
		expect(isAtFit({ x: 0, y: 0, k: 0.2 }, 0.2)).toBe(true);
		expect(isAtFit({ x: 0, y: 0, k: 0.2 * 1.01 }, 0.2)).toBe(false);
	});
});

describe('wheelIntent', () => {
	it('zooms on ctrl, even at fit', () => {
		expect(wheelIntent(wheel(0, 3, 0, true), true)).toBe('zoom');
	});

	it('leaves a vertical scroll at fit to the page', () => {
		expect(wheelIntent(wheel(0, 120), true)).toBe('page');
		expect(wheelIntent(wheel(4, 10), true)).toBe('page');
	});

	it('zooms for a mouse wheel when not at fit', () => {
		expect(wheelIntent(wheel(0, 120), false)).toBe('zoom');
		expect(wheelIntent(wheel(0, 3, 1), false)).toBe('zoom');
	});

	it('pans for a trackpad when not at fit', () => {
		expect(wheelIntent(wheel(4, 7.5), false)).toBe('pan');
		expect(wheelIntent(wheel(0, 12), false)).toBe('pan');
	});

	it('turns wheel travel into a zoom factor, up zooming in', () => {
		expect(wheelFactor(0, 0)).toBe(1);
		expect(wheelFactor(-100, 0)).toBeGreaterThan(1);
		expect(wheelFactor(100, 0)).toBeLessThan(1);
		expect(wheelFactor(-1, 1)).toBeCloseTo(Math.exp(16 * 0.002), 10);
	});
});

describe('levels', () => {
	it('is level 1 just below 0.36 and level 2 at exactly 0.36', () => {
		expect(levelOf(0.3599)).toBe(1);
		expect(levelOf(0.36)).toBe(2);
		expect(levelOf(4)).toBe(2);
	});

	it('targets the fit for level 1', () => {
		const fit = fitView(WORLD, VIEWPORT, MARGIN);
		expect(levelTarget(1, fit, { x: 5, y: 5, k: 2 }, VIEWPORT)).toBe(fit);
	});

	it('targets the threshold scale around the viewport center for level 2', () => {
		const fit = fitView(WORLD, VIEWPORT, MARGIN);
		const target = levelTarget(2, fit, fit, VIEWPORT);
		expect(target.k).toBe(LEVEL_THRESHOLD);
		expect((600 - target.x) / target.k).toBeCloseTo((600 - fit.x) / fit.k, 6);
		expect((250 - target.y) / target.k).toBeCloseTo((250 - fit.y) / fit.k, 6);
	});

	it('keeps a fit larger than the threshold for level 2', () => {
		const big = { x: 0, y: 0, k: 0.5 };
		expect(levelTarget(2, big, big, VIEWPORT).k).toBe(0.5);
	});
});

describe('dragStarted', () => {
	it('starts past 6px of travel and not at 6', () => {
		expect(dragStarted(6, 0)).toBe(false);
		expect(dragStarted(6.1, 0)).toBe(true);
		expect(dragStarted(4, 4)).toBe(false);
		expect(dragStarted(5, 5)).toBe(true);
	});
});

describe('the fly', () => {
	const from = { x: 100, y: 40, k: 0.2 };
	const to = { x: -1500, y: -300, k: 1.8 };

	it('eases in and out', () => {
		expect(cubicInOut(0)).toBe(0);
		expect(cubicInOut(0.5)).toBe(0.5);
		expect(cubicInOut(1)).toBe(1);
		expect(cubicInOut(0.25)).toBeLessThan(0.25);
		expect(cubicInOut(0.75)).toBeGreaterThan(0.75);
	});

	it('has steps + 1 frames from the start view to the end view', () => {
		const frames = flyFrames(from, to, VIEWPORT, 24);
		expect(frames).toHaveLength(25);
		expect(frames[0]).toEqual(from);
		expect(frames[24]).toEqual(to);
	});

	it('grows the scale monotonically, with the geometric mean at the midpoint', () => {
		const frames = flyFrames(from, to, VIEWPORT, 24);
		for (let i = 1; i < frames.length; i++) {
			expect(frames[i].k).toBeGreaterThanOrEqual(frames[i - 1].k);
		}
		expect(frames[12].k).toBeCloseTo(Math.sqrt(from.k * to.k), 10);
	});

	it('moves the world point at the center linearly in the eased progress', () => {
		const frames = flyFrames(from, to, VIEWPORT, 24);
		const center = (v: { x: number; k: number }) => (600 - v.x) / v.k;
		expect(center(frames[12])).toBeCloseTo((center(from) + center(to)) / 2, 6);
	});
});

describe('transformOf', () => {
	it('writes translate and scale', () => {
		expect(transformOf({ x: 12.5, y: -3, k: 0.25 })).toBe('translate(12.5px, -3px) scale(0.25)');
	});
});

describe('tokens', () => {
	it('mirrors the --bracket-* tokens', () => {
		expect(LEVEL_THRESHOLD).toBe(Number(tokenValue('--bracket-level-threshold')));
		expect(ZOOM_MIN_OF_FIT).toBe(Number(tokenValue('--bracket-zoom-min')));
		expect(ZOOM_MAX).toBe(Number(tokenValue('--bracket-zoom-max')));
		expect(`${DRAG_THRESHOLD_PX}px`).toBe(tokenValue('--bracket-drag-threshold'));
		expect(`${FLY_MS}ms`).toBe(tokenValue('--bracket-fly-duration'));
	});
});
