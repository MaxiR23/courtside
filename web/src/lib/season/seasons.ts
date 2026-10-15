import type { CalendarFeed } from '#lib/contract/calendar.ts';
import type { SeasonOption } from './types.ts';

/** The end year in `?season=`: exactly four digits, anything else is no request. */
export function requestedSeason(value: string | null): number | null {
	return value !== null && /^\d{4}$/.test(value) ? Number(value) : null;
}

/** ADR 0042: `seasons` runs from the current season down, newest first. */
export function currentSeason(calendar: CalendarFeed): number {
	return calendar.seasons[0].season;
}

/**
 * Which season a page shows (ADR 0044): `'pending'` while the calendar is awaited, `'current'` for
 * the current season, else the past season's end year. A primitive, so a calendar arriving later
 * does not rebuild what the page loads.
 */
export function seasonOnShow(
	requested: number | null,
	calendar: CalendarFeed | null,
	settled: boolean
): 'pending' | 'current' | number {
	if (requested === null) return 'current';
	if (!settled) return 'pending';
	if (!calendar) return 'current';
	const current = currentSeason(calendar);
	const listed = calendar.seasons.some((item) => item.season === requested);
	return listed && requested !== current ? requested : 'current';
}

/** The seasons inside one of the franchise's name runs; no runs lists every season. */
export function teamSeasons(
	calendar: CalendarFeed,
	names: { from: number; to: number | null }[] | null,
	value: number
): SeasonOption[] {
	if (!names || names.length === 0) return [...calendar.seasons];
	const current = currentSeason(calendar);
	return calendar.seasons.filter(
		(item) =>
			item.season === value ||
			names.some((run) => run.from <= item.season && item.season <= (run.to ?? current))
	);
}

/** The seasons whose label is a regular-season row of the player, plus the current one and `value`. */
export function playerSeasons(
	calendar: CalendarFeed,
	labels: string[] | null,
	value: number
): SeasonOption[] {
	const current = currentSeason(calendar);
	return calendar.seasons.filter(
		(item) =>
			item.season === current ||
			item.season === value ||
			(labels?.includes(item.seasonLabel) ?? false)
	);
}
