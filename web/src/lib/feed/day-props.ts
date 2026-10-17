import type { DayFeed } from '#lib/contract/days.ts';
import type { GameDetailFeed } from '#lib/contract/game-detail.ts';
import { leader, scheduleGames } from '#lib/feed/props.ts';
import { formatDate } from '#lib/format/locale.ts';
import type { DayView } from '#lib/day/types.ts';
import type { Leader, ScheduleGame, TeamStatLine } from '#lib/schedule/types.ts';

export type CardDetails = {
	leaders: { away: Leader; home: Leader } | null;
	stats: { away: TeamStatLine; home: TeamStatLine } | null;
};

const statLine = (stats: NonNullable<GameDetailFeed['teamStats']>['away']): TeamStatLine => ({
	fieldGoalPct: stats.fieldGoalPct,
	threePointPct: stats.threePointPct,
	rebounds: stats.rebounds,
	assists: stats.assists,
	turnovers: stats.turnovers
});

/** The leaders and team stats a past day card shows, read from its game detail; a missing block is null. */
export function cardDetails(feed: GameDetailFeed): CardDetails {
	return {
		leaders: feed.leaders
			? {
					away: leader(feed.leaders.away, feed.away),
					home: leader(feed.leaders.home, feed.home)
				}
			: null,
		stats: feed.teamStats
			? { away: statLine(feed.teamStats.away), home: statLine(feed.teamStats.home) }
			: null
	};
}

/** Adds each part present to a past final card whose stats are on the game page; any other game is returned as is. */
export function withCardDetails(game: ScheduleGame, details: CardDetails | null): ScheduleGame {
	const current = game.details;
	if (
		!details ||
		current?.kind !== 'final-without-stats' ||
		current.statsAvailability !== 'available'
	) {
		return game;
	}
	return {
		...game,
		details: {
			...current,
			...(details.leaders ? { leaders: details.leaders } : {}),
			...(details.stats ? { stats: details.stats } : {})
		}
	};
}

function feedDate(isoDate: string, options: Intl.DateTimeFormatOptions): string {
	// A contract date is a calendar date: format it in UTC so no time zone moves it.
	return formatDate(new Date(`${isoDate}T00:00:00Z`), { ...options, timeZone: 'UTC' });
}

/**
 * Turns the day feed into the day page props, or null when it cannot be shown. A final game shows
 * the highlights block when a video platform name is given, as the home does.
 */
export function toDayView(
	feed: DayFeed,
	options: { videoPlatformName?: string } = {}
): DayView | null {
	const games = scheduleGames(feed.day.games, options);
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
