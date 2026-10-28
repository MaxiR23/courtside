import { formatDate, formatDateParts } from '#lib/format/locale.ts';

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
