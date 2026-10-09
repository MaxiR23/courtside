/**
 * Generated from api/schemas/standings.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type StandingsState = 'final' | 'regular';
export type Conference = 'east' | 'west';
export type Clinch = '*' | 'z' | 'y' | 'x' | 'xp' | 'pb' | 'e';
export type GameResult = 'win' | 'loss';

export interface StandingsFeed {
	season: string;
	state: StandingsState;
	gamesPlayed: number;
	conferences: ConferenceGroup[];
	divisions: DivisionGroup[];
}
export interface ConferenceGroup {
	key: Conference;
	name: string;
	teamCount: number;
	teams: StandingsRow[];
}
export interface StandingsRow {
	code: string;
	city: string;
	name: string;
	colors: StandingsColors;
	seed: number | null;
	clinch: Clinch | null;
	wins: number;
	losses: number;
	pct: string | null;
	gamesBehind: string | null;
	streak: Streak | null;
	home: string;
	away: string;
	lastTen: string;
	division: string;
	conference: string;
	pointsFor: string;
	pointsAgainst: string;
	differential: PerGameDifferential;
	total: TotalDifferential;
}
export interface StandingsColors {
	primary: string | null;
	secondary: string | null;
}
export interface Streak {
	kind: GameResult;
	count: number;
}
export interface PerGameDifferential {
	value: string;
	nonNegative: boolean;
}
export interface TotalDifferential {
	value: string;
	nonNegative: boolean;
}
export interface DivisionGroup {
	name: string;
	conference: Conference;
	/**
	 * @minItems 1
	 */
	teams: [StandingsRow, ...StandingsRow[]];
}
