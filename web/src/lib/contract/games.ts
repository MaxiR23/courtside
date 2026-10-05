/**
 * Generated from api/schemas/games.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';

export interface GamesFeed {
	generatedAt: string;
	days: Day[];
}
export interface Day {
	date: string;
	games: Game[];
}
export interface Game {
	id: string;
	away: Team;
	home: Team;
	status: GameStatus;
	startTime: string;
	venue: string;
	stars: Stars;
	highlights: Highlight[];
	broadcast: string | null;
	period: number | null;
	clock: string | null;
	lineScore: LineScore | null;
	score: Score | null;
	winner: string | null;
	leaders: Leaders | null;
	teamStats: GameTeamStats | null;
	highlightsSearchUrl: string | null;
}
export interface Team {
	code: string;
	name: string;
	city: string;
}
export interface Stars {
	away: Star;
	home: Star;
}
export interface Star {
	playerId: string;
	firstName: string;
	lastName: string;
	teamCode: string;
	photoUrl: string;
	shortName: string;
}
export interface Highlight {
	title: string;
	channel: string;
	thumbnailUrl: string;
	embedUrl: string;
}
export interface LineScore {
	/**
	 * @minItems 1
	 */
	away: [number, ...number[]];
	/**
	 * @minItems 1
	 */
	home: [number, ...number[]];
}
export interface Score {
	away: number;
	home: number;
}
export interface Leaders {
	away: Leader;
	home: Leader;
}
export interface Leader {
	playerId: string;
	displayName: string;
	teamCode: string;
	photoUrl: string;
	points: number;
	rebounds: number;
	assists: number;
}
export interface GameTeamStats {
	away: TeamStats;
	home: TeamStats;
}
export interface TeamStats {
	fieldGoalPct: number;
	threePointPct: number;
	rebounds: number;
	assists: number;
	turnovers: number;
}
