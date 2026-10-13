// web/tests/lib/cup/camera.svelte.test.ts
//
// Tests for the bracket camera controller.
//
// Tested:
// - Attaching applies the fit transform
// - Ctrl+wheel zooms around the pointer; a vertical wheel at fit is left to the page
// - A drag of 4px moves nothing; a drag of 10px pans and sets suppressClick until the next pointer down
// - Zoom in and out respect the bounds
// - goToLevel(2) sets level 2 and goToLevel(1) returns to the fit
// - A fly plays 25 keyframes over 560ms, and does not animate under reduced motion
// - After every input the layer's style holds only the transform
// - shift(dx, dy) moves the layer by -dx, -dy after a level change, and does nothing on a non-interactive camera
// - A camera that is not interactive (mobile) ignores wheel, pointer and buttons
//
// What is covered:
// - The controller with a plain element as the layer, no component
//
// Run with: cd web && pnpm exec vitest run tests/lib/cup/camera.svelte.test.ts
//
// SEE: web/src/lib/cup/camera.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { BracketCamera } from '../../../src/lib/cup/camera.svelte';

const WORLD = { width: 6300, height: 1320 };
const VIEWPORT = { width: 1200, height: 500 };
const RECT = { left: 0, top: 0 };

let layer: HTMLDivElement;

function wheel(init: WheelEventInit & { clientX?: number; clientY?: number }): WheelEvent {
	return new WheelEvent('wheel', { cancelable: true, ...init });
}

function pointer(x: number, y: number, button = 0) {
	return { button, clientX: x, clientY: y, pointerId: 1, currentTarget: null };
}

function camera(interactive = true): BracketCamera {
	const cam = new BracketCamera();
	cam.attach(layer, WORLD, VIEWPORT, interactive);
	return cam;
}

const styleIsOnlyTransform = () =>
	expect(layer.getAttribute('style')).toMatch(/^transform: [^;]+;?$/);

beforeEach(() => {
	layer = document.createElement('div');
});

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('attach', () => {
	it('applies the fit transform and starts at level 1 at fit', () => {
		const cam = camera();
		expect(layer.style.transform).toMatch(/^translate\(.+\) scale\(0\.18/);
		expect(cam.level).toBe(1);
		expect(cam.atFit).toBe(true);
		styleIsOnlyTransform();
	});

	it('changes nothing for a viewport with no size', () => {
		const cam = new BracketCamera();
		cam.attach(layer, WORLD, { width: 0, height: 0 }, true);
		expect(layer.style.transform).toBe('');
		cam.resize(VIEWPORT);
		expect(layer.style.transform).not.toBe('');
	});

	it('goes back to the fit, at once, on resize', () => {
		const cam = camera();
		cam.wheel(wheel({ deltaY: -200, ctrlKey: true, clientX: 100, clientY: 100 }), RECT);
		expect(cam.atFit).toBe(false);
		cam.resize({ width: 800, height: 400 });
		expect(cam.atFit).toBe(true);
		styleIsOnlyTransform();
	});
});

describe('wheel', () => {
	it('zooms around the pointer on ctrl+wheel and prevents the default', () => {
		const cam = camera();
		const before = layer.style.transform;
		const event = wheel({ deltaY: -200, ctrlKey: true, clientX: 300, clientY: 200 });
		cam.wheel(event, RECT);
		expect(event.defaultPrevented).toBe(true);
		expect(layer.style.transform).not.toBe(before);
		expect(cam.atFit).toBe(false);
		styleIsOnlyTransform();
	});

	it('leaves a vertical wheel at fit to the page', () => {
		const cam = camera();
		const before = layer.style.transform;
		const event = wheel({ deltaY: 120 });
		cam.wheel(event, RECT);
		expect(event.defaultPrevented).toBe(false);
		expect(layer.style.transform).toBe(before);
	});

	it('pans on a trackpad scroll when zoomed', () => {
		const cam = camera();
		cam.wheel(wheel({ deltaY: -400, ctrlKey: true, clientX: 600, clientY: 250 }), RECT);
		const zoomed = layer.style.transform;
		const event = wheel({ deltaX: 4, deltaY: 7.5 });
		cam.wheel(event, RECT);
		expect(event.defaultPrevented).toBe(true);
		expect(layer.style.transform).not.toBe(zoomed);
		styleIsOnlyTransform();
	});

	it('ignores the wheel when not interactive', () => {
		const cam = camera(false);
		const before = layer.style.transform;
		const event = wheel({ deltaY: -200, ctrlKey: true });
		cam.wheel(event, RECT);
		expect(event.defaultPrevented).toBe(false);
		expect(layer.style.transform).toBe(before);
	});
});

describe('drag', () => {
	it('does not move on 4px and keeps clicks', () => {
		const cam = camera();
		const before = layer.style.transform;
		cam.pointerDown(pointer(100, 100));
		cam.pointerMove(pointer(104, 100));
		cam.pointerUp(pointer(104, 100));
		expect(layer.style.transform).toBe(before);
		expect(cam.suppressClick).toBe(false);
	});

	it('pans on 10px, swallows the click and clears on the next pointer down', () => {
		const cam = camera();
		cam.wheel(wheel({ deltaY: -400, ctrlKey: true, clientX: 600, clientY: 250 }), RECT);
		const before = layer.style.transform;
		cam.pointerDown(pointer(100, 100));
		cam.pointerMove(pointer(110, 100));
		cam.pointerMove(pointer(120, 100));
		cam.pointerUp(pointer(120, 100));
		expect(layer.style.transform).not.toBe(before);
		expect(cam.suppressClick).toBe(true);
		cam.pointerDown(pointer(5, 5));
		expect(cam.suppressClick).toBe(false);
		styleIsOnlyTransform();
	});

	it('ignores the pointer when not interactive', () => {
		const cam = camera(false);
		const before = layer.style.transform;
		cam.pointerDown(pointer(100, 100));
		cam.pointerMove(pointer(200, 100));
		expect(layer.style.transform).toBe(before);
		expect(cam.suppressClick).toBe(false);
	});
});

describe('buttons and levels', () => {
	it('zooms in and out within the bounds', () => {
		const cam = camera();
		for (let i = 0; i < 20; i++) cam.zoomIn();
		expect(layer.style.transform).toMatch(/scale\(4\)$/);
		for (let i = 0; i < 40; i++) cam.zoomOut();
		const min = /scale\(([\d.e-]+)\)$/.exec(layer.style.transform);
		const fitK = 1200 / 6620;
		expect(Number(min?.[1])).toBeCloseTo(0.75 * fitK, 6);
		styleIsOnlyTransform();
	});

	it('goes to level 2 and back to the fit', () => {
		const cam = camera();
		cam.goToLevel(2);
		expect(cam.level).toBe(2);
		expect(layer.style.transform).toMatch(/scale\(0\.36\)$/);
		cam.goToLevel(1);
		expect(cam.level).toBe(1);
		expect(cam.atFit).toBe(true);
	});

	it('fits again from any zoom', () => {
		const cam = camera();
		cam.zoomIn();
		expect(cam.atFit).toBe(false);
		cam.fit();
		expect(cam.atFit).toBe(true);
	});

	it('ignores the buttons when not interactive', () => {
		const cam = camera(false);
		const before = layer.style.transform;
		cam.zoomIn();
		cam.goToLevel(2);
		expect(layer.style.transform).toBe(before);
		expect(cam.level).toBe(1);
	});
});

describe('the fly', () => {
	function animating() {
		const cancel = vi.fn();
		const animate = vi.fn(() => ({ cancel }) as unknown as Animation);
		layer.animate = animate as unknown as HTMLElement['animate'];
		return { animate, cancel };
	}

	it('plays 25 keyframes over 560ms with linear easing, the target already in the style', () => {
		const { animate } = animating();
		const cam = camera();
		cam.zoomIn();
		expect(animate).toHaveBeenCalledTimes(1);
		const [frames, options] = animate.mock.calls[0] as unknown as [
			{ transform: string }[],
			unknown
		];
		expect(frames).toHaveLength(25);
		expect(options).toEqual({ duration: 560, easing: 'linear' });
		expect(frames[24].transform).toBe(layer.style.transform);
		styleIsOnlyTransform();
	});

	it('updates the level when the animation finishes', () => {
		const { animate } = animating();
		const cam = camera();
		cam.goToLevel(2);
		expect(cam.level).toBe(1);
		const animation = animate.mock.results[0].value as { onfinish: () => void };
		animation.onfinish();
		expect(cam.level).toBe(2);
	});

	it('cancels a running fly when another starts', () => {
		const { cancel } = animating();
		const cam = camera();
		cam.zoomIn();
		cam.zoomIn();
		expect(cancel).toHaveBeenCalledTimes(1);
	});

	it('does not animate under reduced motion and lands at once', () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)',
			addEventListener: () => {},
			removeEventListener: () => {}
		}));
		const { animate } = animating();
		const cam = camera();
		cam.goToLevel(2);
		expect(animate).not.toHaveBeenCalled();
		expect(layer.style.transform).toMatch(/scale\(0\.36\)$/);
		expect(cam.level).toBe(2);
	});

	it('shift follows a native scroll of the viewport by moving the layer the other way', () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)',
			addEventListener: () => {},
			removeEventListener: () => {}
		}));
		const cam = camera();
		cam.goToLevel(2);
		const x = (): number => Number(/translate\((-?[\d.]+)px/.exec(layer.style.transform)?.[1]);
		const before = x();
		cam.shift(100, 0);
		expect(x()).toBeCloseTo(before - 100, 5);
	});

	it('shift does nothing on a camera that is not interactive', () => {
		const cam = camera(false);
		const before = layer.style.transform;
		cam.shift(100, 0);
		expect(layer.style.transform).toBe(before);
	});

	it('cancels the running fly on destroy', () => {
		const { cancel } = animating();
		const cam = camera();
		cam.zoomIn();
		cam.destroy();
		expect(cancel).toHaveBeenCalledTimes(1);
	});
});
