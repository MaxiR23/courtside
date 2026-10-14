// web/tests/lib/playoffs/bracket-camera.svelte.test.ts
//
// Tests for the playoffs bracket camera controller.
//
// Tested:
// - Attaching applies the fit at level 1; a viewport with no size changes nothing
// - select sets level 2 and the selected series; the scale is at most 4.4 and equals fitRect of the series rect
// - overview goes back to the fit and keeps the selected series
// - seriesLevel with nothing selected goes to east-r1-1
// - next and prev cycle and wrap
// - A fly plays 2 keyframes over 800ms with the --ease curve, and does not animate under reduced motion
// - After every input the layer's style holds only the transform
// - shift pans the applied transform by (-dx, -dy) within the panBy clamp and keeps level and selected
// - resize re-applies the current level at once
// - The constants match the --playoffs-camera-* tokens
//
// What is covered:
// - The controller with a plain element as the layer, no component
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/bracket-camera.svelte.test.ts
//
// SEE: web/src/lib/playoffs/bracket-camera.svelte.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { fitRect, fitView, panBy } from '../../../src/lib/bracket/camera';
import {
	CAMERA_EASING,
	CAMERA_MS,
	SeriesCamera
} from '../../../src/lib/playoffs/bracket-camera.svelte';
import {
	FIT_MARGIN,
	SERIES_MARGIN,
	SERIES_ZOOM_MAX,
	seriesRect,
	WORLD
} from '../../../src/lib/playoffs/bracket-layout';

const VIEWPORT = { width: 1200, height: 560 };

let layer: HTMLDivElement;

function camera(games = {}): SeriesCamera {
	const cam = new SeriesCamera();
	cam.attach(layer, VIEWPORT, games);
	return cam;
}

const styleIsOnlyTransform = () =>
	expect(layer.getAttribute('style')).toMatch(/^transform: [^;]+;?$/);

const transformOfView = (v: { x: number; y: number; k: number }) =>
	`translate(${v.x}px, ${v.y}px) scale(${v.k})`;

function animating() {
	const cancel = vi.fn();
	const animate = vi.fn(() => ({ cancel }) as unknown as Animation);
	layer.animate = animate as unknown as HTMLElement['animate'];
	return { animate, cancel };
}

const reducedMotion = () =>
	vi.stubGlobal('matchMedia', (query: string) => ({
		matches: query === '(prefers-reduced-motion: reduce)'
	}));

beforeEach(() => {
	layer = document.createElement('div');
});

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('attach', () => {
	it('applies the fit at level 1 with nothing selected', () => {
		const cam = camera();
		expect(layer.style.transform).toBe(transformOfView(fitView(WORLD, VIEWPORT, FIT_MARGIN)));
		expect(cam.level).toBe(1);
		expect(cam.selected).toBeNull();
		styleIsOnlyTransform();
	});

	it('changes nothing for a viewport with no size', () => {
		const cam = new SeriesCamera();
		cam.attach(layer, { width: 0, height: 0 }, {});
		expect(layer.style.transform).toBe('');
		cam.resize(VIEWPORT);
		expect(layer.style.transform).not.toBe('');
	});
});

describe('levels', () => {
	it('selects a series at level 2, fitted with its games and at most 4.4x', () => {
		const cam = camera({ 'east-r1-1': 5 });
		cam.select('east-r1-1');
		expect(cam.level).toBe(2);
		expect(cam.selected).toBe('east-r1-1');
		const expected = fitRect(seriesRect('east-r1-1', 5), VIEWPORT, SERIES_MARGIN, SERIES_ZOOM_MAX);
		expect(layer.style.transform).toBe(transformOfView(expected));
		expect(expected.k).toBeLessThanOrEqual(4.4);
		styleIsOnlyTransform();
	});

	it('sizes level 2 with the games set later', () => {
		const cam = camera();
		cam.setGames({ finals: 7 });
		cam.select('finals');
		const expected = fitRect(seriesRect('finals', 7), VIEWPORT, SERIES_MARGIN, SERIES_ZOOM_MAX);
		expect(layer.style.transform).toBe(transformOfView(expected));
	});

	it('goes back to the fit from level 2 and keeps the selected series', () => {
		const cam = camera();
		cam.select('east-r3');
		cam.overview();
		expect(cam.level).toBe(1);
		expect(cam.selected).toBe('east-r3');
		expect(layer.style.transform).toBe(transformOfView(fitView(WORLD, VIEWPORT, FIT_MARGIN)));
	});

	it('goes to the first series for level 2 with nothing selected, and keeps the selection', () => {
		const cam = camera();
		cam.seriesLevel();
		expect(cam.selected).toBe('east-r1-1');
		expect(cam.level).toBe(2);
		cam.select('west-r2-1');
		cam.overview();
		cam.seriesLevel();
		expect(cam.selected).toBe('west-r2-1');
	});

	it('cycles with next and prev and wraps around', () => {
		const cam = camera();
		cam.next();
		expect(cam.selected).toBe('east-r1-1');
		cam.next();
		expect(cam.selected).toBe('east-r1-2');
		cam.prev();
		cam.prev();
		expect(cam.selected).toBe('west-r1-4');
		cam.next();
		expect(cam.selected).toBe('east-r1-1');
	});

	it('starts prev from the last series', () => {
		const cam = camera();
		cam.prev();
		expect(cam.selected).toBe('west-r1-4');
		expect(cam.level).toBe(2);
	});

	it('ignores a move before it is attached or measured', () => {
		const cam = new SeriesCamera();
		cam.select('finals');
		expect(layer.style.transform).toBe('');
		expect(cam.selected).toBe('finals');
	});
});

describe('resize', () => {
	it('re-applies the current level at once', () => {
		const cam = camera();
		cam.select('finals');
		const next = { width: 600, height: 400 };
		cam.resize(next);
		const expected = fitRect(seriesRect('finals', 0), next, SERIES_MARGIN, SERIES_ZOOM_MAX);
		expect(layer.style.transform).toBe(transformOfView(expected));
		styleIsOnlyTransform();
	});
});

describe('the fly', () => {
	it('plays 2 keyframes over 800ms with the --ease curve, the target already in the style', () => {
		const { animate } = animating();
		const cam = camera();
		cam.select('east-r1-1');
		expect(animate).toHaveBeenCalledTimes(1);
		const [frames, options] = animate.mock.calls[0] as unknown as [
			{ transform: string }[],
			unknown
		];
		expect(frames).toHaveLength(2);
		expect(frames[1].transform).toBe(layer.style.transform);
		expect(options).toEqual({ duration: 800, easing: 'cubic-bezier(0.2, 0.7, 0.1, 1)' });
		styleIsOnlyTransform();
	});

	it('cancels a running fly when another starts', () => {
		const { cancel } = animating();
		const cam = camera();
		cam.next();
		cam.next();
		expect(cancel).toHaveBeenCalledTimes(1);
	});

	it('does not animate under reduced motion and lands at once', () => {
		reducedMotion();
		const { animate } = animating();
		const cam = camera();
		cam.select('finals');
		expect(animate).not.toHaveBeenCalled();
		expect(layer.style.transform).not.toBe(transformOfView(fitView(WORLD, VIEWPORT, FIT_MARGIN)));
		styleIsOnlyTransform();
	});

	it('cancels the fly on destroy', () => {
		const { cancel } = animating();
		const cam = camera();
		cam.next();
		cam.destroy();
		expect(cancel).toHaveBeenCalledTimes(1);
	});
});

describe('tokens', () => {
	const tokensCss = readFileSync(join(process.cwd(), 'src/lib/styles/tokens.css'), 'utf8');

	it('mirrors the camera duration and easing tokens', () => {
		expect(tokensCss).toMatch(/--playoffs-camera-duration:\s*0\.8s;/);
		expect(CAMERA_MS).toBe(800);
		expect(tokensCss).toMatch(/--playoffs-camera-easing:\s*var\(--ease\);/);
		expect(tokensCss).toContain(`--ease: ${CAMERA_EASING};`);
	});
});

describe('shift', () => {
	it('pans the view by (-dx, -dy) and keeps the level and the selection', () => {
		const cam = camera({ 'east-r1-1': 5 });
		cam.select('east-r1-1');
		const from = fitRect(seriesRect('east-r1-1', 5), VIEWPORT, SERIES_MARGIN, SERIES_ZOOM_MAX);
		cam.shift(40, 10);
		expect(layer.style.transform).toBe(
			transformOfView({ ...from, x: from.x - 40, y: from.y - 10 })
		);
		expect(cam.level).toBe(2);
		expect(cam.selected).toBe('east-r1-1');
		styleIsOnlyTransform();
	});

	it('stays inside the panBy clamp', () => {
		const cam = camera();
		cam.shift(-1e7, -1e7);
		const fit = fitView(WORLD, VIEWPORT, FIT_MARGIN);
		expect(layer.style.transform).toBe(transformOfView(panBy(fit, 1e7, 1e7, WORLD, VIEWPORT)));
	});

	it('does nothing when not attached or not measured', () => {
		const cam = new SeriesCamera();
		cam.shift(10, 10);
		cam.attach(layer, { width: 0, height: 0 }, {});
		cam.shift(10, 10);
		expect(layer.style.transform).toBe('');
	});
});
