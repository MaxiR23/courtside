import type { ScheduleGame } from '#lib/schedule/types.ts';

/** The day page's data: the day's date, its season and its games as cards. */
export type DayView = {
	date: string; // the feed's day.date, 'YYYY-MM-DD'
	title: string; // "February 6, 1999"
	weekday: string; // "Saturday"
	seasonLabel: string; // "1998-99"
	season: number; // end year
	games: ScheduleGame[];
};

export type DayPageState =
	{ kind: 'loading' } | { kind: 'unavailable' } | { kind: 'ready'; view: DayView };
