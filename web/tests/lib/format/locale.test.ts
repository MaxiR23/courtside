// web/tests/lib/format/locale.test.ts
//
// Tests for the locale-aware date and number formatting.
//
// Tested:
// - formatDateParts splits a time into parts in a given time zone
// - formatDate and formatNumber follow the browser language (English, Spanish)
// - An unsupported language falls back to English
// - Numbers of 5 digits are grouped
// - An invalid date throws a RangeError
//
// What is covered:
// - Happy path, fallback, edge case (grouping) and error case
// - Fixed inputs, no real clock
//
// Run with: cd web && pnpm exec vitest run tests/lib/format/locale.test.ts
//
// SEE: web/src/lib/format/locale.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { formatDate, formatDateParts, formatNumber } from '../../../src/lib/format/locale';
import { preferLanguages } from '../../prefer-languages';

const date = new Date(Date.UTC(2026, 9, 4, 12));
const dateOptions: Intl.DateTimeFormatOptions = {
	weekday: 'short',
	month: 'short',
	day: 'numeric',
	timeZone: 'UTC'
};

afterEach(() => {
	vi.restoreAllMocks();
});

describe('formatDate', () => {
	it('formats in English by default', () => {
		expect(formatDate(date, dateOptions)).toBe('Sun, Oct 4');
	});

	it('formats in Spanish with a Spanish preference', () => {
		preferLanguages(['es-ES']);
		expect(formatDate(date, dateOptions)).toBe('dom, 4 oct');
	});

	it('formats in English for an unsupported language', () => {
		preferLanguages(['fr-FR']);
		expect(formatDate(date, dateOptions)).toBe('Sun, Oct 4');
	});

	it('throws a RangeError for an invalid date', () => {
		expect(() => formatDate(new Date(NaN), dateOptions)).toThrow(RangeError);
	});
});

describe('formatNumber', () => {
	it('groups 5 digits with commas in English', () => {
		expect(formatNumber(12345.6)).toBe('12,345.6');
	});

	it('groups 5 digits with dots in Spanish', () => {
		preferLanguages(['es-ES']);
		expect(formatNumber(12345.6)).toBe('12.345,6');
	});

	it('formats in English for an unsupported language', () => {
		preferLanguages(['fr-FR']);
		expect(formatNumber(12345.6)).toBe('12,345.6');
	});
});

describe('formatDateParts', () => {
	const timeOptions: Intl.DateTimeFormatOptions = {
		timeZone: 'America/New_York',
		hour: 'numeric',
		minute: '2-digit'
	};
	const typed = (parts: Intl.DateTimeFormatPart[], type: string) =>
		parts.find((p) => p.type === type)?.value;

	it('splits an Eastern time into hour, minute and day period in English', () => {
		const parts = formatDateParts(new Date(Date.UTC(2026, 9, 5, 1, 0)), timeOptions);
		expect(typed(parts, 'hour')).toBe('9');
		expect(typed(parts, 'minute')).toBe('00');
		expect(typed(parts, 'dayPeriod')).toBe('PM');
	});

	it('has no day period in Spanish', () => {
		preferLanguages(['es-ES']);
		const parts = formatDateParts(new Date(Date.UTC(2026, 9, 5, 1, 0)), timeOptions);
		expect(typed(parts, 'dayPeriod')).toBeUndefined();
		expect(typed(parts, 'hour')).toBe('21');
	});

	it('uses the New York time zone across a UTC day boundary', () => {
		const parts = formatDateParts(new Date(Date.UTC(2026, 9, 5, 1, 30)), timeOptions);
		expect(typed(parts, 'hour')).toBe('9');
		expect(typed(parts, 'minute')).toBe('30');
		expect(typed(parts, 'dayPeriod')).toBe('PM');
	});
});
