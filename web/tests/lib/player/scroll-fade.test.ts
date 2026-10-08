// web/tests/lib/player/scroll-fade.test.ts
//
// Tests for the player photo's scroll fade.
//
// Tested:
// - fadeProgress: 0 at or below the start, 0.5 halfway, clamped to 1, 0 for a zero height
// - scrollFade: inline opacity and transform after a scroll and a frame, one frame per burst
//   of scroll events, nothing under reduced motion or without requestAnimationFrame, destroy
//   removes the listener and cancels the pending frame
//
// What is covered:
// - Pure logic and the action's wiring with stubbed frame, media and rect; no layout, no clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/player/scroll-fade.test.ts
//
// SEE: web/src/lib/player/scroll-fade.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
	FADE_SPAN,
	FADE_START_PX,
	fadeProgress,
	scrollFade
} from '../../../src/lib/player/scroll-fade';

describe('fadeProgress', () => {
	it('is 0 at or below the start', () => {
		expect(fadeProgress(FADE_START_PX, 400)).toBe(0);
		expect(fadeProgress(300, 400)).toBe(0);
	});

	it('is 0.5 halfway through the span', () => {
		const height = 400;
		expect(fadeProgress(FADE_START_PX - 0.5 * FADE_SPAN * height, height)).toBeCloseTo(0.5);
	});

	it('clamps to 1 past the span', () => {
		expect(fadeProgress(-5000, 400)).toBe(1);
	});

	it('is 0 for a zero or negative height', () => {
		expect(fadeProgress(-100, 0)).toBe(0);
		expect(fadeProgress(-100, -5)).toBe(0);
	});
});

describe('scrollFade', () => {
	let frames: Map<number, FrameRequestCallback>;
	let nextId: number;
	let reduced: boolean;
	let node: HTMLElement;
	let top: number;

	beforeEach(() => {
		frames = new Map();
		nextId = 1;
		reduced = false;
		top = 90 - 0.5 * FADE_SPAN * 400;
		vi.stubGlobal(
			'requestAnimationFrame',
			vi.fn((callback: FrameRequestCallback) => {
				const id = nextId++;
				frames.set(id, callback);
				return id;
			})
		);
		vi.stubGlobal(
			'cancelAnimationFrame',
			vi.fn((id: number) => void frames.delete(id))
		);
		vi.stubGlobal(
			'matchMedia',
			vi.fn(() => ({ matches: reduced }))
		);
		node = document.createElement('div');
		node.style.setProperty('--player-photo-drift', '60px');
		// Like a browser, the rect includes the translateY already written on the node.
		node.getBoundingClientRect = () => ({ top: top + shift(), height: 400 }) as DOMRect;
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	const shift = () => parseFloat(node.style.transform.replace('translateY(', '')) || 0;

	const runFrames = () => {
		for (const [id, callback] of [...frames]) {
			frames.delete(id);
			callback(0);
		}
	};

	it('sets opacity and transform after a scroll and its frame', () => {
		const action = scrollFade(node);
		runFrames();
		window.dispatchEvent(new Event('scroll'));
		runFrames();
		expect(Number(node.style.opacity)).toBeCloseTo(0.5);
		expect(node.style.transform).toBe('translateY(30px)');
		action?.destroy();
	});

	it('measures the layout top, not the top moved by its own transform', () => {
		const layoutTop = (p: number) => FADE_START_PX - p * FADE_SPAN * 400;
		const action = scrollFade(node);
		for (const [p, opacity, transform] of [
			[1, 0, 'translateY(60px)'],
			[0.5, 0.5, 'translateY(30px)']
		] as const) {
			top = layoutTop(p);
			for (let frame = 0; frame < 3; frame++) {
				window.dispatchEvent(new Event('scroll'));
				runFrames();
				expect(Number(node.style.opacity)).toBeCloseTo(opacity);
				expect(node.style.transform).toBe(transform);
			}
		}
		action?.destroy();
	});

	it('asks for one frame per burst of scroll events', () => {
		const action = scrollFade(node);
		runFrames();
		const request = vi.mocked(requestAnimationFrame);
		request.mockClear();
		window.dispatchEvent(new Event('scroll'));
		window.dispatchEvent(new Event('scroll'));
		window.dispatchEvent(new Event('scroll'));
		expect(request).toHaveBeenCalledTimes(1);
		runFrames();
		window.dispatchEvent(new Event('scroll'));
		expect(request).toHaveBeenCalledTimes(2);
		action?.destroy();
	});

	it('does nothing under reduced motion', () => {
		reduced = true;
		expect(scrollFade(node)).toBeUndefined();
		window.dispatchEvent(new Event('scroll'));
		runFrames();
		expect(node.style.opacity).toBe('');
		expect(node.style.transform).toBe('');
	});

	it('does nothing without requestAnimationFrame', () => {
		vi.stubGlobal('requestAnimationFrame', undefined);
		expect(scrollFade(node)).toBeUndefined();
		window.dispatchEvent(new Event('scroll'));
		expect(node.style.opacity).toBe('');
	});

	it('removes the listener and cancels the pending frame on destroy', () => {
		const action = scrollFade(node);
		runFrames();
		window.dispatchEvent(new Event('scroll'));
		expect(frames.size).toBe(1);
		action?.destroy();
		expect(frames.size).toBe(0);
		expect(cancelAnimationFrame).toHaveBeenCalled();
		const request = vi.mocked(requestAnimationFrame);
		request.mockClear();
		window.dispatchEvent(new Event('scroll'));
		expect(request).not.toHaveBeenCalled();
	});
});
