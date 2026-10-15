// web/tests/lib/feed/once.svelte.test.ts
//
// Tests for the one-shot feed loader.
//
// Tested:
// - It loads the feed once and sets it
// - It never loads again, whatever the time
// - A failed load sets failed and the error
// - An answer that arrives after the cleanup is dropped
//
// What is covered:
// - The reactive module without mounting; fake timers
// - No real network: the load function is a mock
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/once.svelte.test.ts
//
// SEE: web/src/lib/feed/once.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FeedOnce } from '../../../src/lib/feed/once.svelte';

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('FeedOnce', () => {
	it('loads the feed once and sets it', async () => {
		const load = vi.fn().mockResolvedValue({ season: '2004-05' });
		const once = new FeedOnce(load);
		expect(once.feed).toBeNull();
		once.start();
		await vi.advanceTimersByTimeAsync(0);
		expect(once.feed).toEqual({ season: '2004-05' });
		expect(once.failed).toBe(false);
		expect(once.error).toBeNull();
	});

	it('never loads again, whatever the time', async () => {
		const load = vi.fn().mockResolvedValue({ season: '2004-05' });
		const once = new FeedOnce(load);
		once.start();
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('sets failed and the error on a failed load', async () => {
		const error = new Error('down');
		const once = new FeedOnce(vi.fn().mockRejectedValue(error));
		once.start();
		await vi.advanceTimersByTimeAsync(0);
		expect(once.feed).toBeNull();
		expect(once.failed).toBe(true);
		expect(once.error).toBe(error);
	});

	it('drops an answer that arrives after the cleanup', async () => {
		let resolve: (value: string) => void = () => {};
		const once = new FeedOnce(
			() =>
				new Promise<string>((done) => {
					resolve = done;
				})
		);
		const stop = once.start();
		stop();
		resolve('late');
		await vi.advanceTimersByTimeAsync(0);
		expect(once.feed).toBeNull();
		expect(once.failed).toBe(false);
	});
});
