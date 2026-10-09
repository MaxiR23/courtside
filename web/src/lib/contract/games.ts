/**
 * Generated from api/schemas/games.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type StatsAvailability = 'available' | 'pending' | 'unavailable';

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
	away: GameTeam;
	home: GameTeam;
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
	statsAvailability: StatsAvailability | null;
	highlightsSearchUrl: string | null;
}
/**
 * A side of a game: one of the 30 teams, or a guest team outside the league.
 */
export interface GameTeam {
	code: string;
	name: string;
	city: string;
	guest: boolean;
}
export interface Stars {
	away: Star | null;
	home: Star | null;
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
	photoUrl: string | null;
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
