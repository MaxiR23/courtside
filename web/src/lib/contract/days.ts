/**
 * Generated from api/schemas/days.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';
export type StatsAvailability = 'available' | 'pending' | 'unavailable';
export type CupRound = 'group' | 'quarterfinals' | 'semifinals' | 'championship';
export type PostseasonStage = 'playin' | 'playoffs' | 'finals';
export type Conference = 'east' | 'west';
export type PlayInGameKind = 'seven_eight' | 'nine_ten' | 'eighth_seed';
export type Stakes = 'game_7' | 'elimination' | 'can_clinch' | 'clinched';

export interface DayFeed {
	generatedAt: string;
	season: number;
	seasonLabel: string;
	day: PastDay;
}
export interface PastDay {
	date: string;
	games: PastGame[];
}
export interface PastGame {
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
	winner: Side | null;
	leaders: Leaders | null;
	teamStats: GameTeamStats | null;
	statsAvailability: StatsAvailability | null;
	highlightsSearchUrl: string | null;
	cup: GameCup | null;
	postseason: GamePostseason | null;
	allStar: GameAllStar | null;
}
/**
 * A side of a game: one of the 30 teams, or a guest team outside the league.
 * A guest may have no city (an All-Star team); a league team has one.
 */
export interface GameTeam {
	code: string | null;
	name: string;
	city: string | null;
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
	teamCode: string | null;
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
/**
 * The mark of a Cup game: the round it belongs to.
 */
export interface GameCup {
	stage: CupRound;
}
/**
 * The mark of a play-in or playoff game: its stage, place in the bracket and stakes.
 */
export interface GamePostseason {
	stage: PostseasonStage;
	round: number | null;
	conference: Conference | null;
	number: number | null;
	summary: string | null;
	playIn: PlayInGameKind | null;
	stakes: Stakes | null;
}
/**
 * The mark of an All-Star game: its round as the source writes it, and
 * whether it is the Championship.
 */
export interface GameAllStar {
	roundLabel: string;
	championship: boolean;
}
