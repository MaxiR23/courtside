/**
 * Generated from api/schemas/team.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type Conference = 'east' | 'west';
export type GameResult = 'win' | 'loss';
export type PlayoffStatus = 'seed' | 'playin' | 'out';
export type InjuryStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';
export type TagKind = 'cup' | 'playoffs' | 'allstar';
export type GameKind = 'regular' | 'cup' | 'playoffs' | 'allstar' | 'preseason';
export type TitleKind = 'nba_champions' | 'nba_cup_champions' | 'conference_champions';

export interface TeamFeed {
	code: string;
	city: string;
	name: string;
	conference: Conference;
	division: string;
	colors: TeamColors;
	arena: Venue | null;
	coach: Coach | null;
	season: string;
	record: TeamRecord;
	leaders: TeamLeaders;
	roster: RosterPlayer[];
	injuries: TeamInjury[] | null;
	nextGame: NextGame | null;
	schedule: Schedule | null;
	cup: TeamCup | null;
	titles: [TeamTitle] | [TeamTitle, TeamTitle] | [TeamTitle, TeamTitle, TeamTitle] | null;
	names: NameRun[];
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
	season: string;
	home: SplitRecord;
	away: SplitRecord;
	lastTen: SplitRecord;
	streak: Streak | null;
	gamesBehind: number | null;
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
	opponent: Opponent;
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
/**
 * The Cup mark of a team: its group and its Cup record.
 */
export interface TeamCup {
	group: CupGroupName;
	wins: number;
	losses: number;
}
/**
 * The label of a Cup group: its conference and its letter. The one shape of
 * a group label in every feed that names a group.
 */
export interface CupGroupName {
	conference: Conference;
	letter: 'A' | 'B' | 'C';
}
/**
 * A title the team won in the current season.
 */
export interface TeamTitle {
	kind: TitleKind;
	year: number | null;
	conference: Conference | null;
}
/**
 * One identity of the franchise: its name, city and code from one season to
 * another. `to` is null on the run that holds the current season.
 */
export interface NameRun {
	from: number;
	to: number | null;
	name: string;
	location: string;
	code: string;
}
