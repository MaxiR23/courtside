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
// - mobileFadeProgress: start, end, eased midpoint, linear without a curve, zero height or span
// - scrollFade on mobile: opacity only, starts at the bottom of the stuck tabs, reaches 0 within
//   the span, 0 start without a tab bar, reduced motion, switching layout at runtime
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
	TABS_SELECTOR,
	cubicBezierAt,
	fadeProgress,
	mobileFadeProgress,
	parseCubicBezier,
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

	it('is 0 at or below the start', () => {
		expect(mobileFadeProgress(48, 400, 48, 0.45, ease)).toBe(0);
		expect(mobileFadeProgress(300, 400, 48, 0.45, ease)).toBe(0);
	});

	it('is 1 at the end of the span and past it', () => {
		expect(mobileFadeProgress(48 - 0.45 * 400, 400, 48, 0.45, ease)).toBe(1);
		expect(mobileFadeProgress(-5000, 400, 48, 0.45, ease)).toBe(1);
	});

	it('eases the midpoint above the linear value', () => {
		const p = mobileFadeProgress(48 - 0.5 * 0.45 * 400, 400, 48, 0.45, ease);
		expect(p).toBeCloseTo(cubicBezierAt(ease, 0.5), 6);
		expect(p).toBeGreaterThan(0.5);
	});

	it('is linear without a curve', () => {
		expect(mobileFadeProgress(48 - 0.5 * 0.45 * 400, 400, 48, 0.45, null)).toBeCloseTo(0.5);
	});

	it('is 0 for a zero height or a zero span', () => {
		expect(mobileFadeProgress(-100, 0, 48, 0.45, ease)).toBe(0);
		expect(mobileFadeProgress(-100, 400, 48, 0, ease)).toBe(0);
	});
});

describe('scrollFade on mobile', () => {
	const ease: [number, number, number, number] = [0, 0, 0.58, 1];
	let frames: Map<number, FrameRequestCallback>;
	let nextId: number;
	let reduced: boolean;
	let node: HTMLElement;
	let top: number;
	let tabs: HTMLElement | null;
	let tabsHeight: number;

	beforeEach(() => {
		frames = new Map();
		nextId = 1;
		reduced = false;
		top = 100;
		tabsHeight = 48;
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
		node.style.setProperty('--player-photo-fade-span-mobile', '0.45');
		node.style.setProperty('--player-photo-fade-ease-mobile', 'cubic-bezier(0, 0, 0.58, 1)');
		document.body.appendChild(node);
		node.getBoundingClientRect = () => ({ top: top + shift(), height: 400 }) as DOMRect;
		tabs = document.createElement('nav');
		tabs.className = TABS_SELECTOR.slice(1);
		tabs.style.top = '0px';
		tabs.getBoundingClientRect = () => ({ height: tabsHeight }) as DOMRect;
		document.body.appendChild(tabs);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
		tabs?.remove();
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
		scrollTo(0);
		expect(Number(node.style.opacity)).toBeCloseTo(1 - mobileFadeProgress(0, 400, 48, 0.45, ease));
		expect(node.style.transform).toBe('');
		action?.destroy();
	});

	it('starts at the bottom of the stuck tabs', () => {
		const action = scrollFade(node, 'mobile');
		scrollTo(48);
		expect(Number(node.style.opacity)).toBe(1);
		scrollTo(47);
		expect(Number(node.style.opacity)).toBeLessThan(1);
		tabsHeight = 100;
		scrollTo(90);
		expect(Number(node.style.opacity)).toBeLessThan(1);
		action?.destroy();
	});

	it('reaches 0 within the span', () => {
		const action = scrollFade(node, 'mobile');
		scrollTo(48 - 0.45 * 400);
		expect(Number(node.style.opacity)).toBe(0);
		action?.destroy();
	});

	it('starts at 0 without a tab bar', () => {
		tabs?.remove();
		const action = scrollFade(node, 'mobile');
		scrollTo(10);
		expect(Number(node.style.opacity)).toBe(1);
		scrollTo(-10);
		expect(Number(node.style.opacity)).toBeLessThan(1);
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
