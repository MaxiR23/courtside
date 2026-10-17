// web/tests/lib/calendar/sheet.svelte.test.ts
//
// Tests for the calendar sheet's state.
//
// Tested:
// - open loads the season once and shows the selected day's month
// - open clamps a selected day after the season to the last month
// - changeSeason loads that season and shows its first month, or the selected day's month when it is in the season
// - previous and next move one month and do nothing at the ends; canPrevious and canNext are false at the ends
// - A slow first load that answers after a second season's load does not replace it
// - A failing load sets failed and keeps no feed; no loader sets failed
// - No month after today's is offered: canNext is false at today's month, and a selected day or an opening after today clamps to it (ADR 0054)
//
// What is covered:
// - The reactive module without mounting
// - No real network: the loader is a mock
//
// Run with: cd web && pnpm exec vitest run tests/lib/calendar/sheet.svelte.test.ts
//
// SEE: web/src/lib/calendar/sheet.svelte.ts
import { describe, expect, it, vi } from 'vitest';

import { CalendarSheetState } from '../../../src/lib/calendar/sheet.svelte';
import type { CalendarFeed } from '../../../src/lib/contract/calendar';

const feedOf = (season: number, firstDay: string, lastDay: string): CalendarFeed =>
	({
		season,
		firstDay,
		lastDay,
		days: [firstDay, lastDay],
		seasons: []
	}) as unknown as CalendarFeed;

const FEEDS: Record<string, CalendarFeed> = {
	current: feedOf(2027, '2026-10-20', '2027-04-10'),
	'1999': feedOf(1999, '1999-02-05', '1999-05-05'),
	'2027': feedOf(2027, '2026-10-20', '2027-04-10')
};

// A today after every season of the recordings: no month is cut.
const LATER = '2099-12-31';

const loader = () => vi.fn((season: string) => Promise.resolve(FEEDS[season]));

describe('CalendarSheetState', () => {
	it('opens on the selected day month after loading the season once', async () => {
		const load = loader();
		const sheet = new CalendarSheetState(load, LATER);
		await sheet.open('current', '2026-12-12');
		expect(load).toHaveBeenCalledTimes(1);
		expect(load).toHaveBeenCalledWith('current');
		expect(sheet.month).toBe('2026-12');
		expect(sheet.failed).toBe(false);
	});

	it('opens on the last month when the selected day is after the season', async () => {
		const sheet = new CalendarSheetState(loader(), LATER);
		await sheet.open('1999', '2026-10-12');
		expect(sheet.month).toBe('1999-05');
	});

	it('opens on the first month when the selected day is before the season', async () => {
		const sheet = new CalendarSheetState(loader(), LATER);
		await sheet.open('1999', '1990-01-01');
		expect(sheet.month).toBe('1999-02');
	});

	it('shows the first month of another season', async () => {
		const load = loader();
		const sheet = new CalendarSheetState(load, LATER);
		await sheet.open('current', '2026-10-12');
		await sheet.changeSeason('1999', '2026-10-12');
		expect(load).toHaveBeenLastCalledWith('1999');
		expect(sheet.month).toBe('1999-02');
		expect(sheet.feed?.season).toBe(1999);
	});

	it('shows the selected day month when the new season holds it', async () => {
		const sheet = new CalendarSheetState(loader(), LATER);
		await sheet.open('1999', null);
		await sheet.changeSeason('2027', '2027-02-14');
		expect(sheet.month).toBe('2027-02');
	});

	it('moves one month at a time and stops at both ends', async () => {
		const sheet = new CalendarSheetState(loader(), LATER);
		await sheet.open('1999', '1999-02-06');
		expect(sheet.canPrevious).toBe(false);
		expect(sheet.canNext).toBe(true);
		sheet.previous();
		expect(sheet.month).toBe('1999-02');
		sheet.next();
		sheet.next();
		sheet.next();
		expect(sheet.month).toBe('1999-05');
		expect(sheet.canNext).toBe(false);
		expect(sheet.canPrevious).toBe(true);
		sheet.next();
		expect(sheet.month).toBe('1999-05');
		sheet.previous();
		expect(sheet.month).toBe('1999-04');
	});

	it('drops the answer of a slow load that a newer load passed', async () => {
		let release: (feed: CalendarFeed) => void = () => {};
		const slow = new Promise<CalendarFeed>((resolve) => {
			release = resolve;
		});
		const load = vi.fn((season: string) =>
			season === 'current' ? slow : Promise.resolve(FEEDS[season])
		);
		const sheet = new CalendarSheetState(load, LATER);
		const first = sheet.open('current', null);
		await sheet.changeSeason('1999', null);
		release(FEEDS.current);
		await first;
		expect(sheet.feed?.season).toBe(1999);
		expect(sheet.month).toBe('1999-02');
	});

	it('sets failed and keeps no feed when a load fails', async () => {
		const sheet = new CalendarSheetState(
			vi.fn((season: string) =>
				season === '1999' ? Promise.reject(new Error('down')) : Promise.resolve(FEEDS[season])
			),
			LATER
		);
		await sheet.open('current', null);
		expect(sheet.failed).toBe(false);
		await sheet.changeSeason('1999', null);
		expect(sheet.failed).toBe(true);
		expect(sheet.feed).toBeNull();
		expect(sheet.month).toBeNull();
		expect(sheet.months).toEqual([]);
	});

	it('is failed at once with no loader', async () => {
		const sheet = new CalendarSheetState(undefined, LATER);
		await sheet.open('current', null);
		expect(sheet.failed).toBe(true);
		expect(sheet.feed).toBeNull();
	});

	it("stops at today's month: canNext is false there", async () => {
		const sheet = new CalendarSheetState(loader(), '2026-12-15');
		await sheet.open('current', '2026-12-12');
		expect(sheet.months.at(-1)).toBe('2026-12');
		expect(sheet.canNext).toBe(false);
		expect(sheet.canPrevious).toBe(true);
		sheet.next();
		expect(sheet.month).toBe('2026-12');
	});

	it("opens on today's month when no day is selected", async () => {
		const sheet = new CalendarSheetState(loader(), '2026-12-15');
		await sheet.open('current', null);
		expect(sheet.month).toBe('2026-12');
	});

	it('keeps every month of a season that ended before today', async () => {
		const sheet = new CalendarSheetState(loader(), '2026-12-15');
		await sheet.open('1999', null);
		expect(sheet.months.at(-1)).toBe('1999-05');
	});

	it("never offers a month before the season's first when today is before it", async () => {
		const sheet = new CalendarSheetState(loader(), '2026-01-01');
		await sheet.open('current', null);
		expect(sheet.months).toEqual(['2026-10']);
	});
});
