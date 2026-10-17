import type { ResolvedPathname } from '$app/types';
import type { CalendarFeed } from '#lib/contract/calendar.ts';

/** What the date button hands to the calendar sheet. */
export type DateCalendar = {
	load: ((season: string) => Promise<CalendarFeed>) | undefined; // undefined: no URL configured
	season: string; // 'current' on the home, the day's end year on the day page
	selectedDay: string | null; // 'YYYY-MM-DD'
	today: string; // 'YYYY-MM-DD', the US Eastern date: no later day is ever a link
	windowDays: string[] | null; // the games feed's days when that feed is loaded; null: not loaded or the day page
	windowHref: (date: string) => ResolvedPathname; // a window day: the home, /?day=YYYY-MM-DD
	dayHref: (date: string) => ResolvedPathname; // any other day: /day/YYYY-MM-DD
};
