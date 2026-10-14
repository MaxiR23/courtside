// web/tests/lib/bracket/layer.test.ts
//
// Tests for the camera layer shared by the brackets.
//
// Tested:
// - apply writes only the transform, and writes nothing before attach
// - fly puts the target in the style at once and animates with the flight's frames and options
// - fly calls done on finish and on cancel
// - A second fly cancels the first
// - Under reduced motion fly lands at once, does not animate and calls done
// - detach cancels a running fly; fly with no layer does nothing
//
// What is covered:
// - The layer with a plain element, animate is a mock
//
// Run with: cd web && pnpm exec vitest run tests/lib/bracket/layer.test.ts
//
// SEE: web/src/lib/bracket/layer.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CameraLayer } from '../../../src/lib/bracket/layer';

const TO = { x: 10, y: 20, k: 2 };
const flight = (from: { x: number; y: number; k: number }) => ({
	frames: [from, TO],
	duration: 300,
	easing: 'linear'
});

let layer: HTMLDivElement;

function animating() {
	const cancel = vi.fn();
	const animate = vi.fn(() => ({ cancel }) as unknown as Animation);
	layer.animate = animate as unknown as HTMLElement['animate'];
	return { animate, cancel };
}

beforeEach(() => {
	layer = document.createElement('div');
});

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('apply', () => {
	it('writes only the transform', () => {
		const camera = new CameraLayer();
		camera.attach(layer);
		camera.apply(TO);
		expect(layer.getAttribute('style')).toMatch(/^transform: [^;]+;?$/);
		expect(camera.view).toEqual(TO);
		expect(camera.attached).toBe(true);
	});

	it('changes the view and writes nothing before attach', () => {
		const camera = new CameraLayer();
		camera.apply(TO);
		expect(camera.view).toEqual(TO);
		expect(camera.attached).toBe(false);
		expect(layer.getAttribute('style')).toBeNull();
	});
});

describe('fly', () => {
	it('puts the target in the style at once and animates the frames as transforms', () => {
		const { animate } = animating();
		const camera = new CameraLayer();
		camera.attach(layer);
		camera.fly(TO, flight, () => {});
		expect(layer.style.transform).toBe('translate(10px, 20px) scale(2)');
		const [frames, options] = animate.mock.calls[0] as unknown as [
			{ transform: string }[],
			unknown
		];
		expect(frames).toEqual([
			{ transform: 'translate(0px, 0px) scale(1)' },
			{ transform: 'translate(10px, 20px) scale(2)' }
		]);
		expect(options).toEqual({ duration: 300, easing: 'linear' });
		expect(layer.getAttribute('style')).toMatch(/^transform: [^;]+;?$/);
	});

	it('calls done when the animation finishes and when it is cancelled', () => {
		const { animate } = animating();
		const done = vi.fn();
		const camera = new CameraLayer();
		camera.attach(layer);
		camera.fly(TO, flight, done);
		const animation = animate.mock.results[0].value as {
			onfinish: () => void;
			oncancel: () => void;
		};
		animation.onfinish();
		animation.oncancel();
		expect(done).toHaveBeenCalledTimes(2);
	});

	it('cancels a running fly when another starts', () => {
		const { cancel } = animating();
		const camera = new CameraLayer();
		camera.attach(layer);
		camera.fly(TO, flight, () => {});
		camera.fly({ x: 0, y: 0, k: 1 }, flight, () => {});
		expect(cancel).toHaveBeenCalledTimes(1);
	});

	it('lands at once and calls done under reduced motion, without animating', () => {
		vi.stubGlobal('matchMedia', (query: string) => ({
			matches: query === '(prefers-reduced-motion: reduce)'
		}));
		const { animate } = animating();
		const done = vi.fn();
		const camera = new CameraLayer();
		camera.attach(layer);
		camera.fly(TO, flight, done);
		expect(animate).not.toHaveBeenCalled();
		expect(done).toHaveBeenCalledTimes(1);
		expect(camera.view).toEqual(TO);
	});

	it('does nothing with no layer', () => {
		const done = vi.fn();
		const camera = new CameraLayer();
		camera.fly(TO, flight, done);
		expect(done).not.toHaveBeenCalled();
		expect(camera.view).toEqual({ x: 0, y: 0, k: 1 });
	});
});

describe('detach', () => {
	it('cancels a running fly and forgets the layer', () => {
		const { cancel } = animating();
		const camera = new CameraLayer();
		camera.attach(layer);
		camera.fly(TO, flight, () => {});
		camera.detach();
		expect(cancel).toHaveBeenCalledTimes(1);
		expect(camera.attached).toBe(false);
	});
});
