// web/tests/lib/schedule/entrance.test.ts
//
// Tests for the list entrance state.
//
// Tested:
// - Runs once when the list first scrolls into view; replays on a day change
// - Ignores non-intersecting entries; does nothing without IntersectionObserver
// - Disconnects on cleanup
//
// What is covered:
// - Happy path, edge cases and the missing-API case
//
// Run with: cd web && pnpm exec vitest run tests/lib/schedule/entrance.test.ts
//
// SEE: web/src/lib/schedule/entrance.svelte.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ListEntrance } from '../../../src/lib/schedule/entrance.svelte';

type Callback = (entries: { isIntersecting: boolean }[]) => void;

function stubObserver() {
	const state = { callbacks: [] as Callback[], disconnect: vi.fn(), observe: vi.fn() };
	class FakeObserver {
		constructor(callback: Callback) {
			state.callbacks.push(callback);
		}
		observe = state.observe;
		disconnect = state.disconnect;
	}
	vi.stubGlobal('IntersectionObserver', FakeObserver);
	return state;
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe('ListEntrance', () => {
	it('starts with no entrance run', () => {
		expect(new ListEntrance().run).toBe(0);
	});

	it('runs the entrance once when the list first scrolls into view', () => {
		const observer = stubObserver();
		const entrance = new ListEntrance();
		entrance.observe(document.createElement('div'));
		observer.callbacks[0]([{ isIntersecting: true }]);
		observer.callbacks[0]([{ isIntersecting: true }]);
		expect(entrance.run).toBe(1);
		expect(observer.disconnect).toHaveBeenCalled();
	});

	it('ignores entries that are not intersecting', () => {
		const observer = stubObserver();
		const entrance = new ListEntrance();
		entrance.observe(document.createElement('div'));
		observer.callbacks[0]([{ isIntersecting: false }]);
		expect(entrance.run).toBe(0);
	});

	it('does not observe again once the list has been seen', () => {
		const observer = stubObserver();
		const entrance = new ListEntrance();
		entrance.observe(document.createElement('div'));
		observer.callbacks[0]([{ isIntersecting: true }]);
		entrance.observe(document.createElement('div'));
		expect(observer.observe).toHaveBeenCalledTimes(1);
	});

	it('replays the entrance on a day change', () => {
		const entrance = new ListEntrance();
		entrance.replay();
		entrance.replay();
		expect(entrance.run).toBe(2);
	});

	it('does nothing without IntersectionObserver', () => {
		vi.stubGlobal('IntersectionObserver', undefined);
		const entrance = new ListEntrance();
		const cleanup = entrance.observe(document.createElement('div'));
		expect(() => cleanup()).not.toThrow();
		expect(entrance.run).toBe(0);
	});

	it('disconnects on cleanup', () => {
		const observer = stubObserver();
		const entrance = new ListEntrance();
		entrance.observe(document.createElement('div'))();
		expect(observer.disconnect).toHaveBeenCalled();
	});
});
