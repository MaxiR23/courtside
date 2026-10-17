/**
 * Generated from api/schemas/playoffs.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type PlayoffsState = 'picture' | 'playin' | 'playoffs' | 'finals' | 'complete';
export type PlayoffStage = 'playin' | 'round_1' | 'round_2' | 'round_3' | 'finals';
export type PlayoffStageStatus = 'complete' | 'in_progress' | 'next' | 'upcoming';
export type Conference = 'east' | 'west';
export type Clinch = '*' | 'z' | 'y' | 'x' | 'xp' | 'pb' | 'e';
export type PictureLine = 'playoffs' | 'playin';
export type PlayInGameKind = 'seven_eight' | 'nine_ten' | 'eighth_seed';
export type PlayInSlotKey = 'place' | 'loser_of' | 'winner_of';
export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';
export type SeriesId =
	| 'east-r1-1'
	| 'east-r1-2'
	| 'east-r1-3'
	| 'east-r1-4'
	| 'east-r2-1'
	| 'east-r2-2'
	| 'east-r3'
	| 'finals'
	| 'west-r3'
	| 'west-r2-1'
	| 'west-r2-2'
	| 'west-r1-1'
	| 'west-r1-2'
	| 'west-r1-3'
	| 'west-r1-4';
export type SeriesLabelKey =
	'seed' | 'playin_winner' | 'round_1_winner' | 'round_2_winner' | 'round_3_winner';
export type SeriesStatus = 'upcoming' | 'in_progress' | 'complete';
export type LeaderCategory =
	| 'points'
	| 'rebounds'
	| 'assists'
	| 'steals'
	| 'blocks'
	| 'field_goal_pct'
	| 'threes_made'
	| 'double_doubles'
	| 'minutes';
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

export interface PlayoffsFeed {
	season: string;
	state: PlayoffsState;
	postseasonDates: DateSpan;
	currentRound: number | null;
	finalsGame: number | null;
	finalsSummary: string | null;
	/**
	 * @minItems 5
	 * @maxItems 5
	 */
	stages: [
		PlayoffStageEntry,
		PlayoffStageEntry,
		PlayoffStageEntry,
		PlayoffStageEntry,
		PlayoffStageEntry
	];
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	picture: [PictureTable, PictureTable];
	playIn: [PlayIn, PlayIn] | null;
	/**
	 * @minItems 15
	 * @maxItems 15
	 */
	bracket: [
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series,
		Series
	];
	champion: Champion | null;
	leaders:
		| [
				LeaderGroup,
				LeaderGroup,
				LeaderGroup,
				LeaderGroup,
				LeaderGroup,
				LeaderGroup,
				LeaderGroup,
				LeaderGroup,
				LeaderGroup
		  ]
		| null;
	awards: Award[] | null;
	buildVersion: number | null;
}
export interface DateSpan {
	firstDate: string;
	lastDate: string;
}
export interface PlayoffStageEntry {
	stage: PlayoffStage;
	status: PlayoffStageStatus;
	firstDate: string | null;
	lastDate: string | null;
}
export interface PictureTable {
	conference: Conference;
	/**
	 * @maxItems 10
	 */
	rows:
		| []
		| [PictureRow]
		| [PictureRow, PictureRow]
		| [PictureRow, PictureRow, PictureRow]
		| [PictureRow, PictureRow, PictureRow, PictureRow]
		| [PictureRow, PictureRow, PictureRow, PictureRow, PictureRow]
		| [PictureRow, PictureRow, PictureRow, PictureRow, PictureRow, PictureRow]
		| [PictureRow, PictureRow, PictureRow, PictureRow, PictureRow, PictureRow, PictureRow]
		| [
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow
		  ]
		| [
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow
		  ]
		| [
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow,
				PictureRow
		  ];
}
export interface PictureRow {
	seed: number | null;
	team: PlayoffTeam;
	wins: number | null;
	losses: number | null;
	gamesBehind: string | null;
	clinch: Clinch | null;
	line: PictureLine | null;
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
	colors: StandingsColors;
}
export interface StandingsColors {
	primary: string | null;
	secondary: string | null;
}
export interface PlayIn {
	conference: Conference;
	/**
	 * @minItems 3
	 * @maxItems 3
	 */
	games: [PlayInGame, PlayInGame, PlayInGame];
}
export interface PlayInGame {
	kind: PlayInGameKind;
	top: PlayInSlot;
	bottom: PlayInSlot;
	game: PlayoffGame | null;
	outcome: PlayInOutcome | null;
}
export interface PlayInSlot {
	label: PlayInSlotLabel;
	team: PlayoffTeam | null;
	currently: PlayoffTeam | null;
}
export interface PlayInSlotLabel {
	key: PlayInSlotKey;
	place: number | null;
	game: PlayInGameKind | null;
}
export interface PlayoffGame {
	id: string;
	date: string;
	startTime: string;
	away: Opponent;
	home: Opponent;
	status: GameStatus;
	score: Score | null;
	winner: Side | null;
	overtime: boolean;
	venue: string;
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
}
export interface Score {
	away: number;
	home: number;
}
export interface PlayInOutcome {
	seed: (7 | 8) | null;
	loserOut: boolean;
}
export interface Series {
	id: SeriesId;
	round: number;
	conference: Conference | null;
	top: SeriesSide;
	bottom: SeriesSide;
	status: SeriesStatus;
	summary: string | null;
	winner: string | null;
	/**
	 * @maxItems 7
	 */
	games:
		| []
		| [SeriesGame]
		| [SeriesGame, SeriesGame]
		| [SeriesGame, SeriesGame, SeriesGame]
		| [SeriesGame, SeriesGame, SeriesGame, SeriesGame]
		| [SeriesGame, SeriesGame, SeriesGame, SeriesGame, SeriesGame]
		| [SeriesGame, SeriesGame, SeriesGame, SeriesGame, SeriesGame, SeriesGame]
		| [SeriesGame, SeriesGame, SeriesGame, SeriesGame, SeriesGame, SeriesGame, SeriesGame];
}
export interface SeriesSide {
	label: SeriesLabel;
	team: PlayoffTeam | null;
	seed: number | null;
	wins: number | null;
	currently: PlayoffTeam | null;
}
export interface SeriesLabel {
	key: SeriesLabelKey;
	conference: Conference;
	seed: number | null;
	series: number | null;
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
	venue: string;
	broadcast: string | null;
	detailAvailable: boolean;
	number: number;
}
export interface Champion {
	team: PlayoffTeam;
	wins: 4;
	losses: number;
	firstDate: string;
	lastDate: string;
	record: string | null;
	home: string | null;
	road: string | null;
	pointDifferential: TotalDifferential;
}
export interface TotalDifferential {
	value: string;
	nonNegative: boolean;
}
export interface LeaderGroup {
	category: LeaderCategory;
	/**
	 * @maxItems 5
	 */
	leaders:
		| []
		| [PlayoffLeader]
		| [PlayoffLeader, PlayoffLeader]
		| [PlayoffLeader, PlayoffLeader, PlayoffLeader]
		| [PlayoffLeader, PlayoffLeader, PlayoffLeader, PlayoffLeader]
		| [PlayoffLeader, PlayoffLeader, PlayoffLeader, PlayoffLeader, PlayoffLeader];
}
export interface PlayoffLeader {
	rank: number;
	playerId: string;
	name: string;
	photoUrl: string | null;
	teamCode: string;
	seasonCode: string | null;
	value: string;
}
export interface Award {
	code: AwardCode;
	team: number | null;
	/**
	 * @minItems 1
	 */
	winners: [AwardWinner, ...AwardWinner[]];
}
export interface AwardWinner {
	playerId: string;
	name: string;
	photoUrl: string | null;
	teamCode: string | null;
	seasonCode: string | null;
}
