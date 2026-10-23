/**
 * Generated from api/schemas/playoffs-finals.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type SeriesStatus = 'upcoming' | 'in_progress' | 'complete';
export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';
export type GameResult = 'win' | 'loss';
export type HeadToHeadStat =
	| 'points'
	| 'field_goal_pct'
	| 'effective_fg_pct'
	| 'assists'
	| 'rebounds'
	| 'blocks'
	| 'steals'
	| 'technical_fouls';

export interface PlayoffsFinalsFeed {
	season: string;
	status: SeriesStatus;
	champion: string | null;
	curveTeam: string;
	/**
	 * @maxItems 7
	 */
	games:
		| []
		| [FinalsGame]
		| [FinalsGame, FinalsGame]
		| [FinalsGame, FinalsGame, FinalsGame]
		| [FinalsGame, FinalsGame, FinalsGame, FinalsGame]
		| [FinalsGame, FinalsGame, FinalsGame, FinalsGame, FinalsGame]
		| [FinalsGame, FinalsGame, FinalsGame, FinalsGame, FinalsGame, FinalsGame]
		| [FinalsGame, FinalsGame, FinalsGame, FinalsGame, FinalsGame, FinalsGame, FinalsGame];
	finalsMvp: FinalsMvp | null;
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	road: [RoadTeam, RoadTeam];
	headToHead: HeadToHead;
	averages: [RosterAverages, RosterAverages] | null;
	buildVersion: number | null;
}
export interface FinalsGame {
	game: SeriesGame;
	leaders: Leaders | null;
	winProbability: FinalsWinProbability | null;
	largestDeficit: LargestDeficit | null;
	highlights: Highlight[] | null;
}
export interface SeriesGame {
	id: string;
	date: string;
	startTime: string;
	away: Opponent;
	home: Opponent;
	status: GameStatus;
	score: Score | null;
	winner: Side | null;
	overtime: boolean;
	venue: string | null;
	broadcast: string | null;
	detailAvailable: boolean;
	number: number;
	overtimePeriods: number | null;
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
	points: number | null;
	rebounds: number | null;
	assists: number | null;
}
export interface FinalsWinProbability {
	/**
	 * @minItems 1
	 */
	points: [TeamWinProbabilityPoint, ...TeamWinProbabilityPoint[]];
	periods: WinProbabilityPeriods;
}
export interface TeamWinProbabilityPoint {
	elapsedSeconds: number;
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
export interface LargestDeficit {
	points: number;
	elapsedSeconds: number;
}
export interface Highlight {
	title: string;
	channel: string;
	thumbnailUrl: string;
	embedUrl: string;
}
export interface FinalsMvp {
	playerId: string;
	name: string;
	photoUrl: string | null;
	teamCode: string | null;
	seasonCode: string | null;
	accent: string | null;
	games: number | null;
	points: number | null;
	rebounds: number | null;
	assists: number | null;
	bestGame: BestGame | null;
}
export interface BestGame {
	gameId: string;
	number: number;
	points: number;
}
export interface RoadTeam {
	team: PlayoffTeam;
	seed: number | null;
	regularSeason: string | null;
	postseason: string | null;
	/**
	 * @maxItems 4
	 */
	series:
		| []
		| [RoadSeries]
		| [RoadSeries, RoadSeries]
		| [RoadSeries, RoadSeries, RoadSeries]
		| [RoadSeries, RoadSeries, RoadSeries, RoadSeries];
}
/**
 * A league team of the postseason with its colors.
 */
export interface PlayoffTeam {
	code: string | null;
	name: string | null;
	city: string | null;
	guest: boolean;
	seasonCode: string | null;
	historical: boolean;
	logo: TeamLogo | null;
	colors: StandingsColors;
}
export interface StandingsColors {
	primary: string | null;
	secondary: string | null;
}
export interface RoadSeries {
	round: number;
	opponent: PlayoffTeam;
	opponentSeed: number | null;
	wins: number | null;
	losses: number | null;
	result: GameResult | null;
}
export interface HeadToHead {
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	records: [FinalistRecord, FinalistRecord];
	/**
	 * @minItems 8
	 * @maxItems 8
	 */
	bars: [
		HeadToHeadBar,
		HeadToHeadBar,
		HeadToHeadBar,
		HeadToHeadBar,
		HeadToHeadBar,
		HeadToHeadBar,
		HeadToHeadBar,
		HeadToHeadBar
	];
}
export interface FinalistRecord {
	teamCode: string;
	seasonCode: string | null;
	record: string | null;
}
export interface HeadToHeadBar {
	stat: HeadToHeadStat;
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	values: [BarValue, BarValue];
	better: string | null;
}
export interface BarValue {
	teamCode: string;
	value: number | null;
}
export interface RosterAverages {
	teamCode: string;
	seasonCode: string | null;
	players: PlayerPostseasonAverages[];
}
export interface PlayerPostseasonAverages {
	playerId: string;
	name: string;
	photoUrl: string | null;
	points: number | null;
	rebounds: number | null;
	assists: number | null;
	blocks: number | null;
	fieldGoalPct: number | null;
}
