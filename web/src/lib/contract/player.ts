/**
 * Generated from api/schemas/player.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type InjuryStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';
export type TagKind = 'cup' | 'playoffs' | 'allstar';
export type Conference = 'east' | 'west';
export type GameKind = 'regular' | 'cup' | 'playoffs' | 'allstar' | 'preseason';
export type GameResult = 'win' | 'loss';
/**
 * The kind of a season award, shared by the playoffs and the player feeds.
 */
export type AwardCode =
	| 'mvp'
	| 'dpoy'
	| 'roy'
	| 'sixth_man'
	| 'mip'
	| 'cpoy'
	| 'finals_mvp'
	| 'east_finals_mvp'
	| 'west_finals_mvp'
	| 'all_star_mvp'
	| 'cup_mvp'
	| 'cup_all_tournament'
	| 'all_nba'
	| 'all_rookie'
	| 'all_defensive'
	| 'twyman_stokes';

export interface PlayerFeed {
	id: string;
	firstName: string;
	lastName: string;
	number: string | null;
	position: string;
	team: Team | null;
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
	awards: Award[] | null;
	allStarYear: number | null;
	active: boolean;
	seasonLabel: string | null;
	buildVersion: number | null;
}
export interface Team {
	code: string;
	name: string;
	city: string;
	seasonCode: string | null;
	logo: TeamLogo | null;
	colors: TeamColors | null;
}
/**
 * A team's logo: the one for a light background and, when the source has
 * one, the one for a dark background.
 */
export interface TeamLogo {
	light: string;
	dark: string | null;
}
export interface TeamColors {
	primary: string;
	secondary: string | null;
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
	opponent: Opponent;
	isHome: boolean;
	tag: GameTag | null;
	arena: string;
	city: string | null;
	broadcast: string | null;
	detailAvailable: boolean;
}
/**
 * A team a game is played against: a league team or a guest.
 */
export interface Opponent {
	code: string | null;
	name: string | null;
	city: string | null;
	guest: boolean;
	seasonCode: string | null;
	historical: boolean;
	logo: TeamLogo | null;
	colors: TeamColors | null;
}
export interface GameTag {
	kind: TagKind;
	conference: Conference | null;
	round: number | null;
	game: number | null;
}
export interface PlayerLive {
	gameId: string;
	opponent: Opponent;
	isHome: boolean;
	period: number;
	clock: string;
	teamScore: number;
	opponentScore: number;
	line: BoxScorePlayer | null;
}
export interface BoxScorePlayer {
	points: number | null;
	fieldGoalsMade: number | null;
	fieldGoalsAttempted: number | null;
	threePointsMade: number | null;
	threePointsAttempted: number | null;
	freeThrowsMade: number | null;
	freeThrowsAttempted: number | null;
	offensiveRebounds: number | null;
	defensiveRebounds: number | null;
	rebounds: number | null;
	assists: number | null;
	turnovers: number | null;
	steals: number | null;
	blocks: number | null;
	fouls: number | null;
	playerId: string;
	displayName: string;
	starter: boolean;
	minutes: string | null;
	plusMinus: number | null;
	photoUrl: string | null;
}
export interface GameLogEntry {
	gameId: string;
	date: string;
	opponent: Opponent | null;
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
	seasonCodes: (string | null)[] | null;
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
	code: AwardCode | null;
	team: number | null;
	count: number;
	/**
	 * @minItems 1
	 */
	seasons: [string, ...string[]];
}
