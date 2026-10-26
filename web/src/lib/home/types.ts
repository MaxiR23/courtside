import type { ComingUpStatus } from '#lib/contract/home.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';

/** Where a Coming up item links; null: no page (Opening Night, preseason). */
export type ComingUpTarget = 'cup' | 'allStar' | 'playoffs';

export type ComingUpItemView = {
	key: string; // the feed key, for the each-block key
	date: string; // "Nov 4" or "Nov 4 – Dec 3"
	title: string;
	sub: string;
	status: ComingUpStatus;
	statusLabel: string; // Done / Now / Upcoming
	target: ComingUpTarget | null;
};

export type NoGamesView = {
	date: string; // today of the games feed, "Sunday, October 4"
	tag: string | null; // the scenario chip; null without the home feed
	paragraph: string | null; // null without the home feed
	nextTipOff: string | null; // null when nextGame is null or without the home feed
	broadcast: string | null; // nextGame.broadcast; null when unknown
	comingUp: ComingUpItemView[] | null; // null outside the window or without the home feed
};

export type HomeLastGameSideView = {
	team: TeamMarkTeam; // through teamMark(): code, name, city, guest, logo
	score: number;
	loser: boolean; // the feed's winner is the other side; false when winner is null
	accent: string | null; // the feed's resolved color; null: the neutral accent
};

export type HomeLastGameView = {
	id: string; // the game page id
	label: string; // "Final", "Final/OT", "Play-In", "First round · Game 3"
	away: HomeLastGameSideView;
	home: HomeLastGameSideView;
};

export type HomeLastGamesView = {
	title: string; // "Last night", "3 days ago", ...
	count: string; // "2 games"
	games: HomeLastGameView[];
};

export type EmptyDayView = {
	title: string; // "No games on this day"
	text: string; // "Next games: Tue, Oct 6 · 5 games" or the two-weeks message
	goTo: { date: string; label: string } | null; // date 'YYYY-MM-DD'; null: outside the games feed window or no next game
};

export type HomeStandingsRowView = {
	code: string; // the each-block key
	seed: string; // "1", or "—" when the feed has no seed
	team: TeamMarkTeam; // logo, else the code
	record: string; // "34–7"
	gamesBehind: string; // "1.0", or "—" for the leader
};

export type HomeConferenceTabView = {
	key: string; // "east" | "west"
	label: string; // "East"
	rows: HomeStandingsRowView[]; // the first 6 rows in feed order
	playIn: HomeStandingsRowView[]; // rows 7 to 10 in feed order; empty: no footnote
};

export type HomePathSeriesView = {
	key: string; // the round key, for the each-block key
	round: string; // "First round"
	opponent: TeamMarkTeam;
	accent: string | null; // the opponent's resolved color; null: the neutral accent
	result: string; // "4–2", from the finalist's side
	won: boolean;
};

export type HomeFinalistTabView = {
	key: string; // the team code, else "finalist-0" / "finalist-1"
	team: TeamMarkTeam;
	series: HomePathSeriesView[]; // three, in round order
};

export type HomeStandingsView =
	| { kind: 'standings'; title: string; tabs: HomeConferenceTabView[] }
	| { kind: 'finalsPath'; title: string; tabs: HomeFinalistTabView[] };

export type HomeLeaderView = {
	key: string; // the category key
	category: string; // "Points per game"
	team: TeamMarkTeam | null; // null: no team link in the feed
	name: string; // a dash when the identity was not read
	photo: string | null; // null: the empty photo box
	value: string; // "31.4"
};

export type HomeLeadersView = {
	title: string; // "This season", "Playoffs", "2025-26 season"
	leaders: HomeLeaderView[]; // feed order, one to four
};
