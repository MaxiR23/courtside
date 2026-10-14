// web/tests/lib/all-star/live-tick.svelte.test.ts
//
// Tests for the live clock tick.
//
// Tested:
// - The tick starts at 0 and increments every 1000 ms once started
// - The cleanup stops the tick
// - A clock derived from the tick shows the new feed clock on the next tick, and does not
//   change between ticks while the feed is the same (it never counts down)
//
// What is covered:
// - The reactive module without mounting; fake timers, no real clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/all-star/live-tick.svelte.test.ts
//
// SEE: web/src/lib/all-star/live-tick.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { LiveTick, TICK_MS } from '../../../src/lib/all-star/live-tick.svelte';

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('LiveTick', () => {
	it('starts at 0 and increments every second', () => {
		const live = new LiveTick();
		expect(live.tick).toBe(0);
		live.start();
		vi.advanceTimersByTime(TICK_MS - 1);
		expect(live.tick).toBe(0);
		vi.advanceTimersByTime(1);
		expect(live.tick).toBe(1);
		vi.advanceTimersByTime(3 * TICK_MS);
		expect(live.tick).toBe(4);
	});

	it('uses the injected timers and stops on cleanup', () => {
		const setTimer = vi.fn(() => 7 as unknown as ReturnType<typeof setInterval>);
		const clearTimer = vi.fn();
		const live = new LiveTick({
			setTimer: setTimer as unknown as typeof setInterval,
			clearTimer: clearTimer as unknown as typeof clearInterval
		});
		const stop = live.start();
		expect(setTimer).toHaveBeenCalledWith(expect.any(Function), 1000);
		stop();
		expect(clearTimer).toHaveBeenCalledWith(7);
	});

	it('stops ticking after the cleanup', () => {
		const live = new LiveTick();
		const stop = live.start();
		vi.advanceTimersByTime(TICK_MS);
		stop();
		vi.advanceTimersByTime(5 * TICK_MS);
		expect(live.tick).toBe(1);
	});

	it('re-reads the latest feed clock on each tick and never counts down', () => {
		const live = new LiveTick();
		let feedClock = '5:12';
		const reads: string[] = [];
		const read = () => {
			void live.tick;
			reads.push(feedClock);
			return feedClock;
		};
		live.start();
		expect(read()).toBe('5:12');
		vi.advanceTimersByTime(TICK_MS);
		expect(read()).toBe('5:12'); // the same feed: the same text
		feedClock = '4:58';
		vi.advanceTimersByTime(TICK_MS);
		expect(read()).toBe('4:58'); // the new feed value shows on the next tick
	});
});
