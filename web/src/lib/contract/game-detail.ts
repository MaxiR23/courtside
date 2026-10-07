/**
 * Generated from api/schemas/game-detail.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
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
	winner: string | null;
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
	code: string;
	name: string;
	city: string;
	record: Record;
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
	fieldGoalPct: string | null;
	threePointPct: string | null;
	freeThrowPct: string | null;
	rebounds: string | null;
	assists: string | null;
	turnovers: string | null;
	steals: string | null;
	blocks: string | null;
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
	photoUrl: string;
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
	teamCode: string;
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
	away: Injury[];
	home: Injury[];
}
export interface Injury {
	displayName: string;
	status: InjuryStatus;
	comment: string | null;
}
export interface LastGames {
	/**
	 * @maxItems 5
	 */
	away:
		| []
		| [LastGame]
		| [LastGame, LastGame]
		| [LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame, LastGame];
	/**
	 * @maxItems 5
	 */
	home:
		| []
		| [LastGame]
		| [LastGame, LastGame]
		| [LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame]
		| [LastGame, LastGame, LastGame, LastGame, LastGame];
}
export interface LastGame {
	date: string;
	opponent: string;
	isHome: boolean;
	result: GameResult;
	teamScore: number;
	opponentScore: number;
}
export interface Standings {
	away: TeamStanding;
	home: TeamStanding;
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
