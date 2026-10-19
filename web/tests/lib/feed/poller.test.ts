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
// - gamePollInterval: null once final, 30 s while live, 60 s otherwise and with no feed yet
// - FeedPoller with a null interval stops, and does not restart when the tab is visible again
// - A request that times out fails as network; the poller keeps the feed and polls again
// - FeedPoller with gamePollInterval polls a detail feed; it exposes the error of the last load
// - teamPollInterval: 5 min once a feed is loaded, 60 s while none has; pauses while hidden
// - standingsPollInterval: 5 min once final, 60 s otherwise; pauses while hidden
// - cupPollInterval: 5 min once complete, 60 s otherwise; pauses while hidden
// - cupMatchupPollInterval: 60 s
// - playoffsPollInterval: 5 min once complete, 60 s otherwise
// - allStarPollInterval: 30 s while the state is live, 60 s before, after and with no feed yet
// - playerPollInterval: 30 s while live, 60 s otherwise; slows down when live turns null
//
// What is covered:
// - The reactive module without mounting; fake timers, an injected clock and a fake document
// - No real network: the load function is a mock
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/poller.test.ts
//
// SEE: web/src/lib/feed/poller.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { GameDetailFeed } from '../../../src/lib/contract/game-detail';
import type { GameStatus, GamesFeed } from '../../../src/lib/contract/games';
import type { PlayerFeed } from '../../../src/lib/contract/player';
import type { AllStarFeed } from '../../../src/lib/contract/all-star';
import type { CupFeed } from '../../../src/lib/contract/cup';
import type { PlayoffsFeed } from '../../../src/lib/contract/playoffs';
import type { StandingsFeed } from '../../../src/lib/contract/standings';
import type { TeamFeed } from '../../../src/lib/contract/team';
import { FeedLoadError, loadGameDetailFeed } from '../../../src/lib/feed/load';
import {
	allStarPollInterval,
	cupMatchupPollInterval,
	cupPollInterval,
	FeedPoller,
	GamesFeedPoller,
	gamePollInterval,
	IDLE_POLL_MS,
	LIVE_POLL_MS,
	playerPollInterval,
	playoffsPollInterval,
	SLOW_POLL_MS,
	pollInterval,
	standingsPollInterval,
	teamPollInterval
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
	vi.restoreAllMocks();
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

const detailWith = (status: GameStatus): GameDetailFeed =>
	({ id: '401', status }) as GameDetailFeed;

describe('gamePollInterval', () => {
	it('is 30 s while the game is live and 60 s for every other status and with no feed', () => {
		expect(gamePollInterval(detailWith('live'))).toBe(LIVE_POLL_MS);
		for (const status of ['scheduled', 'delayed', 'postponed', 'canceled'] as const) {
			expect(gamePollInterval(detailWith(status))).toBe(IDLE_POLL_MS);
		}
		expect(gamePollInterval(null)).toBe(IDLE_POLL_MS);
	});

	it('is null once the game is final', () => {
		expect(gamePollInterval(detailWith('final'))).toBeNull();
	});
});

describe('FeedPoller', () => {
	it('polls a live detail every 30 s and stops once a load returns a final game', async () => {
		const load = vi
			.fn()
			.mockResolvedValueOnce(detailWith('live'))
			.mockResolvedValue(detailWith('final'));
		new FeedPoller(load, gamePollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(load).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('makes no second request when the first load is final', async () => {
		const load = vi.fn().mockResolvedValue(detailWith('final'));
		new FeedPoller(load, gamePollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('does not restart after the tab becomes visible again', async () => {
		const page = fakePage();
		const load = vi.fn().mockResolvedValue(detailWith('final'));
		new FeedPoller(load, gamePollInterval, {
			visibility: () => page as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('hidden');
		page.set('visible');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('stops when the final feed loads while the tab is hidden', async () => {
		const page = fakePage('hidden');
		const load = vi.fn().mockResolvedValue(detailWith('final'));
		new FeedPoller(load, gamePollInterval, {
			visibility: () => page as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('visible');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
	});

	it('keeps polling after a failed first load', async () => {
		const load = vi
			.fn()
			.mockRejectedValueOnce(new Error('down'))
			.mockResolvedValue(detailWith('live'));
		new FeedPoller(load, gamePollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('keeps the last feed and polls again when a request times out', async () => {
		const url = 'https://feeds.test/game.json';
		vi.spyOn(AbortSignal, 'timeout').mockImplementation((ms) => {
			const controller = new AbortController();
			setTimeout(
				() => controller.abort(new DOMException('The operation timed out.', 'TimeoutError')),
				ms
			);
			return controller.signal;
		});
		const live = { ...detailWith('live') };
		const fetchMock = vi
			.fn()
			.mockImplementationOnce(() =>
				Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(live) })
			)
			.mockImplementationOnce(
				(_url: string, init: RequestInit) =>
					new Promise((_, reject) => {
						init.signal?.addEventListener('abort', () => reject(init.signal?.reason));
					})
			)
			.mockImplementationOnce(() =>
				Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(live) })
			);
		const guarded = (u: string, init?: RequestInit) => {
			if (u !== url) throw new Error(`unexpected URL ${u}`);
			return fetchMock(u, init);
		};
		const p = new FeedPoller(
			() => loadGameDetailFeed(url, guarded as unknown as typeof fetch),
			gamePollInterval,
			{ visibility: () => fakePage() as unknown as Document }
		);
		p.start();
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(14_999);
		expect(p.failed).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		expect(p.failed).toBe(true);
		expect(p.feed).toEqual(live);
		expect(p.error).toBeInstanceOf(FeedLoadError);
		expect((p.error as FeedLoadError).reason).toBe('network');
		await vi.advanceTimersByTimeAsync(30_000);
		expect(fetchMock).toHaveBeenCalledTimes(3);
	});

	it('exposes the error of the last failed load and clears it on the next success', async () => {
		const failure = new Error('down');
		const load = vi.fn().mockRejectedValueOnce(failure).mockResolvedValue(detailWith('scheduled'));
		const p = new FeedPoller(load, gamePollInterval, {
			visibility: () => fakePage() as unknown as Document
		});
		p.start();
		await vi.advanceTimersByTimeAsync(0);
		expect(p.failed).toBe(true);
		expect(p.error).toBe(failure);
		await vi.advanceTimersByTimeAsync(IDLE_POLL_MS);
		expect(p.failed).toBe(false);
		expect(p.error).toBeNull();
	});
});

describe('teamPollInterval', () => {
	it('is 5 min once a feed is loaded and 60 s while none has loaded', () => {
		expect(teamPollInterval({ code: 'OKC' } as TeamFeed)).toBe(300_000);
		expect(SLOW_POLL_MS).toBe(300_000);
		expect(teamPollInterval(null)).toBe(IDLE_POLL_MS);
	});

	it('polls again after 60 s when the first load failed', async () => {
		const load = vi
			.fn()
			.mockRejectedValueOnce(new Error('down'))
			.mockResolvedValue({ code: 'OKC' });
		new FeedPoller(load, teamPollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(59_999);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('polls again after 5 min and not before', async () => {
		const load = vi.fn().mockResolvedValue({ code: 'OKC' });
		new FeedPoller(load, teamPollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(299_999);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('does not poll while the tab is hidden and loads at once when it is visible again', async () => {
		const page = fakePage();
		const load = vi.fn().mockResolvedValue({ code: 'OKC' });
		new FeedPoller(load, teamPollInterval, {
			visibility: () => page as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('hidden');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(load).toHaveBeenCalledTimes(1);
		page.set('visible');
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(2);
	});
});

describe('playerPollInterval', () => {
	const feed = (live: boolean) => ({ id: 'p-2', live: live ? {} : null }) as unknown as PlayerFeed;

	it('is 30 s with a live game and 60 s with live null or no feed', () => {
		expect(playerPollInterval(feed(true))).toBe(LIVE_POLL_MS);
		expect(playerPollInterval(feed(false))).toBe(IDLE_POLL_MS);
		expect(playerPollInterval(null)).toBe(IDLE_POLL_MS);
	});

	it('polls at 30 s while live and slows to 60 s once a load returns live null', async () => {
		const load = vi
			.fn()
			.mockResolvedValueOnce(feed(true))
			.mockResolvedValueOnce(feed(false))
			.mockResolvedValue(feed(false));
		new FeedPoller(load, playerPollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(load).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(load).toHaveBeenCalledTimes(2);
		await vi.advanceTimersByTimeAsync(30_000);
		expect(load).toHaveBeenCalledTimes(3);
	});

	it('does not poll while the tab is hidden and loads at once when it is visible again', async () => {
		const page = fakePage();
		const load = vi.fn().mockResolvedValue(feed(true));
		new FeedPoller(load, playerPollInterval, {
			visibility: () => page as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('hidden');
		await vi.advanceTimersByTimeAsync(180_000);
		expect(load).toHaveBeenCalledTimes(1);
		page.set('visible');
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(2);
	});
});

describe('standingsPollInterval', () => {
	it('is 5 min once final and 60 s otherwise and with no feed yet', () => {
		expect(standingsPollInterval({ state: 'final' } as StandingsFeed)).toBe(SLOW_POLL_MS);
		expect(standingsPollInterval({ state: 'regular' } as StandingsFeed)).toBe(IDLE_POLL_MS);
		expect(standingsPollInterval(null)).toBe(IDLE_POLL_MS);
	});

	it('polls again after 60 s and not before', async () => {
		const load = vi.fn().mockResolvedValue({ state: 'regular', conferences: [] });
		new FeedPoller(load, standingsPollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(59_999);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('does not poll while the tab is hidden and loads at once when it is visible again', async () => {
		const page = fakePage();
		const load = vi.fn().mockResolvedValue({ state: 'regular', conferences: [] });
		new FeedPoller(load, standingsPollInterval, {
			visibility: () => page as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('hidden');
		await vi.advanceTimersByTimeAsync(180_000);
		expect(load).toHaveBeenCalledTimes(1);
		page.set('visible');
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(2);
	});
});

describe('cupPollInterval', () => {
	it('is 5 min once complete and 60 s for every other stage and with no feed yet', () => {
		expect(cupPollInterval({ stage: 'complete' } as CupFeed)).toBe(SLOW_POLL_MS);
		for (const stage of ['draw', 'group', 'quarterfinals', 'semifinals', 'championship']) {
			expect(cupPollInterval({ stage } as unknown as CupFeed)).toBe(IDLE_POLL_MS);
		}
		expect(cupPollInterval(null)).toBe(IDLE_POLL_MS);
	});

	it('polls again after 60 s and not before', async () => {
		const load = vi.fn().mockResolvedValue({ stage: 'group', stages: [] });
		new FeedPoller(load, cupPollInterval, {
			visibility: () => fakePage() as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(59_999);
		expect(load).toHaveBeenCalledTimes(1);
		await vi.advanceTimersByTimeAsync(1);
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('does not poll while the tab is hidden and loads at once when it is visible again', async () => {
		const page = fakePage();
		const load = vi.fn().mockResolvedValue({ stage: 'group', stages: [] });
		new FeedPoller(load, cupPollInterval, {
			visibility: () => page as unknown as Document
		}).start();
		await vi.advanceTimersByTimeAsync(0);
		page.set('hidden');
		await vi.advanceTimersByTimeAsync(180_000);
		expect(load).toHaveBeenCalledTimes(1);
		page.set('visible');
		await vi.advanceTimersByTimeAsync(0);
		expect(load).toHaveBeenCalledTimes(2);
	});
});

describe('cupMatchupPollInterval', () => {
	it('is 60 s', () => {
		expect(cupMatchupPollInterval()).toBe(IDLE_POLL_MS);
	});
});

describe('playoffsPollInterval', () => {
	it('is 5 min once complete', () => {
		expect(playoffsPollInterval({ state: 'complete' } as PlayoffsFeed)).toBe(SLOW_POLL_MS);
	});

	it('is 60 s in every other state and with no feed yet', () => {
		for (const state of ['picture', 'playin', 'playoffs', 'finals']) {
			expect(playoffsPollInterval({ state } as unknown as PlayoffsFeed)).toBe(IDLE_POLL_MS);
		}
		expect(playoffsPollInterval(null)).toBe(IDLE_POLL_MS);
	});
});

describe('allStarPollInterval', () => {
	const inState = (state: AllStarFeed['state']) => ({ state }) as unknown as AllStarFeed;

	it('is 30 s while the state is live', () => {
		expect(allStarPollInterval(inState('live'))).toBe(LIVE_POLL_MS);
	});

	it('is 60 s before, after and with no feed yet', () => {
		expect(allStarPollInterval(inState('before'))).toBe(IDLE_POLL_MS);
		expect(allStarPollInterval(inState('after'))).toBe(IDLE_POLL_MS);
		expect(allStarPollInterval(null)).toBe(IDLE_POLL_MS);
	});
});
