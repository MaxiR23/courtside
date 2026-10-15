// web/tests/lib/day/loader.svelte.test.ts
//
// Tests for the day page's loader.
//
// Tested:
// - It loads the day and then the calendar of the day's season, once each, and makes no further call as time passes
// - A 503 gives unavailable and no calendar request
// - A 404 for a date in the games feed's days calls onWindowDay once and stays loading
// - A 404 for a date outside those days, and a 404 with a failing window load, give unavailable
// - A 404 with no window loader gives unavailable
// - A calendar failure, or no calendar loader, keeps ready and sets calendarFailed
// - A cleanup before the answer leaves the state unchanged
//
// What is covered:
// - The reactive module without mounting; fake timers
// - No real network: the loaders are mocks
//
// Run with: cd web && pnpm exec vitest run tests/lib/day/loader.svelte.test.ts
//
// SEE: web/src/lib/day/loader.svelte.ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { CalendarFeed } from '../../../src/lib/contract/calendar';
import type { DayFeed } from '../../../src/lib/contract/days';
import { DayLoader } from '../../../src/lib/day/loader.svelte';
import { FeedLoadError } from '../../../src/lib/feed/load';

const DAY = { season: 1999, day: { date: '1999-02-06', games: [] } } as unknown as DayFeed;
const CALENDAR = { season: 1999, days: ['1999-02-06'] } as unknown as CalendarFeed;
const notFound = () => Promise.reject(new FeedLoadError('not-found', 'no day'));

beforeEach(() => {
	vi.useFakeTimers();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('DayLoader', () => {
	it('loads the day, then the calendar of its season, once each and never again', async () => {
		const loadDay = vi.fn(() => Promise.resolve(DAY));
		const loadCalendar = vi.fn(() => Promise.resolve(CALENDAR));
		const loader = new DayLoader(loadDay, undefined, loadCalendar, vi.fn());
		loader.start('1999-02-06');
		await vi.advanceTimersByTimeAsync(0);
		expect(loader.kind).toBe('ready');
		expect(loader.feed).toBe(DAY);
		expect(loader.calendar).toBe(CALENDAR);
		expect(loadCalendar).toHaveBeenCalledWith('1999');
		await vi.advanceTimersByTimeAsync(10 * 60_000);
		expect(loadDay).toHaveBeenCalledTimes(1);
		expect(loadCalendar).toHaveBeenCalledTimes(1);
	});

	it('is unavailable on a 503 and asks for no calendar', async () => {
		const loadCalendar = vi.fn(() => Promise.resolve(CALENDAR));
		const loader = new DayLoader(
			() => Promise.reject(new FeedLoadError('status', 'down')),
			undefined,
			loadCalendar,
			vi.fn()
		);
		loader.start('1999-02-06');
		await vi.advanceTimersByTimeAsync(0);
		expect(loader.kind).toBe('unavailable');
		expect(loadCalendar).not.toHaveBeenCalled();
	});

	it('hands a 404 for a day of the games feed to onWindowDay, once', async () => {
		const onWindowDay = vi.fn();
		const loader = new DayLoader(
			notFound,
			() => Promise.resolve(['2026-10-12', '1999-02-06']),
			undefined,
			onWindowDay
		);
		loader.start('1999-02-06');
		await vi.advanceTimersByTimeAsync(0);
		expect(onWindowDay).toHaveBeenCalledTimes(1);
		expect(loader.kind).toBe('loading');
	});

	it('is unavailable on a 404 for a date outside the games feed days', async () => {
		const onWindowDay = vi.fn();
		const loader = new DayLoader(
			notFound,
			() => Promise.resolve(['2026-10-12']),
			undefined,
			onWindowDay
		);
		loader.start('1993-09-30');
		await vi.advanceTimersByTimeAsync(0);
		expect(loader.kind).toBe('unavailable');
		expect(onWindowDay).not.toHaveBeenCalled();
	});

	it('is unavailable on a 404 when the window load fails or there is none', async () => {
		const failing = new DayLoader(
			notFound,
			() => Promise.reject(new FeedLoadError('status', 'down')),
			undefined,
			vi.fn()
		);
		failing.start('1999-02-06');
		const none = new DayLoader(notFound, undefined, undefined, vi.fn());
		none.start('1999-02-06');
		await vi.advanceTimersByTimeAsync(0);
		expect(failing.kind).toBe('unavailable');
		expect(none.kind).toBe('unavailable');
	});

	it('stays ready and sets calendarFailed when the calendar fails or has no loader', async () => {
		const failing = new DayLoader(
			() => Promise.resolve(DAY),
			undefined,
			() => Promise.reject(new FeedLoadError('status', 'down')),
			vi.fn()
		);
		failing.start('1999-02-06');
		const none = new DayLoader(() => Promise.resolve(DAY), undefined, undefined, vi.fn());
		none.start('1999-02-06');
		await vi.advanceTimersByTimeAsync(0);
		for (const loader of [failing, none]) {
			expect(loader.kind).toBe('ready');
			expect(loader.calendarFailed).toBe(true);
			expect(loader.calendar).toBeNull();
		}
	});

	it('drops the answers that arrive after the cleanup', async () => {
		const onWindowDay = vi.fn();
		const loader = new DayLoader(
			() => Promise.resolve(DAY),
			undefined,
			() => Promise.resolve(CALENDAR),
			onWindowDay
		);
		const stop = loader.start('1999-02-06');
		stop();
		await vi.advanceTimersByTimeAsync(0);
		expect(loader.kind).toBe('loading');
		expect(loader.feed).toBeNull();
		expect(loader.calendar).toBeNull();
	});
});
