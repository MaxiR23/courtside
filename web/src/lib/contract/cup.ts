/**
 * Generated from api/schemas/cup.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type CupStage =
	'draw' | 'group' | 'quarterfinals' | 'semifinals' | 'championship' | 'complete';
export type CupRound = 'group' | 'quarterfinals' | 'semifinals' | 'championship';
export type StageStatus = 'complete' | 'in_progress' | 'next' | 'upcoming';
export type Conference = 'east' | 'west';
export type GameResult = 'win' | 'loss';
export type CupTag = 'won_group' | 'wild_card' | 'eliminated';
export type SlotId =
	'east-qf-1' | 'east-qf-2' | 'east-sf' | 'final' | 'west-sf' | 'west-qf-1' | 'west-qf-2';
export type SlotLabelKey = 'seed' | 'wild_card' | 'quarterfinal_winner' | 'semifinal_winner';
export type SlotRule =
	| 'best_group_winner'
	| 'second_best_group_winner'
	| 'third_best_group_winner'
	| 'best_non_winner'
	| 'quarterfinal_winner'
	| 'semifinal_winner';
export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';

export interface CupFeed {
	season: string;
	drawn: boolean;
	stage: CupStage;
	firstGameDate: string | null;
	groupGamesPlayed: number;
	groupGamesTotal: 60;
	champion: Opponent | null;
	defendingChampion: Opponent | null;
	/**
	 * @minItems 4
	 * @maxItems 4
	 */
	stages: [StageEntry, StageEntry, StageEntry, StageEntry];
	/**
	 * @minItems 6
	 * @maxItems 6
	 */
	groups: [CupGroup, CupGroup, CupGroup, CupGroup, CupGroup, CupGroup];
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	wildCard: [WildCardTable, WildCardTable];
	/**
	 * @minItems 7
	 * @maxItems 7
	 */
	bracket: [
		BracketSlot,
		BracketSlot,
		BracketSlot,
		BracketSlot,
		BracketSlot,
		BracketSlot,
		BracketSlot
	];
	games: CupGames;
	buildVersion: number | null;
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
export interface StageEntry {
	stage: CupRound;
	status: StageStatus;
	firstDate: string | null;
	lastDate: string | null;
}
export interface CupGroup {
	name: CupGroupName;
	/**
	 * @maxItems 5
	 */
	teams:
		| []
		| [Opponent]
		| [Opponent, Opponent]
		| [Opponent, Opponent, Opponent]
		| [Opponent, Opponent, Opponent, Opponent]
		| [Opponent, Opponent, Opponent, Opponent, Opponent];
	/**
	 * @maxItems 5
	 */
	rows:
		| []
		| [GroupRow]
		| [GroupRow, GroupRow]
		| [GroupRow, GroupRow, GroupRow]
		| [GroupRow, GroupRow, GroupRow, GroupRow]
		| [GroupRow, GroupRow, GroupRow, GroupRow, GroupRow];
	gamesFinal: number;
	final: boolean;
}
/**
 * The label of a Cup group: its conference and its letter. The one shape of
 * a group label in every feed that names a group.
 */
export interface CupGroupName {
	conference: Conference;
	letter: 'A' | 'B' | 'C';
}
export interface GroupRow {
	position: number | null;
	team: Opponent;
	wins: number;
	losses: number;
	gamesBehind: string | null;
	differential: PerGameDifferential | null;
	total: TotalDifferential | null;
	streak: Streak | null;
	pointsFor: number | null;
	pointsAgainst: number | null;
	home: string | null;
	away: string | null;
	overtime: string | null;
	tag: CupTag | null;
}
export interface PerGameDifferential {
	value: string;
	nonNegative: boolean;
}
export interface TotalDifferential {
	value: string;
	nonNegative: boolean;
}
export interface Streak {
	kind: GameResult;
	count: number;
}
export interface WildCardTable {
	conference: Conference;
	rows: WildCardRow[];
}
export interface WildCardRow {
	rank: number;
	team: Opponent;
	group: CupGroupName | null;
	wins: number;
	losses: number;
	total: TotalDifferential | null;
	pointsFor: number | null;
	tag: CupTag | null;
}
export interface BracketSlot {
	id: SlotId;
	round: CupRound;
	conference: Conference | null;
	top: SlotSide;
	bottom: SlotSide;
	game: CupGame | null;
}
export interface SlotSide {
	label: SlotLabel;
	rule: SlotRule;
	known: boolean;
	team: Opponent | null;
	projected: Projection | null;
	standing: SideStanding | null;
}
export interface SlotLabel {
	key: SlotLabelKey;
	conference: Conference;
	seed: number | null;
	quarterfinal: number | null;
}
export interface Projection {
	team: Opponent;
	wins: number;
	losses: number;
}
export interface SideStanding {
	seed: number | null;
	group: CupGroupName | null;
	wins: number;
	losses: number;
}
export interface CupGame {
	id: string;
	stage: CupRound;
	date: string;
	startTime: string;
	away: Opponent;
	home: Opponent;
	status: GameStatus;
	score: Score | null;
	winner: Side | null;
	period: number | null;
	broadcast: string | null;
	venue: string;
	city: string | null;
	neutralSite: boolean;
	countsInStandings: boolean;
	detailAvailable: boolean;
}
export interface Score {
	away: number;
	home: number;
}
export interface CupGames {
	days: CupDay[];
	counts: StageCounts;
}
export interface CupDay {
	date: string;
	/**
	 * @minItems 1
	 */
	games: [CupGame, ...CupGame[]];
}
export interface StageCounts {
	all: number;
	group: number;
	quarterfinals: number;
	semifinals: number;
	championship: number;
}
