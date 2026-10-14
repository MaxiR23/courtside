// web/tests/lib/playoffs/count-up.svelte.test.ts
//
// Tests for the hero count-up controller.
//
// Tested:
// - The count starts at zero before it starts
// - The final values are forced when the timeout ends
// - Under reduced motion the final values show at once and no timer is set
// - The cleanup clears the timer
//
// What is covered:
// - The reactive module without mounting; fake timers
// - Animation frames are driven by hand; no real frame or frame count is asserted (docs/testing.md)
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/count-up.svelte.test.ts
//
// SEE: web/src/lib/playoffs/count-up.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { CountUp } from '../../../src/lib/playoffs/count-up.svelte';

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

// Frames are driven by hand: no real animation frame runs.
function frames() {
	const queue: FrameRequestCallback[] = [];
	return {
		requestFrame: ((cb: FrameRequestCallback) =>
			queue.push(cb)) as unknown as typeof requestAnimationFrame,
		cancelFrame: (() => queue.splice(0)) as unknown as typeof cancelAnimationFrame,
		run: () => queue.splice(0).forEach((cb) => cb(0)),
		pending: () => queue.length
	};
}

describe('CountUp', () => {
	it('starts at zero before it starts', () => {
		const count = new CountUp({ durationMs: 1400, timeoutMs: 1600, reduced: false, ...frames() });
		expect(count.progress).toBe(0);
		expect(count.text('16-6')).toBe('0-0');
	});

	it('forces the final values when the timeout ends', () => {
		const driver = frames();
		let clock = 0;
		const count = new CountUp({
			durationMs: 1400,
			timeoutMs: 1600,
			reduced: false,
			...driver,
			now: () => clock
		});
		count.start();
		clock = 700;
		driver.run();
		expect(count.progress).toBeGreaterThan(0);
		expect(count.progress).toBeLessThan(1);
		expect(count.text('16-6')).not.toBe('16-6');
		vi.advanceTimersByTime(1599);
		expect(count.progress).toBeLessThan(1);
		vi.advanceTimersByTime(1);
		expect(count.progress).toBe(1);
		expect(count.text('16-6')).toBe('16-6');
	});

	it('shows the final values at once under reduced motion and sets no timer', () => {
		const setTimer = vi.fn() as unknown as typeof setTimeout;
		const count = new CountUp({ durationMs: 1400, timeoutMs: 1600, reduced: true, setTimer });
		count.start();
		expect(count.text('+142')).toBe('+142');
		expect(setTimer).not.toHaveBeenCalled();
		expect(vi.getTimerCount()).toBe(0);
	});

	it('clears the timer on cleanup', () => {
		const clearTimer = vi.fn(clearTimeout) as unknown as typeof clearTimeout;
		const driver = frames();
		const count = new CountUp({
			durationMs: 1400,
			timeoutMs: 1600,
			reduced: false,
			clearTimer,
			...driver
		});
		const stop = count.start();
		expect(driver.pending()).toBe(1);
		stop();
		expect(clearTimer).toHaveBeenCalledTimes(1);
		expect(driver.pending()).toBe(0);
		vi.advanceTimersByTime(2000);
		expect(count.progress).toBe(0);
	});
});
