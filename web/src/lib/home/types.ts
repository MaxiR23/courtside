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
