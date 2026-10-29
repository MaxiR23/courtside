// web/tests/lib/game/scoreboard-watch.test.ts
//
// Tests for the scoreboard watch state.
//
// Tested:
// - Starts not passed; observes the plain viewport, no root margin
// - Passed once the scoreboard is above the viewport; not passed again when it comes back
// - A scoreboard below the viewport is not passed; the latest entry of a batch wins
// - Does nothing without IntersectionObserver; disconnects on cleanup
//
// What is covered:
// - Happy path, edge cases and the missing-API case
//
// Run with: cd web && pnpm exec vitest run tests/lib/game/scoreboard-watch.test.ts
//
// SEE: web/src/lib/game/scoreboard-watch.svelte.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ScoreboardWatch } from '../../../src/lib/game/scoreboard-watch.svelte';

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

describe('ScoreboardWatch', () => {
	it('starts with the scoreboard not passed', () => {
		expect(new ScoreboardWatch().passed).toBe(false);
	});

	it('observes against the plain viewport, with no root margin', () => {
		const observer = stubObserver();
		const node = document.createElement('div');
		new ScoreboardWatch().observe(node);
		expect(observer.options[0]).toBeUndefined();
		expect(observer.observe).toHaveBeenCalledWith(node);
	});

	it('reports passed once the scoreboard is above the viewport', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([above]);
		expect(watch.passed).toBe(true);
	});

	it('reports passed once the bottom edge has left the top of the viewport', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([{ isIntersecting: false, boundingClientRect: { top: -1 } }]);
		expect(watch.passed).toBe(true);
	});

	it('reports not passed again when the scoreboard comes back into view', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([above]);
		observer.callbacks[0]([visible]);
		expect(watch.passed).toBe(false);
	});

	it('does not count a scoreboard below the viewport as passed', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([below]);
		expect(watch.passed).toBe(false);
	});

	it('uses the latest entry of a batch', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'));
		observer.callbacks[0]([above, visible]);
		expect(watch.passed).toBe(false);
	});

	it('stays not passed without IntersectionObserver', () => {
		vi.stubGlobal('IntersectionObserver', undefined);
		const watch = new ScoreboardWatch();
		const stop = watch.observe(document.createElement('div'));
		expect(watch.passed).toBe(false);
		expect(() => stop()).not.toThrow();
	});

	it('disconnects on cleanup', () => {
		const observer = stubObserver();
		const stop = new ScoreboardWatch().observe(document.createElement('div'));
		stop();
		expect(observer.disconnect).toHaveBeenCalled();
	});
});
