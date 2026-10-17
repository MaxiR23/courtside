// web/tests/lib/season/seasons.test.ts
//
// Tests for the season decision and the selector lists.
//
// Tested:
// - requestedSeason accepts exactly four digits and rejects everything else
// - currentSeason is the first season of the calendar
// - seasonOnShow: current with no request, pending until the calendar settles, current with a failed
//   calendar, for the current season and for an unlisted year, the number for a listed past year
// - teamSeasons: every season with no names, only the seasons inside runs, a run with no end runs to
//   the current season, the season on show is kept
// - playerSeasons: the labels that match plus the current season, no labels, a label not in the calendar
// - seasonLabelOf: the calendar's label of a listed season, null for an unlisted season and for a missing calendar
//
// What is covered:
// - Pure logic: happy path, edge cases and the error paths
//
// Run with: cd web && pnpm exec vitest run tests/lib/season/seasons.test.ts
//
// SEE: web/src/lib/season/seasons.ts
import { describe, expect, it } from 'vitest';

import type { CalendarFeed } from '../../../src/lib/contract/calendar';
import {
	currentSeason,
	playerSeasons,
	requestedSeason,
	seasonLabelOf,
	seasonOnShow,
	teamSeasons
} from '../../../src/lib/season/seasons';
import calendarJson from '../feed/fixtures/calendar.json';

const calendar = calendarJson as unknown as CalendarFeed;
const ends = (list: { season: number }[]) => list.map((item) => item.season);

describe('requestedSeason', () => {
	it('accepts four digits', () => {
		expect(requestedSeason('2005')).toBe(2005);
	});

	it.each([null, '', '05', '20050', 'abcd', '2005x', ' 2005'])('rejects %j', (value) => {
		expect(requestedSeason(value)).toBeNull();
	});
});

describe('currentSeason', () => {
	it('is the first season of the calendar', () => {
		expect(currentSeason(calendar)).toBe(2027);
	});
});

describe('seasonOnShow', () => {
	it('is current with no request, even before the calendar settles', () => {
		expect(seasonOnShow(null, null, false)).toBe('current');
	});

	it('is pending until the calendar settles', () => {
		expect(seasonOnShow(2005, null, false)).toBe('pending');
	});

	it('is current with a failed or missing calendar', () => {
		expect(seasonOnShow(2005, null, true)).toBe('current');
	});

	it('is current for the current season and for a year the calendar does not list', () => {
		expect(seasonOnShow(2027, calendar, true)).toBe('current');
		expect(seasonOnShow(1990, calendar, true)).toBe('current');
		expect(seasonOnShow(2030, calendar, true)).toBe('current');
	});

	it('is the number for a listed past year', () => {
		expect(seasonOnShow(2005, calendar, true)).toBe(2005);
	});
});

describe('teamSeasons', () => {
	it('lists every season with no names or an empty list', () => {
		expect(ends(teamSeasons(calendar, null, 2027))).toEqual(ends(calendar.seasons));
		expect(ends(teamSeasons(calendar, [], 2027))).toEqual(ends(calendar.seasons));
	});

	it('lists only the seasons inside the runs, newest first', () => {
		const names = [
			{ from: 1994, to: 1996 },
			{ from: 1999, to: 2001 },
			{ from: 2020, to: null }
		];
		expect(ends(teamSeasons(calendar, names, 2027))).toEqual([
			2027, 2026, 2025, 2024, 2023, 2022, 2021, 2020, 2001, 2000, 1999, 1996, 1995, 1994
		]);
	});

	it('keeps the season on show', () => {
		const names = [{ from: 1994, to: 1996 }];
		expect(ends(teamSeasons(calendar, names, 2010))).toContain(2010);
	});
});

describe('playerSeasons', () => {
	it('lists the labels that match plus the current season', () => {
		const labels = [calendar.seasons[10].seasonLabel, calendar.seasons[20].seasonLabel];
		expect(ends(playerSeasons(calendar, labels, 2027))).toEqual([
			2027,
			calendar.seasons[10].season,
			calendar.seasons[20].season
		]);
	});

	it('lists the current season and the one on show with no labels', () => {
		expect(ends(playerSeasons(calendar, null, 2005))).toEqual([2027, 2005]);
	});

	it('ignores a label the calendar does not have', () => {
		expect(ends(playerSeasons(calendar, ['1980-81'], 2027))).toEqual([2027]);
	});
});

describe('seasonLabelOf', () => {
	it("gives the calendar's label of a listed season", () => {
		expect(seasonLabelOf(calendar, 2005)).toBe('2004-05');
	});

	it('gives null for an unlisted season and for a missing calendar', () => {
		expect(seasonLabelOf(calendar, 1980)).toBeNull();
		expect(seasonLabelOf(null, 2005)).toBeNull();
	});
});
