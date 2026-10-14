/**
 * Generated from api/schemas/all-star.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type AllStarState = 'before' | 'live' | 'after';
export type PlacementKind = 'champion' | 'runner_up' | 'eliminated' | 'so_far' | 'yet_to_play';
export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';
export type BroadcastKind = 'tv' | 'streaming';
export type TeamStatKind =
	'field_goal_pct' | 'three_points_made' | 'rebounds' | 'assists' | 'steals' | 'blocks';
export type GameResult = 'win' | 'loss';

export interface AllStarFeed {
	year: number;
	state: AllStarState;
	edition: AllStarEdition;
	mvp: AllStarMvp | null;
	previous: AllStarRecap | null;
}
export interface AllStarEdition {
	date: string | null;
	venue: Venue | null;
	formatLine: string | null;
	teams: AllStarTeam[];
	games: AllStarGame[];
}
export interface Venue {
	name: string;
	city: string | null;
	photoUrl: string | null;
}
export interface AllStarTeam {
	team: Opponent;
	wins: number;
	losses: number;
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
	attendance: number | null;
	broadcasts: Broadcast[];
	roundLabel: string | null;
	championship: boolean;
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
	jersey: string | null;
	position: string | null;
	leagueTeam: LeagueTeam | null;
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
	points: number;
	rebounds: number;
	assists: number;
}
export interface Top5Row {
	playerId: string;
	name: string;
	photoUrl: string | null;
	side: Side;
	leagueTeam: LeagueTeam | null;
	points: number;
	rebounds: number;
	assists: number;
}
export interface Highlight {
	title: string;
	channel: string;
	thumbnailUrl: string;
	embedUrl: string;
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
	points: number;
	rebounds: number;
	assists: number;
}
export interface MvpTotals {
	games: number;
	points: number;
	rebounds: number;
	assists: number;
}
export interface AllStarRecap {
	year: number;
	date: string;
	venue: Venue | null;
	championship: AllStarResult;
	mvp: AllStarMvp | null;
}
export interface AllStarResult {
	gameId: string;
	away: Opponent;
	home: Opponent;
	score: Score;
	winner: Side;
	overtime: boolean;
}
