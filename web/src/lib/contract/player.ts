/**
 * Generated from api/schemas/player.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type InjuryStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';
export type TagKind = 'cup' | 'playoffs' | 'allstar';
export type Conference = 'east' | 'west';
export type GameKind = 'regular' | 'cup' | 'playoffs' | 'allstar';
export type GameResult = 'win' | 'loss';

export interface PlayerFeed {
	id: string;
	firstName: string;
	lastName: string;
	number: string | null;
	position: string;
	team: Team;
	photoUrl: string | null;
	injury: PlayerInjury | null;
	profile: Profile;
	summary: Summary | null;
	nextGame: NextGame | null;
	live: PlayerLive | null;
	/**
	 * @maxItems 5
	 */
	lastGames:
		| []
		| [GameLogEntry]
		| [GameLogEntry, GameLogEntry]
		| [GameLogEntry, GameLogEntry, GameLogEntry]
		| [GameLogEntry, GameLogEntry, GameLogEntry, GameLogEntry]
		| [GameLogEntry, GameLogEntry, GameLogEntry, GameLogEntry, GameLogEntry];
	averages: Averages;
	seasons: Seasons;
	milestones: Milestones | null;
	gameLog: GameLog | null;
	awards: Award[];
}
export interface Team {
	code: string;
	name: string;
	city: string;
}
export interface PlayerInjury {
	status: InjuryStatus;
	comment: string | null;
	updatedAt: string;
}
export interface Profile {
	height: Height | null;
	weight: Weight | null;
	birthDate: string | null;
	age: number | null;
	birthplace: Birthplace | null;
	college: string | null;
	draft: Draft | null;
	seasons: number | null;
	debutSeason: string | null;
}
export interface Height {
	display: string;
	cm: number;
}
export interface Weight {
	lb: number;
	kg: number;
}
export interface Birthplace {
	place: string;
	country: string | null;
}
export interface Draft {
	year: number;
	round: number;
	pick: number;
	teamName: string;
}
export interface Summary {
	season: string;
	points: RankedStat;
	rebounds: RankedStat;
	assists: RankedStat;
	fieldGoalPct: RankedPercentage;
}
export interface RankedStat {
	value: number;
	rank: number | null;
}
export interface RankedPercentage {
	value: number;
	rank: number | null;
}
export interface NextGame {
	gameId: string;
	startTime: string;
	opponent: string;
	isHome: boolean;
	tag: GameTag | null;
	arena: string;
	city: string | null;
	broadcast: string | null;
	detailAvailable: boolean;
}
export interface GameTag {
	kind: TagKind;
	conference: Conference | null;
	round: number | null;
	game: number | null;
}
export interface PlayerLive {
	gameId: string;
	opponent: string;
	isHome: boolean;
	period: number;
	clock: string;
	teamScore: number;
	opponentScore: number;
	line: BoxScorePlayer | null;
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
export interface GameLogEntry {
	gameId: string;
	date: string;
	opponent: string | null;
	isHome: boolean;
	kind: GameKind;
	tag: GameTag | null;
	result: GameResult;
	teamScore: number;
	opponentScore: number;
	minutes: number;
	fieldGoalsMade: number;
	fieldGoalsAttempted: number;
	fieldGoalPct: number;
	threePointsMade: number;
	threePointsAttempted: number;
	threePointPct: number;
	freeThrowsMade: number;
	freeThrowsAttempted: number;
	freeThrowPct: number;
	rebounds: number;
	assists: number;
	blocks: number;
	steals: number;
	fouls: number;
	turnovers: number;
	points: number;
	detailAvailable: boolean;
}
export interface Averages {
	regular: SeasonAverageRow | null;
	playoffs: SeasonAverageRow | null;
	career: AverageRow | null;
}
export interface SeasonAverageRow {
	gamesPlayed: number;
	minutes: number;
	fieldGoalPct: number;
	threePointPct: number;
	freeThrowPct: number;
	rebounds: number;
	assists: number;
	blocks: number;
	steals: number;
	fouls: number;
	turnovers: number;
	points: number;
	season: string;
}
export interface AverageRow {
	gamesPlayed: number;
	minutes: number;
	fieldGoalPct: number;
	threePointPct: number;
	freeThrowPct: number;
	rebounds: number;
	assists: number;
	blocks: number;
	steals: number;
	fouls: number;
	turnovers: number;
	points: number;
}
export interface Seasons {
	regular: SeasonSplit;
	playoffs: SeasonSplit;
}
export interface SeasonSplit {
	perGame: SeasonRow[];
	totals: SeasonRow[];
	career: CareerRows | null;
}
export interface SeasonRow {
	gamesPlayed: number;
	gamesStarted: number;
	minutes: number | null;
	fieldGoalsMade: number;
	fieldGoalsAttempted: number;
	fieldGoalPct: number;
	threePointsMade: number;
	threePointsAttempted: number;
	threePointPct: number;
	freeThrowsMade: number;
	freeThrowsAttempted: number;
	freeThrowPct: number;
	offensiveRebounds: number;
	defensiveRebounds: number;
	rebounds: number;
	assists: number;
	blocks: number;
	steals: number;
	fouls: number;
	turnovers: number;
	points: number;
	season: string;
	/**
	 * @minItems 1
	 */
	teams: [string, ...string[]];
}
export interface CareerRows {
	perGame: StatRow;
	totals: StatRow;
}
export interface StatRow {
	gamesPlayed: number;
	gamesStarted: number;
	minutes: number | null;
	fieldGoalsMade: number;
	fieldGoalsAttempted: number;
	fieldGoalPct: number;
	threePointsMade: number;
	threePointsAttempted: number;
	threePointPct: number;
	freeThrowsMade: number;
	freeThrowsAttempted: number;
	freeThrowPct: number;
	offensiveRebounds: number;
	defensiveRebounds: number;
	rebounds: number;
	assists: number;
	blocks: number;
	steals: number;
	fouls: number;
	turnovers: number;
	points: number;
}
export interface Milestones {
	season: string;
	current: MilestoneCounts;
	career: MilestoneCounts;
}
export interface MilestoneCounts {
	doubleDoubles: number;
	tripleDoubles: number;
	disqualifications: number;
	ejections: number;
	technicals: number;
	flagrants: number;
	assistTurnoverRatio: number;
	stealTurnoverRatio: number;
}
export interface GameLog {
	season: string;
	entries: GameLogEntry[];
}
export interface Award {
	name: string;
	count: number;
	/**
	 * @minItems 1
	 */
	seasons: [string, ...string[]];
}
