/**
 * Generated from api/schemas/team.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type Conference = 'east' | 'west';
export type GameResult = 'win' | 'loss';
export type PlayoffStatus = 'seed' | 'playin' | 'out';
export type InjuryStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';
export type TagKind = 'cup' | 'playoffs' | 'allstar';
export type GameKind = 'regular' | 'cup' | 'playoffs' | 'allstar';

export interface TeamFeed {
	code: string;
	city: string;
	name: string;
	conference: Conference;
	division: string;
	colors: TeamColors;
	arena: Venue;
	coach: Coach | null;
	season: string;
	record: TeamRecord;
	leaders: TeamLeaders;
	roster: RosterPlayer[];
	injuries: TeamInjury[];
	nextGame: NextGame | null;
	schedule: Schedule | null;
}
export interface TeamColors {
	primary: string;
	secondary: string;
}
export interface Venue {
	name: string;
	city: string | null;
	photoUrl: string | null;
}
export interface Coach {
	name: string;
	seasons: number | null;
}
export interface TeamRecord {
	wins: number;
	losses: number;
	winPct: number;
	home: SplitRecord;
	away: SplitRecord;
	lastTen: SplitRecord;
	streak: Streak | null;
	gamesBehind: number;
	conferenceRank: number;
	divisionRank: number;
	playoff: PlayoffPosition | null;
	pointsFor: PointsTotal;
	pointsAgainst: PointsTotal;
	differential: Differential;
}
export interface SplitRecord {
	wins: number;
	losses: number;
	winPct: number;
}
export interface Streak {
	kind: GameResult;
	count: number;
}
export interface PlayoffPosition {
	status: PlayoffStatus;
	seed: number;
}
export interface PointsTotal {
	perGame: number;
	total: number;
}
export interface Differential {
	perGame: number;
	total: number;
}
export interface TeamLeaders {
	season: string;
	points: TeamLeader | null;
	rebounds: TeamLeader | null;
	assists: TeamLeader | null;
}
export interface TeamLeader {
	playerId: string;
	name: string;
	number: string | null;
	position: string;
	photoUrl: string | null;
	value: number;
}
export interface RosterPlayer {
	id: string;
	name: string;
	number: string | null;
	position: string | null;
	height: string | null;
	weight: number | null;
	age: number | null;
	birthDate: string | null;
	birthplace: string | null;
	college: string | null;
	experience: number | null;
	photoUrl: string | null;
	status: 'active' | InjuryStatus;
}
export interface TeamInjury {
	playerId: string;
	name: string;
	number: string | null;
	position: string | null;
	status: InjuryStatus;
	comment: string | null;
	updatedAt: string;
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
export interface Schedule {
	/**
	 * @minItems 1
	 */
	groups: [ScheduleGroup, ...ScheduleGroup[]];
	defaultGroup: string;
}
export interface ScheduleGroup {
	key: string;
	/**
	 * @minItems 1
	 */
	games: [ScheduleGame, ...ScheduleGame[]];
}
export interface ScheduleGame {
	gameId: string;
	startTime: string;
	opponent: string;
	isHome: boolean;
	kind: GameKind;
	tag: GameTag | null;
	result: GameResult | null;
	teamScore: number | null;
	opponentScore: number | null;
	broadcast: string | null;
	isNext: boolean;
	detailAvailable: boolean;
}
