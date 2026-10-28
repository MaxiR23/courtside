// web/tests/lib/format/time.test.ts
//
// Tests for the time helpers: times in the viewer's zone, the NBA day in US Eastern.
//
// Tested:
// - A tip shows in the zone given, with no zone suffix (Buenos Aires, Madrid)
// - The time and the day period are split; a 24-hour language has an empty day period
// - viewerTime joins the parts without a trailing space
// - With no zone given, the default zone is used (pinned to America/New_York in the suite)
// - viewerDate follows the viewer's zone; nbaDate stays on the Eastern day
// - An invalid instant throws a RangeError
//
// What is covered:
// - Happy path, edge cases (day change, 24-hour language) and error case
// - Fixed instants, no real clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/format/time.test.ts
//
// SEE: web/src/lib/format/time.ts, docs/adr/0082-tip-times-in-the-viewers-time-zone.md
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
	NBA_TIME_ZONE,
	nbaDate,
	viewerDate,
	viewerTime,
	viewerTimeParts
} from '../../../src/lib/format/time';
import { preferLanguages } from '../../prefer-languages';

const LATE = '2026-10-04T23:30:00Z';
const SHORT_DAY: Intl.DateTimeFormatOptions = { weekday: 'short', month: 'short', day: 'numeric' };

afterEach(() => {
	vi.restoreAllMocks();
	vi.unstubAllEnvs();
});

describe('viewerTime', () => {
	it('shows a tip in Buenos Aires with no zone suffix', () => {
		expect(viewerTime(LATE, 'America/Argentina/Buenos_Aires')).toBe('8:30 PM');
	});

	it('shows the same tip in Madrid after local midnight', () => {
		expect(viewerTime(LATE, 'Europe/Madrid')).toBe('1:30 AM');
	});

	it('uses the default zone when none is given', () => {
		expect(viewerTime(LATE)).toBe('7:30 PM');
	});

	it('gives a 24-hour time with no trailing space in Spanish', () => {
		preferLanguages(['es']);
		expect(viewerTime(LATE, 'Europe/Madrid')).toBe('1:30');
	});

	it('throws a RangeError on an invalid instant', () => {
		expect(() => viewerTime('not a date')).toThrow(RangeError);
	});
});

describe('viewerTimeParts', () => {
	it('splits the time and the day period', () => {
		expect(viewerTimeParts(LATE, 'America/Argentina/Buenos_Aires')).toEqual({
			time: '8:30',
			dayPeriod: 'PM'
		});
	});

	it('gives an empty day period in a 24-hour language', () => {
		preferLanguages(['es']);
		expect(viewerTimeParts('2026-10-04T18:30:00Z', 'Europe/Madrid')).toEqual({
			time: '20:30',
			dayPeriod: ''
		});
	});
});

describe('viewerDate and nbaDate', () => {
	it('gives the next day in Madrid for a late tip', () => {
		expect(viewerDate(LATE, SHORT_DAY, 'Europe/Madrid')).toBe('Mon, Oct 5');
	});

	it('gives the Eastern day whatever the default zone', () => {
		vi.stubEnv('TZ', 'Europe/Madrid');
		expect(nbaDate(LATE, SHORT_DAY)).toBe('Sun, Oct 4');
		expect(viewerDate(LATE, SHORT_DAY)).toBe('Mon, Oct 5');
	});

	it('names the zone of the NBA day', () => {
		expect(NBA_TIME_ZONE).toBe('America/New_York');
	});
});
