/**
 * Generated from api/schemas/calendar.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export interface CalendarFeed {
	generatedAt: string;
	season: number;
	seasonLabel: string;
	firstDay: string;
	lastDay: string;
	/**
	 * @minItems 1
	 */
	days: [string, ...string[]];
	windowDays: string[];
	/**
	 * @minItems 1
	 */
	seasons: [CalendarSeason, ...CalendarSeason[]];
}
export interface CalendarSeason {
	season: number;
	seasonLabel: string;
}
