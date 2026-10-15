import type { DayFeed } from '#lib/contract/days.ts';
import { scheduleGames } from '#lib/feed/props.ts';
import { formatDate } from '#lib/format/locale.ts';
import type { DayView } from '#lib/day/types.ts';

function feedDate(isoDate: string, options: Intl.DateTimeFormatOptions): string {
	// A contract date is a calendar date: format it in UTC so no time zone moves it.
	return formatDate(new Date(`${isoDate}T00:00:00Z`), { ...options, timeZone: 'UTC' });
}

/**
 * Turns the day feed into the day page props, or null when it cannot be shown. A past game has no
 * highlights block: no video platform name is passed.
 */
export function toDayView(feed: DayFeed): DayView | null {
	const games = scheduleGames(feed.day.games, {});
	if (!games) return null;
	return {
		date: feed.day.date,
		title: feedDate(feed.day.date, { month: 'long', day: 'numeric', year: 'numeric' }),
		weekday: feedDate(feed.day.date, { weekday: 'long' }),
		seasonLabel: feed.seasonLabel,
		season: feed.season,
		games
	};
}
