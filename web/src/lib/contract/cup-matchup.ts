/**
 * Generated from api/schemas/cup-matchup.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type SlotId =
	'east-qf-1' | 'east-qf-2' | 'east-sf' | 'final' | 'west-sf' | 'west-qf-1' | 'west-qf-2';
export type CupRound = 'group' | 'quarterfinals' | 'semifinals' | 'championship';
export type Conference = 'east' | 'west';
export type GameStatus = 'scheduled' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';
export type Side = 'away' | 'home';
export type SlotLabelKey = 'seed' | 'wild_card' | 'quarterfinal_winner' | 'semifinal_winner';
export type SlotRule =
	| 'best_group_winner'
	| 'second_best_group_winner'
	| 'third_best_group_winner'
	| 'best_non_winner'
	| 'quarterfinal_winner'
	| 'semifinal_winner';
export type GameResult = 'win' | 'loss';
export type InjuryStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';

export interface CupMatchupFeed {
	season: string;
	id: SlotId;
	round: CupRound;
	conference: Conference | null;
	game: CupGame | null;
	top: MatchupSide;
	bottom: MatchupSide;
	buildVersion: number | null;
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
export interface MatchupSide {
	label: SlotLabel;
	rule: SlotRule;
	known: boolean;
	projected: boolean;
	team: Opponent | null;
	details: MatchupTeam | null;
}
export interface SlotLabel {
	key: SlotLabelKey;
	conference: Conference;
	seed: number | null;
	quarterfinal: number | null;
}
export interface MatchupTeam {
	path: PathGame[];
	injuries: TeamInjury[];
	roster: MatchupPlayer[];
}
export interface PathGame {
	gameId: string;
	stage: CupRound;
	startTime: string;
	opponent: Opponent;
	isHome: boolean;
	status: GameStatus;
	result: GameResult | null;
	teamScore: number | null;
	opponentScore: number | null;
	detailAvailable: boolean;
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
export interface MatchupPlayer {
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
	averages: PerGameAverages | null;
	starter: boolean;
	leader: StatLeaders;
}
export interface PerGameAverages {
	points: number;
	rebounds: number;
	assists: number;
}
export interface StatLeaders {
	points: boolean;
	rebounds: boolean;
	assists: boolean;
}
