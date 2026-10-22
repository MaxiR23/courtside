/**
 * Generated from api/schemas/all-star.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type AllStarState = 'before' | 'live' | 'after';
export type GameResult = 'win' | 'loss';
export type PlacementKind = 'champion' | 'runner_up' | 'eliminated' | 'so_far' | 'yet_to_play';
export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';
export type BroadcastKind = 'tv' | 'streaming';
export type TeamStatKind =
	'field_goal_pct' | 'three_points_made' | 'rebounds' | 'assists' | 'steals' | 'blocks';

export interface AllStarFeed {
	year: number;
	state: AllStarState;
	edition: AllStarEdition;
	mvp: AllStarMvp | null;
	previous: AllStarRecap | null;
	previousEdition: AllStarPreviousEdition | null;
	buildVersion: number | null;
}
export interface AllStarEdition {
	date: string | null;
	venue: Venue | null;
	format: AllStarFormat | null;
	teams: AllStarTeam[];
	games: AllStarGame[];
	counts: AllStarCounts;
	defaultGameId: string | null;
	editionHighlight: Highlight | null;
}
export interface Venue {
	name: string;
	city: string | null;
	photoUrl: string | null;
}
/**
 * The format of an edition's games: a target score (with untimed), or the
 * regulation periods and minutes. The page writes the words (ADR 0054).
 */
export interface AllStarFormat {
	targetPoints: number | null;
	untimed: boolean;
	periods: number | null;
	minutes: number | null;
}
export interface AllStarTeam {
	team: Opponent;
	wins: number;
	losses: number;
	results: AllStarTeamResult[];
	placement: Placement;
	roster: RosterTile[];
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
export interface AllStarTeamResult {
	gameId: string;
	roundLabel: string | null;
	result: GameResult;
	teamScore: number;
	opponentScore: number;
	opponent: Opponent;
	overtime: boolean;
}
export interface Placement {
	kind: PlacementKind;
	roundLabel: string | null;
}
export interface RosterTile {
	playerId: string;
	name: string;
	photoUrl: string | null;
	leagueTeam: LeagueTeam | null;
}
/**
 * The league team of a player, by its standard code, with its colors.
 */
export interface LeagueTeam {
	code: string;
	colors: StandingsColors;
	logo: TeamLogo | null;
}
export interface StandingsColors {
	primary: string | null;
	secondary: string | null;
}
export interface AllStarGame {
	id: string;
	startTime: string;
	status: GameStatus;
	statusText: string | null;
	clock: string | null;
	period: number | null;
	score: Score | null;
	overtime: boolean;
	winner: Side | null;
	leading: Side | null;
	attendance: number | null;
	broadcasts: Broadcast[];
	roundLabel: string | null;
	championship: boolean;
	isNext: boolean;
	away: Opponent | null;
	home: Opponent | null;
	toBeDetermined: boolean;
	boxScore: AllStarBoxScore | null;
	teamStats: AllStarTeamStat[] | null;
	leaders: Leaders | null;
	/**
	 * @maxItems 5
	 */
	top5:
		| []
		| [Top5Row]
		| [Top5Row, Top5Row]
		| [Top5Row, Top5Row, Top5Row]
		| [Top5Row, Top5Row, Top5Row, Top5Row]
		| [Top5Row, Top5Row, Top5Row, Top5Row, Top5Row];
	highlights: Highlight[] | null;
}
export interface Score {
	away: number;
	home: number;
}
export interface Broadcast {
	name: string;
	kind: BroadcastKind;
}
export interface AllStarBoxScore {
	away: AllStarTeamBox;
	home: AllStarTeamBox;
}
export interface AllStarTeamBox {
	players: AllStarBoxPlayer[];
	totals: BoxScoreTotals;
}
export interface AllStarBoxPlayer {
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
	jersey: string | null;
	position: string | null;
	leagueTeam: LeagueTeam | null;
	topPoints: boolean;
}
export interface BoxScoreTotals {
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
	fieldGoalPct: number | null;
	threePointPct: number | null;
	freeThrowPct: number | null;
}
export interface AllStarTeamStat {
	stat: TeamStatKind;
	away: number;
	home: number;
	better: Side | null;
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
export interface Top5Row {
	playerId: string;
	name: string;
	photoUrl: string | null;
	side: Side;
	leagueTeam: LeagueTeam | null;
	points: number | null;
	rebounds: number | null;
	assists: number | null;
}
export interface Highlight {
	title: string;
	channel: string;
	thumbnailUrl: string;
	embedUrl: string;
}
export interface AllStarCounts {
	games: number;
	teams: number;
	final: number;
	live: number;
}
export interface AllStarMvp {
	playerId: string;
	name: string;
	photoUrl: string | null;
	jersey: string | null;
	leagueTeam: LeagueTeam | null;
	/**
	 * @minItems 1
	 */
	lines: [MvpLine, ...MvpLine[]];
	totals: MvpTotals;
}
export interface MvpLine {
	gameId: string;
	roundLabel: string | null;
	result: GameResult;
	teamScore: number;
	opponentScore: number;
	opponent: Opponent;
	points: number | null;
	rebounds: number | null;
	assists: number | null;
}
export interface MvpTotals {
	games: number;
	points: number | null;
	rebounds: number | null;
	assists: number | null;
}
export interface AllStarRecap {
	year: number;
	date: string;
	venue: Venue | null;
	championship: AllStarResult;
	mvp: AllStarMvp | null;
	editionHighlight: Highlight | null;
}
export interface AllStarResult {
	gameId: string;
	away: Opponent;
	home: Opponent;
	score: Score;
	winner: Side;
	overtime: boolean;
}
/**
 * The previous edition drawn as its after view: the edition and its MVP.
 */
export interface AllStarPreviousEdition {
	date: string | null;
	venue: Venue | null;
	format: AllStarFormat | null;
	teams: AllStarTeam[];
	games: AllStarGame[];
	counts: AllStarCounts;
	defaultGameId: string | null;
	editionHighlight: Highlight | null;
	mvp: AllStarMvp | null;
}
