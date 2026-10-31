// web/tests/lib/scroll/scrolled-past.test.ts
//
// Tests for the element watch state.
//
// Tested:
// - Starts not passed; observes the plain viewport, no root margin
// - Passed once the element is above the viewport; not passed again when it comes back
// - An element below the viewport is not passed; the latest entry of a batch wins
// - Does nothing without IntersectionObserver; disconnects on cleanup
// - The sticky bar state: stuck follows the sentinel, bottom edge is the sticky top plus the height,
//   each bar has its own state, the page's bar is the latest still registered, cleanup removes
//   only its own entry, one shared instance
//
// What is covered:
// - Happy path, edge cases (below the viewport, resize, two bars) and the missing-API cases
//
// Run with: cd web && pnpm exec vitest run tests/lib/scroll/scrolled-past.test.ts
//
// SEE: web/src/lib/scroll/scrolled-past.svelte.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	ScrolledPastWatch,
	StickyBarState,
	stickyBar
} from '../../../src/lib/scroll/scrolled-past.svelte';

type Entry = { isIntersecting: boolean; boundingClientRect: { top: number } };
type Callback = (entries: Entry[]) => void;

function stubObserver() {
	const state = {
		callbacks: [] as Callback[],
		options: [] as (IntersectionObserverInit | undefined)[],
		disconnect: vi.fn(),
		observe: vi.fn()
	};
	class FakeObserver {
		constructor(callback: Callback, options?: IntersectionObserverInit) {
			state.callbacks.push(callback);
			state.options.push(options);
		}
		observe = state.observe;
		disconnect = state.disconnect;
	}
	vi.stubGlobal('IntersectionObserver', FakeObserver);
	return state;
}

const above: Entry = { isIntersecting: false, boundingClientRect: { top: -10 } };
const visible: Entry = { isIntersecting: true, boundingClientRect: { top: 200 } };
const below: Entry = { isIntersecting: false, boundingClientRect: { top: 900 } };

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('ScrolledPastWatch', () => {
	it('starts with the element not passed', () => {
		expect(new ScrolledPastWatch().passed).toBe(false);
	});

	it('observes against the plain viewport, with no root margin', () => {
		const observer = stubObserver();
		const node = document.createElement('div');
		new ScrolledPastWatch().observe(node);
		expect(observer.options[0]).toBeUndefined();
		expect(observer.observe).toHaveBeenCalledWith(node);
	});

	it('reports passed once the element is above the viewport', () => {
		const observer = stubObserver();
		const watch = new ScrolledPastWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([above]);
		expect(watch.passed).toBe(true);
	});

	it('reports passed once the bottom edge has left the top of the viewport', () => {
		const observer = stubObserver();
		const watch = new ScrolledPastWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([{ isIntersecting: false, boundingClientRect: { top: -1 } }]);
		expect(watch.passed).toBe(true);
	});

	it('reports not passed again when the element comes back into view', () => {
		const observer = stubObserver();
		const watch = new ScrolledPastWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([above]);
		observer.callbacks[0]([visible]);
		expect(watch.passed).toBe(false);
	});

	it('does not count an element below the viewport as passed', () => {
		const observer = stubObserver();
		const watch = new ScrolledPastWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([below]);
		expect(watch.passed).toBe(false);
	});

	it('uses the latest entry of a batch', () => {
		const observer = stubObserver();
		const watch = new ScrolledPastWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([above, visible]);
		expect(watch.passed).toBe(false);
	});

	it('stays not passed without IntersectionObserver', () => {
		vi.stubGlobal('IntersectionObserver', undefined);
		const watch = new ScrolledPastWatch();
		const stop = watch.observe(document.createElement('div'));
		expect(watch.passed).toBe(false);
		expect(() => stop()).not.toThrow();
	});

	it('disconnects on cleanup', () => {
		const observer = stubObserver();
		const stop = new ScrolledPastWatch().observe(document.createElement('div'));
		stop();
		expect(observer.disconnect).toHaveBeenCalled();
	});
});

function stubResizeObserver() {
	const state = {
		callbacks: [] as (() => void)[],
		observe: vi.fn(),
		disconnect: vi.fn()
	};
	class FakeResizeObserver {
		constructor(callback: () => void) {
			state.callbacks.push(callback);
		}
		observe = state.observe;
		disconnect = state.disconnect;
	}
	vi.stubGlobal('ResizeObserver', FakeResizeObserver);
	return state;
}

function barOf(height: number, top?: string) {
	const bar = document.createElement('nav');
	if (top) bar.style.top = top;
	const box = { height };
	bar.getBoundingClientRect = () => box as DOMRect;
	return { bar, box };
}

describe('StickyBarState', () => {
	it('starts not stuck, with the bottom edge at 0', () => {
		const state = new StickyBarState();
		expect(state.stuck).toBe(false);
		expect(state.bottom).toBe(0);
	});

	it('observes the sentinel, not the bar, against the plain viewport', () => {
		const observer = stubObserver();
		stubResizeObserver();
		const sentinel = document.createElement('div');
		new StickyBarState().observe(sentinel, barOf(49).bar);
		expect(observer.observe).toHaveBeenCalledTimes(1);
		expect(observer.observe).toHaveBeenCalledWith(sentinel);
		expect(observer.options[0]).toBeUndefined();
	});

	it('reports stuck once the sentinel has left the top of the viewport', () => {
		const observer = stubObserver();
		stubResizeObserver();
		const state = new StickyBarState();
		state.observe(document.createElement('div'), barOf(49).bar);
		observer.callbacks[0]([above]);
		expect(state.stuck).toBe(true);
	});

	it('reports not stuck while the sentinel is in view, and while it is below the viewport', () => {
		const observer = stubObserver();
		stubResizeObserver();
		const state = new StickyBarState();
		state.observe(document.createElement('div'), barOf(49).bar);
		observer.callbacks[0]([above]);
		observer.callbacks[0]([visible]);
		expect(state.stuck).toBe(false);
		observer.callbacks[0]([below]);
		expect(state.stuck).toBe(false);
	});

	it('measures the bottom edge as the sticky top plus the bar height', () => {
		stubObserver();
		stubResizeObserver();
		const state = new StickyBarState();
		state.observe(document.createElement('div'), barOf(49, '12px').bar);
		expect(state.bottom).toBe(61);
		const plain = new StickyBarState();
		plain.observe(document.createElement('div'), barOf(49).bar);
		expect(plain.bottom).toBe(49);
	});

	it('updates the bottom edge when the bar resizes', () => {
		stubObserver();
		const resize = stubResizeObserver();
		const { bar, box } = barOf(49, '12px');
		const state = new StickyBarState();
		state.observe(document.createElement('div'), bar);
		expect(resize.observe).toHaveBeenCalledWith(bar);
		box.height = 90;
		resize.callbacks[0]();
		expect(state.bottom).toBe(102);
	});

	it('measures once and does not throw without ResizeObserver', () => {
		stubObserver();
		vi.stubGlobal('ResizeObserver', undefined);
		const state = new StickyBarState();
		let stop = () => {};
		expect(() => {
			stop = state.observe(document.createElement('div'), barOf(49).bar);
		}).not.toThrow();
		expect(state.bottom).toBe(49);
		expect(() => stop()).not.toThrow();
	});

	it('stays not stuck without IntersectionObserver', () => {
		vi.stubGlobal('IntersectionObserver', undefined);
		stubResizeObserver();
		const state = new StickyBarState();
		const stop = state.observe(document.createElement('div'), barOf(49).bar);
		expect(state.stuck).toBe(false);
		expect(() => stop()).not.toThrow();
	});

	it('gives each registered bar its own stuck state and bottom edge', () => {
		const observer = stubObserver();
		const resize = stubResizeObserver();
		const state = new StickyBarState();
		const first = barOf(49).bar;
		const second = barOf(60, '10px').bar;
		state.observe(document.createElement('div'), first);
		state.observe(document.createElement('div'), second);
		expect(observer.disconnect).not.toHaveBeenCalled();
		expect(resize.disconnect).not.toHaveBeenCalled();
		observer.callbacks[1]([above]);
		expect(state.stuckOf(first)).toBe(false);
		expect(state.stuckOf(second)).toBe(true);
		observer.callbacks[0]([above]);
		observer.callbacks[1]([visible]);
		expect(state.stuckOf(first)).toBe(true);
		expect(state.stuckOf(second)).toBe(false);
		expect(state.bottomOf(first)).toBe(49);
		expect(state.bottomOf(second)).toBe(70);
	});

	it('makes stuck and bottom follow the latest registered bar, falling back when it is cleaned up', () => {
		const observer = stubObserver();
		stubResizeObserver();
		const state = new StickyBarState();
		const stopFirst = state.observe(document.createElement('div'), barOf(49).bar);
		const stopSecond = state.observe(document.createElement('div'), barOf(60).bar);
		observer.callbacks[0]([above]);
		expect(state.stuck).toBe(false);
		expect(state.bottom).toBe(60);
		stopSecond();
		expect(state.stuck).toBe(true);
		expect(state.bottom).toBe(49);
		stopFirst();
		expect(state.stuck).toBe(false);
		expect(state.bottom).toBe(0);
	});

	it('removes only its own entry on cleanup', () => {
		const observer = stubObserver();
		stubResizeObserver();
		const state = new StickyBarState();
		const { bar } = barOf(49);
		const staleStop = state.observe(document.createElement('div'), bar);
		state.observe(document.createElement('div'), bar);
		observer.callbacks[1]([above]);
		staleStop();
		expect(state.stuckOf(bar)).toBe(true);
		expect(state.bottomOf(bar)).toBe(49);
		expect(state.stuck).toBe(true);
	});

	it('reports false and 0 for null and for a bar that is not registered', () => {
		stubObserver();
		stubResizeObserver();
		const state = new StickyBarState();
		state.observe(document.createElement('div'), barOf(49).bar);
		expect(state.stuckOf(null)).toBe(false);
		expect(state.bottomOf(null)).toBe(0);
		expect(state.stuckOf(barOf(10).bar)).toBe(false);
		expect(state.bottomOf(barOf(10).bar)).toBe(0);
	});

	it('disconnects both observers and resets the state on cleanup', () => {
		const observer = stubObserver();
		const resize = stubResizeObserver();
		const state = new StickyBarState();
		const stop = state.observe(document.createElement('div'), barOf(49).bar);
		observer.callbacks[0]([above]);
		stop();
		expect(observer.disconnect).toHaveBeenCalled();
		expect(resize.disconnect).toHaveBeenCalled();
		expect(state.stuck).toBe(false);
		expect(state.bottom).toBe(0);
	});

	it('exports one shared instance', () => {
		expect(stickyBar).toBeInstanceOf(StickyBarState);
	});
});
