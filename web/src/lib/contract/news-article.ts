/**
 * Generated from api/schemas/news-article.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type NewsLanguage = 'en' | 'es';
export type NewsKind = 'news' | 'recap';

export interface NewsArticleFeed {
	note: NewsNote | null;
	game: NewsGame | null;
}
export interface NewsNote {
	id: string;
	language: NewsLanguage;
	kind: NewsKind;
	headline: string;
	description: string | null;
	published: string;
	photo: NewsPhoto | null;
	teams: string[];
	players: NewsPlayer[];
	gameId: string | null;
}
export interface NewsPhoto {
	url: string;
	width: number;
	height: number;
	credit: string | null;
}
export interface NewsPlayer {
	playerId: string;
	name: string;
}
export interface NewsGame {
	id: string;
	away: Opponent;
	home: Opponent;
	score: Score | null;
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
export interface Score {
	away: number;
	home: number;
}
