// web/tests/lib/game/scoreboard-watch.test.ts
//
// Tests for the scoreboard watch state.
//
// Tested:
// - Starts not passed; observes with a top root margin of the bar height
// - Passed once the scoreboard is above the bar; not passed again when it comes back
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
		options: [] as IntersectionObserverInit[],
		disconnect: vi.fn(),
		observe: vi.fn()
	};
	class FakeObserver {
		constructor(callback: Callback, options: IntersectionObserverInit) {
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

	it('observes with a top root margin of the bar height', () => {
		const observer = stubObserver();
		const node = document.createElement('div');
		new ScoreboardWatch().observe(node, 52);
		expect(observer.options[0].rootMargin).toBe('-52px 0px 0px 0px');
		expect(observer.observe).toHaveBeenCalledWith(node);
	});

	it('reports passed once the scoreboard is above the bar', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'), 52);
		observer.callbacks[0]([above]);
		expect(watch.passed).toBe(true);
	});

	it('reports not passed again when the scoreboard comes back into view', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'), 52);
		observer.callbacks[0]([above]);
		observer.callbacks[0]([visible]);
		expect(watch.passed).toBe(false);
	});

	it('does not count a scoreboard below the viewport as passed', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'), 52);
		observer.callbacks[0]([below]);
		expect(watch.passed).toBe(false);
	});

	it('uses the latest entry of a batch', () => {
		const observer = stubObserver();
		const watch = new ScoreboardWatch();
		watch.observe(document.createElement('div'), 52);
		observer.callbacks[0]([above, visible]);
		expect(watch.passed).toBe(false);
	});

	it('stays not passed without IntersectionObserver', () => {
		vi.stubGlobal('IntersectionObserver', undefined);
		const watch = new ScoreboardWatch();
		const stop = watch.observe(document.createElement('div'), 52);
		expect(watch.passed).toBe(false);
		expect(() => stop()).not.toThrow();
	});

	it('disconnects on cleanup', () => {
		const observer = stubObserver();
		const stop = new ScoreboardWatch().observe(document.createElement('div'), 52);
		stop();
		expect(observer.disconnect).toHaveBeenCalled();
	});
});
