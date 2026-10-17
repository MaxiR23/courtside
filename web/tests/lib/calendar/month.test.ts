// web/tests/lib/calendar/month.test.ts
//
// Tests for the pure month helpers of the calendar sheet and the day page.
//
// Tested:
// - monthOf takes the month of a date
// - monthsBetween lists one month, a season from October to June, the 1998-99 lockout and the 2019-20 restart that runs to August
// - monthGrid pads weeks of 7 cells from Sunday: a February of 28 days on a Sunday, a leap February and a month starting on Saturday
// - openingMonth gives the selected day's month inside the season and the first month before, after it and for null
// - clampedMonth clamps the selected month to both ends and gives the last month for null
// - neighbours gives the previous and next day, null at the ends, works for a date not in the list and crosses the lockout and restart gaps
// - lastLinkedDay gives today inside the season, the last day when today is after it, and the first day when today is before it
// - isWindowDay: the games feed's days win when loaded, else the calendar's window, and an empty window has no day
// - easternToday gives the US Eastern date, one day behind UTC at 03:30
//
// What is covered:
// - Pure logic: happy path and edges; no clock, no time zone of the machine
//
// Run with: cd web && pnpm exec vitest run tests/lib/calendar/month.test.ts
//
// SEE: web/src/lib/calendar/month.ts
import { describe, expect, it } from 'vitest';

import {
	clampedMonth,
	easternToday,
	isWindowDay,
	lastLinkedDay,
	monthGrid,
	monthOf,
	monthsBetween,
	neighbours,
	openingMonth
} from '../../../src/lib/calendar/month';

describe('monthOf', () => {
	it('takes the YYYY-MM of a date', () => {
		expect(monthOf('1999-02-05')).toBe('1999-02');
	});
});

describe('monthsBetween', () => {
	it('lists one month when both days share it', () => {
		expect(monthsBetween('2026-10-01', '2026-10-31')).toEqual(['2026-10']);
	});

	it('lists a season from October to June', () => {
		const months = monthsBetween('2025-10-21', '2026-06-19');
		expect(months).toHaveLength(9);
		expect(months[0]).toBe('2025-10');
		expect(months[2]).toBe('2025-12');
		expect(months[3]).toBe('2026-01');
		expect(months[8]).toBe('2026-06');
	});

	it('lists the months of the 1998-99 lockout season', () => {
		expect(monthsBetween('1999-02-05', '1999-05-05')).toEqual([
			'1999-02',
			'1999-03',
			'1999-04',
			'1999-05'
		]);
	});

	it('lists the months of the 2019-20 restart that runs to August', () => {
		const months = monthsBetween('2019-10-22', '2020-08-14');
		expect(months[0]).toBe('2019-10');
		expect(months[months.length - 1]).toBe('2020-08');
		expect(months).toHaveLength(11);
	});
});

describe('monthGrid', () => {
	it('gives 4 rows with no padding for a February of 28 days that starts on a Sunday', () => {
		const grid = monthGrid('2015-02');
		expect(grid).toHaveLength(4);
		expect(grid[0][0]).toBe('2015-02-01');
		expect(grid[3][6]).toBe('2015-02-28');
		expect(grid.flat().every((cell) => cell !== null)).toBe(true);
	});

	it('gives 29 days for a leap February', () => {
		const days = monthGrid('2024-02')
			.flat()
			.filter((cell) => cell !== null);
		expect(days).toHaveLength(29);
		expect(days[28]).toBe('2024-02-29');
	});

	it('pads a month that starts on a Saturday into 6 rows', () => {
		const grid = monthGrid('2020-08');
		expect(grid).toHaveLength(6);
		expect(grid[0]).toEqual([null, null, null, null, null, null, '2020-08-01']);
		expect(grid[5].slice(0, 2)).toEqual(['2020-08-30', '2020-08-31']);
		expect(grid[5].slice(2)).toEqual([null, null, null, null, null]);
		expect(grid.every((week) => week.length === 7)).toBe(true);
	});
});

describe('openingMonth', () => {
	it('gives the selected day month inside the season', () => {
		expect(openingMonth('1999-03-01', '1999-02-05', '1999-05-05')).toBe('1999-03');
	});

	it('gives the first month for a day before the season, after it, or none', () => {
		expect(openingMonth('2026-10-12', '1999-02-05', '1999-05-05')).toBe('1999-02');
		expect(openingMonth('1998-01-01', '1999-02-05', '1999-05-05')).toBe('1999-02');
		expect(openingMonth(null, '1999-02-05', '1999-05-05')).toBe('1999-02');
	});
});

describe('clampedMonth', () => {
	it('keeps the selected month inside the season', () => {
		expect(clampedMonth('1999-03-20', '1999-02-05', '1999-05-05')).toBe('1999-03');
	});

	it('clamps to the first and the last month', () => {
		expect(clampedMonth('1998-12-01', '1999-02-05', '1999-05-05')).toBe('1999-02');
		expect(clampedMonth('2026-10-12', '1999-02-05', '1999-05-05')).toBe('1999-05');
	});

	it('gives the last month when nothing is selected', () => {
		expect(clampedMonth(null, '1999-02-05', '1999-05-05')).toBe('1999-05');
	});
});

describe('neighbours', () => {
	const days = ['1999-02-05', '1999-02-06', '1999-02-09', '1999-05-05'];

	it('gives the day before and the day after a middle day', () => {
		expect(neighbours(days, '1999-02-06')).toEqual({
			previous: '1999-02-05',
			next: '1999-02-09'
		});
	});

	it('gives a null previous at the first day and a null next at the last', () => {
		expect(neighbours(days, '1999-02-05')).toEqual({ previous: null, next: '1999-02-06' });
		expect(neighbours(days, '1999-05-05')).toEqual({ previous: '1999-02-09', next: null });
	});

	it('works for a date that is not in the list', () => {
		expect(neighbours(days, '1999-02-07')).toEqual({
			previous: '1999-02-06',
			next: '1999-02-09'
		});
	});

	it('crosses the gap of a lockout season, from the first day back to null', () => {
		expect(neighbours(days, '1999-02-05').previous).toBeNull();
		expect(neighbours(days, '1999-02-09').next).toBe('1999-05-05');
	});

	it('crosses the pause of the 2020 restart', () => {
		const restart = ['2020-03-10', '2020-03-11', '2020-07-30', '2020-07-31'];
		expect(neighbours(restart, '2020-03-11').next).toBe('2020-07-30');
		expect(neighbours(restart, '2020-07-30').previous).toBe('2020-03-11');
	});
});

describe('easternToday', () => {
	it('gives the previous US Eastern date at 03:30 UTC', () => {
		expect(easternToday(new Date('2026-10-15T03:30:00Z'))).toBe('2026-10-14');
	});

	it('gives the same date at noon UTC', () => {
		expect(easternToday(new Date('2026-10-15T16:00:00Z'))).toBe('2026-10-15');
	});
});

describe('lastLinkedDay', () => {
	it('gives today when it is inside the season', () => {
		expect(lastLinkedDay('2026-10-20', '2027-04-10', '2026-12-15')).toBe('2026-12-15');
	});

	it('gives the last day when today is after the season', () => {
		expect(lastLinkedDay('1999-02-05', '1999-05-05', '2026-10-15')).toBe('1999-05-05');
	});

	it('gives the first day when today is before the season', () => {
		expect(lastLinkedDay('2026-10-20', '2027-04-10', '2026-01-01')).toBe('2026-10-20');
	});
});

describe('isWindowDay', () => {
	const gamesDays = ['2026-10-01', '2026-10-02'];
	const window = ['2026-10-02', '2026-10-03'];

	it("uses the games feed's days when that feed is loaded", () => {
		expect(isWindowDay('2026-10-01', gamesDays, window)).toBe(true);
		expect(isWindowDay('2026-10-03', gamesDays, window)).toBe(false);
	});

	it("falls back to the calendar's window before the games feed has loaded", () => {
		expect(isWindowDay('2026-10-03', null, window)).toBe(true);
		expect(isWindowDay('2026-10-01', null, window)).toBe(false);
	});

	it('has no window day with an empty window', () => {
		expect(isWindowDay('2026-10-01', null, [])).toBe(false);
	});
});
