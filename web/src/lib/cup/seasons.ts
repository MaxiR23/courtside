import type { CalendarFeed } from '#lib/contract/calendar.ts';
import type { SeasonOption } from '#lib/season/types.ts';

/** The first Cup season (2023-24), as the api's season Cup feed (ADR 0045, ADR 0049). No feed carries it. */
export const FIRST_CUP_SEASON = 2024;

/** The calendar's seasons from the first Cup season, newest first. */
export function cupSeasons(calendar: CalendarFeed): SeasonOption[] {
	return calendar.seasons.filter((entry) => entry.season >= FIRST_CUP_SEASON);
}
