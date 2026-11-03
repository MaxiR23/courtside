import { formatDate, formatDateParts } from '#lib/format/locale.ts';
import { m } from '#lib/paraglide/messages.js';

/** The zone of the NBA day (ADR 0013, ADR 0082). */
export const NBA_TIME_ZONE = 'America/New_York';

/**
 * An instant's time in the viewer's zone (or the given one), split: "8:30" and "PM".
 * A 24-hour language gives "20:30" and "".
 */
export function viewerTimeParts(
	instant: string,
	timeZone?: string
): { time: string; dayPeriod: string } {
	const parts = formatDateParts(new Date(instant), {
		timeZone,
		hour: 'numeric',
		minute: '2-digit'
	});
	let time = '';
	let dayPeriod = '';
	for (const part of parts) {
		if (part.type === 'dayPeriod') dayPeriod = part.value;
		else if (!dayPeriod) time += part.value;
	}
	return { time: time.trim(), dayPeriod };
}

/** "8:30 PM", or "20:30" in a 24-hour language: the parts joined by one space, with no empty part. */
export function viewerTime(instant: string, timeZone?: string): string {
	const { time, dayPeriod } = viewerTimeParts(instant, timeZone);
	return [time, dayPeriod].filter(Boolean).join(' ');
}

/** An instant's date in the viewer's zone, for a date shown together with its time. */
export function viewerDate(
	instant: string,
	options: Intl.DateTimeFormatOptions,
	timeZone?: string
): string {
	return formatDate(new Date(instant), { ...options, timeZone });
}

/** An instant's date in US Eastern: the NBA day, for a date that names the game's day without a time. */
export function nbaDate(instant: string, options: Intl.DateTimeFormatOptions): string {
	return formatDate(new Date(instant), { ...options, timeZone: NBA_TIME_ZONE });
}

const HOUR_MS = 3_600_000;

/**
 * A note's date (ADR 0082): under 24 hours old, the hours ("16 h ago", at least 1); otherwise the
 * day and short month in the viewer's zone, with the year when it is not the current one. `now`
 * is an argument so no caller reads the clock here.
 */
export function noteDate(published: string, now: Date): string {
	const age = now.getTime() - new Date(published).getTime();
	if (age < 24 * HOUR_MS)
		return m.news_hours_ago({ hours: Math.max(1, Math.floor(age / HOUR_MS)) });
	const year = (instant: Date) => formatDateParts(instant, { year: 'numeric' })[0].value;
	const sameYear = year(new Date(published)) === year(now);
	return viewerDate(
		published,
		sameYear
			? { day: 'numeric', month: 'short' }
			: { day: 'numeric', month: 'short', year: 'numeric' }
	);
}

/** A note's full date and time in the viewer's zone: "November 2, 2026, 8:30 PM". */
export function noteFullDate(published: string): string {
	const date = viewerDate(published, { day: 'numeric', month: 'long', year: 'numeric' });
	return `${date}, ${viewerTime(published)}`;
}
