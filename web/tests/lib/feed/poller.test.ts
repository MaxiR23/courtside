// web/tests/lib/feed/poller.test.ts
//
// Tests for the games feed polling state.
//
// Tested:
// - pollInterval: 30 s while any game is live, 60 s otherwise and with no feed yet (ADR 0007)
// - Loads at once on start; polls every 30 s while a game is live and slows to 60 s after
// - Keeps the last feed and sets failed when a later load fails; records when a feed was received
// - Pauses while the tab is hidden and loads at once when it is visible again
// - Never runs two loads at once; stops and drops a pending result after cleanup
//
// What is covered:
// - The reactive module without mounting; fake timers, an injected clock and a fake document
// - No real network: the load function is a mock
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/poller.test.ts
//
// SEE: web/src/lib/feed/poller.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GameStatus, GamesFeed } from '../../../src/lib/contract/games';
import {
	GamesFeedPoller,
	IDLE_POLL_MS,
	LIVE_POLL_MS,
	pollInterval
} from '../../../src/lib/feed/poller.svelte';

const feedWith = (...statuses: GameStatus[]): GamesFeed =>
	({
		generatedAt: '2026-10-04T12:00:00Z',
		days: [{ date: '2026-10-04', games: statuses.map((status) => ({ status })) }]
	}) as unknown as GamesFeed;

function fakePage(state: 'visible' | 'hidden' = 'visible') {
	const listeners = new Set<() => void>();
	return {
		visibilityState: state as DocumentVisibilityState,
		addEventListener: vi.fn((_type: string, listener: () => void) => void listeners.add(listener)),
		removeEventListener: vi.fn(
			(_type: string, listener: () => void) => void listeners.delete(listener)
		),
		set(next: DocumentVisibilityState) {
			this.visibilityState = next;
			for (const listener of [...listeners]) listener();
		},
		count: () => listeners.size
	};
}

function poller(load: () => Promise<GamesFeed>, page = fakePage(), now?: () => Date) {
	return new GamesFeedPoller(load, {
		now,
		visibility: () => page as unknown as Document
	});
}

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('pollInterval', () => {
	it('is 30 s when any game is live', () => {
		expect(pollInterval(feedWith('final', 'live'))).toBe(LIVE_POLL_MS);
		expect(LIVE_POLL_MS).toBe(30_000);
	});

	it('is 60 s when no game is live', () => {
		expect(pollInterval(feedWith('scheduled', 'final', 'delayed'))).toBe(IDLE_POLL_MS);
		expect(IDLE_POLL_MS).toBe(60_000);
	});

	it('is 60 s with no feed yet', () => {
		expect(pollInterval(null)).toBe(IDLE_POLL_MS);
	});
});

describe('GamesFeedPoller', () => {
	it('loads at once on start', async () => {
		const feed = feedWith('scheduled');
		const load = vi.fn().mockResolvedValue(feed);
		const p = poller(load);
		p.start();
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(0);
		expect(p.feed).toBe(feed);
		expect(p.failed).toBe(false);
	});

	it('records when the feed was received', async () => {
		const received = new Date(2026, 9, 4, 12, 5);
		const p = poller(vi.fn().mockResolvedValue(feedWith('final')), fakePage(), () => received);
		expect(p.receivedAt).toBeNull();
		p.start();
		await vi.advanceTimersByTimeAsync(0);
		expect(p.receivedAt).toBe(received);
	});

	it('polls every 30 s while a game is live', async () => {
		const load = vi.fn().mockResolvedValue(feedWith('live'));
		poller(load).start();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(29_999);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(load).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(load).toHaveBeenCalledTimes(3);
	});

	it('slows to 60 s when the live game goes final', async () => {
		const load = vi
			.fn()
			.mockResolvedValueOnce(feedWith('live'))
			.mockResolvedValue(feedWith('final'));
		poller(load).start();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(load).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(59_999);
		expect(load).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(1);
		expect(load).toHaveBeenCalledTimes(3);
	});

	it('keeps the last feed and sets failed when a later load fails', async () => {
		const feed = feedWith('scheduled');
		const load = vi.fn().mockResolvedValueOnce(feed).mockRejectedValue(new Error('down'));
		const p = poller(load);
		p.start();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
		expect(load).toHaveBeenCalledTimes(2);
		expect(p.feed).toBe(feed);
		expect(p.failed).toBe(true);
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
		expect(load).toHaveBeenCalledTimes(3);
	});

	it('sets failed with no feed when the first load fails, and recovers on the next', async () => {
		const feed = feedWith('scheduled');
		const load = vi.fn().mockRejectedValueOnce(new Error('down')).mockResolvedValue(feed);
		const p = poller(load);
		p.start();
		await vi.advanceTimersByTimeAsync(0);
		expect(p.feed).toBeNull();
		expect(p.failed).toBe(true);
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
		expect(p.feed).toBe(feed);
		expect(p.failed).toBe(false);
	});

	it('pauses while the tab is hidden', async () => {
		const page = fakePage();
		const load = vi.fn().mockResolvedValue(feedWith('live'));
		poller(load, page).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('hidden');
		await vi.advanceTimersByTimeAsync(5 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('does not poll when the tab is hidden after a load', async () => {
		const page = fakePage('hidden');
		const load = vi.fn().mockResolvedValue(feedWith('live'));
		poller(load, page).start();
		await vi.advanceTimersByTimeAsync(5 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('loads at once when the tab becomes visible again', async () => {
		const page = fakePage();
		const load = vi.fn().mockResolvedValue(feedWith('live'));
		poller(load, page).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('hidden');
		await vi.advanceTimersByTimeAsync(5 * 60_000);
		page.set('visible');
		expect(load).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(LIVE_POLL_MS);
		expect(load).toHaveBeenCalledTimes(3);
	});

	it('never runs two loads at once', async () => {
		const page = fakePage();
		let finish: (feed: GamesFeed) => void = () => {};
		const load = vi.fn(
			() =>
				new Promise<GamesFeed>((resolve) => {
					finish = resolve;
				})
		);
		poller(load, page).start();
		page.set('hidden');
		page.set('visible');
		expect(load).toHaveBeenCalledTimes(1);
		finish(feedWith('final'));
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('stops polling and drops a pending result after cleanup', async () => {
		const page = fakePage();
		let finish: (feed: GamesFeed) => void = () => {};
		const load = vi.fn(
			() =>
				new Promise<GamesFeed>((resolve) => {
					finish = resolve;
				})
		);
		const p = poller(load, page);
		const stop = p.start();
		expect(page.count()).toBe(1);
		stop();
		expect(page.count()).toBe(0);
		finish(feedWith('live'));
		await vi.advanceTimersByTimeAsync(5 * 60_000);
		expect(p.feed).toBeNull();
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('stops the timer after cleanup', async () => {
		const load = vi.fn().mockResolvedValue(feedWith('live'));
		const stop = poller(load).start();
		await vi.advanceTimersByTimeAsync(0);
		stop();
		await vi.advanceTimersByTimeAsync(5 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
	});
});
