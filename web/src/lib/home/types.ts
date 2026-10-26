import type { ComingUpStatus } from '#lib/contract/home.ts';

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
