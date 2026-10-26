/**
 * Generated from api/schemas/power-ranking.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type PowerRankingState = 'available' | 'unavailable';

export interface PowerRankingFeed {
	season: string;
	state: PowerRankingState;
	teams: PowerRankingTeam[];
}
export interface PowerRankingTeam {
	rank: number;
	tied: boolean;
	team: PowerRankingIdentity;
	record: string;
	rating: string;
	ratingNegative: boolean;
	offense: string;
	defense: string;
	projected: string;
	playoffs: string;
	title: string;
	playoffsLow: boolean;
	titleShare: number;
}
export interface PowerRankingIdentity {
	code: string;
	name: string | null;
	city: string | null;
	logo: TeamLogo | null;
	colors: TeamColors | null;
	accent: string | null;
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
