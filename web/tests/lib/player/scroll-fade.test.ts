// web/tests/lib/player/scroll-fade.test.ts
//
// Tests for the player photo's scroll fade.
//
// Tested:
// - fadeProgress: 0 at or below the start, 0.5 halfway, clamped to 1, 0 for a zero height
// - scrollFade: inline opacity and transform after a scroll and a frame, one frame per burst
//   of scroll events, nothing under reduced motion or without requestAnimationFrame, destroy
//   removes the listener and cancels the pending frame
// - parseCubicBezier: valid strings, null for anything else or an x outside [0, 1]
// - cubicBezierAt: edges, linear curve, ease-out above the diagonal, clamping
// - mobileFadeProgress: 0 while the top is at or below the viewport top, 1 once the bottom reaches
//   the bar's bottom, eased midpoint, linear without a curve, the 390px half-on-screen bound,
//   no bar, a photo no taller than the bar, zero height
// - scrollFade on mobile: opacity only, 1 until the top leaves the viewport, 0 at the shared bar's
//   bottom, follows a re-registered bar, full height without a bar, no lookup by class name,
//   reduced motion, switching layout at runtime
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
	cubicBezierAt,
	fadeProgress,
	mobileFadeProgress,
	parseCubicBezier,
	scrollFade
} from '../../../src/lib/player/scroll-fade';
import { stickyBar } from '../../../src/lib/scroll/scrolled-past.svelte';

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

describe('parseCubicBezier', () => {
	it('parses valid strings', () => {
		expect(parseCubicBezier('cubic-bezier(0, 0, 0.58, 1)')).toEqual([0, 0, 0.58, 1]);
		expect(parseCubicBezier('cubic-bezier(.2,.7,.1,1)')).toEqual([0.2, 0.7, 0.1, 1]);
	});

	it('returns null for anything else', () => {
		expect(parseCubicBezier('')).toBeNull();
		expect(parseCubicBezier('ease-out')).toBeNull();
		expect(parseCubicBezier('cubic-bezier(1, 2)')).toBeNull();
		expect(parseCubicBezier('cubic-bezier(1.5, 0, 0.5, 1)')).toBeNull();
	});
});

describe('cubicBezierAt', () => {
	const easeOut: [number, number, number, number] = [0, 0, 0.58, 1];

	it('is 0 at 0 and 1 at 1', () => {
		expect(cubicBezierAt(easeOut, 0)).toBe(0);
		expect(cubicBezierAt(easeOut, 1)).toBe(1);
	});

	it('follows the diagonal for the linear curve', () => {
		expect(cubicBezierAt([0, 0, 1, 1], 0.3)).toBeCloseTo(0.3, 4);
	});

	it('is above the diagonal for ease-out', () => {
		const y = cubicBezierAt(easeOut, 0.5);
		expect(y).toBeGreaterThan(0.5);
		expect(y).toBeLessThan(1);
	});

	it('clamps x outside [0, 1]', () => {
		expect(cubicBezierAt(easeOut, -1)).toBe(0);
		expect(cubicBezierAt(easeOut, 2)).toBe(1);
	});
});

describe('mobileFadeProgress', () => {
	const ease: [number, number, number, number] = [0, 0, 0.58, 1];

	it('is 0 at the viewport top and below it', () => {
		expect(mobileFadeProgress(0, 400, 77, ease)).toBe(0);
		expect(mobileFadeProgress(250, 400, 77, ease)).toBe(0);
	});

	it('is above 0 just past the viewport top', () => {
		expect(mobileFadeProgress(-1, 400, 77, ease)).toBeGreaterThan(0);
	});

	it("is 1 when the bottom reaches the bar's bottom and past it", () => {
		expect(mobileFadeProgress(77 - 400, 400, 77, ease)).toBe(1);
		expect(mobileFadeProgress(-5000, 400, 77, ease)).toBe(1);
	});

	it('eases the midpoint above the linear value', () => {
		const p = mobileFadeProgress(-(400 - 77) / 2, 400, 77, ease);
		expect(p).toBeCloseTo(cubicBezierAt(ease, 0.5), 6);
		expect(p).toBeGreaterThan(0.5);
	});

	it('is linear without a curve', () => {
		expect(mobileFadeProgress(-(400 - 77) / 2, 400, 77, null)).toBeCloseTo(0.5);
	});

	it('keeps the opacity at 0.5 or more with half the photo on screen at 390px', () => {
		const p = mobileFadeProgress(77 - 135, 270, 77, ease);
		expect(1 - p).toBeGreaterThanOrEqual(0.5);
	});

	it('runs over the full height without a bar', () => {
		expect(mobileFadeProgress(-400, 400, 0, ease)).toBe(1);
		expect(mobileFadeProgress(-200, 400, 0, null)).toBeCloseTo(0.5);
	});

	it('is 0 for a zero or negative height', () => {
		expect(mobileFadeProgress(-100, 0, 77, ease)).toBe(0);
		expect(mobileFadeProgress(-100, -5, 77, ease)).toBe(0);
	});

	it('is gone as soon as the top leaves a photo no taller than the bar', () => {
		expect(mobileFadeProgress(0, 60, 77, ease)).toBe(0);
		expect(mobileFadeProgress(-1, 60, 77, ease)).toBe(1);
	});
});

describe('scrollFade on mobile', () => {
	const ease: [number, number, number, number] = [0, 0, 0.58, 1];
	let frames: Map<number, FrameRequestCallback>;
	let nextId: number;
	let reduced: boolean;
	let node: HTMLElement;
	let top: number;
	let cleanups: (() => void)[];
	let decoy: HTMLElement | null;

	// jsdom has no IntersectionObserver or ResizeObserver, so the bar is measured once on register.
	const registerBar = (height: number) => {
		const bar = document.createElement('nav');
		bar.style.top = '0px';
		bar.getBoundingClientRect = () => ({ height }) as DOMRect;
		cleanups.push(stickyBar.observe(document.createElement('div'), bar));
	};

	beforeEach(() => {
		frames = new Map();
		nextId = 1;
		reduced = false;
		top = 100;
		cleanups = [];
		decoy = null;
		vi.stubGlobal('ResizeObserver', undefined);
		vi.stubGlobal('IntersectionObserver', undefined);
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
		node.style.setProperty('--player-photo-fade-ease-mobile', 'cubic-bezier(0, 0, 0.58, 1)');
		document.body.appendChild(node);
		node.getBoundingClientRect = () => ({ top: top + shift(), height: 400 }) as DOMRect;
		registerBar(77);
	});

	afterEach(() => {
		vi.restoreAllMocks();
		vi.unstubAllGlobals();
		for (const cleanup of cleanups) cleanup();
		decoy?.remove();
		node.remove();
	});

	const shift = () => parseFloat(node.style.transform.replace('translateY(', '')) || 0;

	const runFrames = () => {
		for (const [id, callback] of [...frames]) {
			frames.delete(id);
			callback(0);
		}
	};

	const scrollTo = (value: number) => {
		top = value;
		window.dispatchEvent(new Event('scroll'));
		runFrames();
	};

	it('writes opacity and never a transform', () => {
		const action = scrollFade(node, 'mobile');
		runFrames();
		scrollTo(-100);
		expect(Number(node.style.opacity)).toBeCloseTo(1 - mobileFadeProgress(-100, 400, 77, ease));
		expect(node.style.transform).toBe('');
		action?.destroy();
	});

	it("stays at 1 while the photo's top is at or below the viewport top", () => {
		const action = scrollFade(node, 'mobile');
		scrollTo(0);
		expect(Number(node.style.opacity)).toBe(1);
		scrollTo(-1);
		expect(Number(node.style.opacity)).toBeLessThan(1);
		action?.destroy();
	});

	it("reaches 0 when the photo's bottom reaches the bar's bottom", () => {
		const action = scrollFade(node, 'mobile');
		scrollTo(77 - 400);
		expect(Number(node.style.opacity)).toBe(0);
		action?.destroy();
	});

	it("follows the shared bar's bottom edge", () => {
		for (const cleanup of cleanups.splice(0)) cleanup();
		registerBar(120);
		const action = scrollFade(node, 'mobile');
		scrollTo(120 - 400);
		expect(Number(node.style.opacity)).toBe(0);
		scrollTo(121 - 400);
		expect(Number(node.style.opacity)).toBeGreaterThan(0);
		action?.destroy();
	});

	it('runs over the full height without a registered bar', () => {
		for (const cleanup of cleanups.splice(0)) cleanup();
		const action = scrollFade(node, 'mobile');
		scrollTo(-399);
		expect(Number(node.style.opacity)).toBeGreaterThan(0);
		scrollTo(-400);
		expect(Number(node.style.opacity)).toBe(0);
		action?.destroy();
	});

	it('does no lookup by class name', () => {
		decoy = document.createElement('nav');
		decoy.className = 'section-tabs';
		decoy.getBoundingClientRect = () => ({ height: 300 }) as DOMRect;
		document.body.appendChild(decoy);
		const one = vi.spyOn(document, 'querySelector');
		const all = vi.spyOn(document, 'querySelectorAll');
		const action = scrollFade(node, 'mobile');
		runFrames();
		scrollTo(-50);
		scrollTo(-200);
		scrollTo(77 - 400);
		expect(Number(node.style.opacity)).toBe(0);
		expect(one).not.toHaveBeenCalled();
		expect(all).not.toHaveBeenCalled();
		action?.destroy();
	});

	it('does nothing under reduced motion', () => {
		reduced = true;
		expect(scrollFade(node, 'mobile')).toBeUndefined();
		scrollTo(-100);
		expect(node.style.opacity).toBe('');
		expect(node.style.transform).toBe('');
	});

	it('clears the transform when the layout switches and drifts again on desktop', () => {
		top = 90 - 0.5 * FADE_SPAN * 400;
		const action = scrollFade(node, 'desktop');
		runFrames();
		expect(node.style.transform).toBe('translateY(30px)');
		action?.update('mobile');
		runFrames();
		expect(node.style.transform).toBe('');
		action?.update('desktop');
		runFrames();
		expect(node.style.transform).toBe('translateY(30px)');
		action?.destroy();
	});
});
