/**
 * Generated from api/schemas/home.schema.json by scripts/contract.sh.
 * Do not edit by hand: run scripts/contract.sh instead.
 */

export type HomeScenario = 'offDay' | 'allStarBreak' | 'finalsPreview' | 'offseason';
export type ComingUpKey =
	| 'openingNight'
	| 'cupGroupStage'
	| 'cupKnockout'
	| 'cupFinal'
	| 'allStar'
	| 'playIn'
	| 'playoffs'
	| 'finals'
	| 'preseason';
export type ComingUpStatus = 'done' | 'now' | 'upcoming';
export type LastGamesTitleKey =
	'lastNight' | 'daysAgo' | 'beforeTheBreak' | 'conferenceFinals' | 'lastGamesPlayed';
export type Side = 'away' | 'home';
export type LastGameLabel =
	| 'final'
	| 'finalOvertime'
	| 'playIn'
	| 'firstRound'
	| 'conferenceSemifinals'
	| 'conferenceFinals'
	| 'finals';
export type HomeLeadersTitle = 'season' | 'playoffs' | 'previousSeason';
export type HomeLeaderCategory = 'points' | 'rebounds' | 'assists' | 'blocks';
export type PathRound = 'firstRound' | 'conferenceSemifinals' | 'conferenceFinals';

export interface HomeFeed {
	season: string;
	date: string;
	scenario: HomeScenario;
	comingUp: [ComingUpItem, ...ComingUpItem[]] | null;
	nextGame: NextGame | null;
	lastGames: LastGames | null;
	leaders: HomeLeaders | null;
	finalsPath: FinalsPath | null;
}
export interface ComingUpItem {
	key: ComingUpKey;
	startDate: string;
	endDate: string | null;
	status: ComingUpStatus;
}
export interface NextGame {
	date: string;
	firstTipOff: string;
	broadcast: string | null;
	gameCount: number;
	inGamesWindow: boolean;
}
export interface LastGames {
	date: string;
	title: LastGamesTitle;
	/**
	 * @minItems 1
	 */
	games: [LastGame, ...LastGame[]];
}
export interface LastGamesTitle {
	key: LastGamesTitleKey;
	days: number | null;
}
export interface LastGame {
	id: string;
	away: Opponent;
	home: Opponent;
	score: Score;
	winner: Side | null;
	label: LastGameLabel;
	gameNumber: number | null;
	accent: GameAccent | null;
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
/**
 * The color each side of a game shows in the hero (ADR 0068); null for a
 * side with no colors.
 */
export interface GameAccent {
	away: string | null;
	home: string | null;
}
export interface HomeLeaders {
	title: HomeLeadersTitle;
	seasonLabel: string | null;
	/**
	 * @minItems 1
	 * @maxItems 4
	 */
	categories:
		| [HomeLeader]
		| [HomeLeader, HomeLeader]
		| [HomeLeader, HomeLeader, HomeLeader]
		| [HomeLeader, HomeLeader, HomeLeader, HomeLeader];
}
export interface HomeLeader {
	category: HomeLeaderCategory;
	playerId: string;
	name: string;
	photoUrl: string | null;
	team: HomeLeaderTeam | null;
	value: string;
}
export interface HomeLeaderTeam {
	code: string;
	logo: TeamLogo | null;
	colors: TeamColors | null;
	accent: string | null;
}
export interface FinalsPath {
	/**
	 * @minItems 2
	 * @maxItems 2
	 */
	finalists: [FinalistPath, FinalistPath];
}
export interface FinalistPath {
	team: Opponent;
	accent: string | null;
	/**
	 * @minItems 3
	 * @maxItems 3
	 */
	series: [PathSeries, PathSeries, PathSeries];
}
export interface PathSeries {
	round: PathRound;
	opponent: Opponent;
	result: string;
	won: boolean;
	accent: string | null;
}
