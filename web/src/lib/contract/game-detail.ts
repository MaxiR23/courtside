/**
 * Generated from api/schemas/game-detail.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';
export type InjuryStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';
export type GameResult = 'win' | 'loss';
export type Conference = 'east' | 'west';

export interface GameDetailFeed {
	id: string;
	status: GameStatus;
	startTime: string;
	venue: Venue;
	away: DetailTeam;
	home: DetailTeam;
	broadcast: string | null;
	period: number | null;
	clock: string | null;
	lineScore: LineScore | null;
	score: Score | null;
	winner: Side | null;
	teamStats: DetailGameTeamStats | null;
	stars: Stars | null;
	boxScore: BoxScore | null;
	winProbability: [WinProbabilityPoint, ...WinProbabilityPoint[]] | null;
	winProbabilityLeader: WinProbabilityLeader | null;
	winProbabilityPeriods: WinProbabilityPeriods | null;
	injuries: Injuries | null;
	lastGames: LastGames | null;
	standings: Standings | null;
	seasonSeries: SeasonSeries | null;
	highlights: Highlight[] | null;
	highlightsSearchUrl: string | null;
	videos: Video[] | null;
}
export interface Venue {
	name: string;
	city: string | null;
	photoUrl: string | null;
}
export interface DetailTeam {
	code: string | null;
	name: string;
	city: string;
	guest: boolean;
	record: Record | null;
}
export interface Record {
	wins: number;
	losses: number;
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
export interface DetailGameTeamStats {
	away: DetailTeamStats;
	home: DetailTeamStats;
	leaders: TeamStatLeaders;
}
export interface DetailTeamStats {
	fieldGoalPct: number;
	threePointPct: number;
	rebounds: number;
	assists: number;
	turnovers: number;
	freeThrowPct: number;
	steals: number;
	blocks: number;
}
export interface TeamStatLeaders {
	fieldGoalPct: Side | null;
	threePointPct: Side | null;
	freeThrowPct: Side | null;
	rebounds: Side | null;
	assists: Side | null;
	turnovers: Side | null;
	steals: Side | null;
	blocks: Side | null;
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
export interface BoxScore {
	away: TeamBoxScore;
	home: TeamBoxScore;
}
export interface TeamBoxScore {
	players: BoxScorePlayer[];
	totals: BoxScoreTotals;
}
export interface BoxScorePlayer {
	points: number;
	fieldGoalsMade: number;
	fieldGoalsAttempted: number;
	threePointsMade: number;
	threePointsAttempted: number;
	freeThrowsMade: number;
	freeThrowsAttempted: number;
	offensiveRebounds: number;
	defensiveRebounds: number;
	rebounds: number;
	assists: number;
	turnovers: number;
	steals: number;
	blocks: number;
	fouls: number;
	playerId: string;
	displayName: string;
	starter: boolean;
	minutes: string;
	plusMinus: number;
	photoUrl: string | null;
}
export interface BoxScoreTotals {
	points: number;
	fieldGoalsMade: number;
	fieldGoalsAttempted: number;
	threePointsMade: number;
	threePointsAttempted: number;
	freeThrowsMade: number;
	freeThrowsAttempted: number;
	offensiveRebounds: number;
	defensiveRebounds: number;
	rebounds: number;
	assists: number;
	turnovers: number;
	steals: number;
	blocks: number;
	fouls: number;
	fieldGoalPct: number;
	threePointPct: number;
	freeThrowPct: number;
}
export interface WinProbabilityPoint {
	elapsedSeconds: number;
	homeWinProbability: number;
}
export interface WinProbabilityLeader {
	side: Side;
	winProbability: number;
}
export interface WinProbabilityPeriods {
	/**
	 * @minItems 1
	 */
	periods: [GamePeriod, ...GamePeriod[]];
	endElapsedSeconds: number;
}
export interface GamePeriod {
	number: number;
	startElapsedSeconds: number;
}
export interface Injuries {
	away: Injury[] | null;
	home: Injury[] | null;
}
export interface Injury {
	playerId: string | null;
	displayName: string;
	status: InjuryStatus;
	comment: string | null;
}
export interface LastGames {
	away:
		| []
		| [LastGame]
		| [LastGame, LastGame]
		| [LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame, LastGame]
		| null;
	home:
		| []
		| [LastGame]
		| [LastGame, LastGame]
		| [LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame, LastGame]
		| null;
}
export interface LastGame {
	date: string;
	opponent: Opponent;
	isHome: boolean;
	result: GameResult;
	teamScore: number;
	opponentScore: number;
}
/**
 * A team a game is played against: a league team or a guest.
 */
export interface Opponent {
	code: string | null;
	name: string | null;
	city: string | null;
	guest: boolean;
}
export interface Standings {
	away: TeamStanding | null;
	home: TeamStanding | null;
}
export interface TeamStanding {
	conference: Conference;
	conferenceRank: number;
	record: Record;
	homeRecord: Record;
	awayRecord: Record;
	lastTen: Record;
}
export interface SeasonSeries {
	totalGames: number;
	awayWins: number;
	homeWins: number;
	leader: string | null;
	games: SeriesGame[];
}
export interface SeriesGame {
	date: string;
	away: string;
	home: string;
	isCurrent: boolean;
	score: Score | null;
	winner: string | null;
	arena: string;
}
export interface Highlight {
	title: string;
	channel: string;
	thumbnailUrl: string;
	embedUrl: string;
}
export interface Video {
	title: string;
	duration: string;
	thumbnailUrl: string | null;
	linkUrl: string;
}
