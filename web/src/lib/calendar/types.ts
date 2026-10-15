import type { ResolvedPathname } from '$app/types';
import type { CalendarFeed } from '#lib/contract/calendar.ts';

/** What the date button hands to the calendar sheet. */
export type DateCalendar = {
	load: ((season: string) => Promise<CalendarFeed>) | undefined; // undefined: no URL configured
	season: string; // 'current' on the home, the day's end year on the day page
	selectedDay: string | null; // 'YYYY-MM-DD'
	today: string | null; // 'YYYY-MM-DD'
	dayHref: (date: string) => ResolvedPathname;
};
