/**
 * Generated from api/schemas/search.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type InjuryStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';

export interface SearchFeed {
	/**
	 * @minItems 30
	 * @maxItems 30
	 */
	teams: [
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam,
		SearchTeam
	];
	players: SearchPlayer[];
}
export interface SearchTeam {
	code: string;
	city: string;
	name: string;
	colors: StandingsColors;
	record: string;
	division: string;
	divisionRank: number | null;
}
export interface StandingsColors {
	primary: string | null;
	secondary: string | null;
}
export interface SearchPlayer {
	id: string;
	name: string;
	shortName: string;
	number: string | null;
	position: string | null;
	positionAbbr: string | null;
	photoUrl: string | null;
	injury: SearchInjury | null;
	team: SearchPlayerTeam;
}
export interface SearchInjury {
	status: InjuryStatus;
}
export interface SearchPlayerTeam {
	code: string;
	primary: string | null;
}
