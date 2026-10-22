import type { TeamLogo } from '#lib/contract/games.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';

export type HeroPlayer = {
	firstName: string;
	lastName: string;
	shortName: string; // background word
	teamCode: string; // three letters
	teamName: string; // full team name, player strip
	photo: string; // image URL
};

/** A side of a hero game: its team mark, its identity from the feed and its star. */
export type HeroSide = TeamMarkTeam & {
	code: string;
	name: string;
	logo: TeamLogo | null; // null: the monogram
	accent: string | null; // null: the neutral accent
	star: HeroPlayer;
};

export type HeroStatus = 'tonight' | 'live' | 'final' | 'delayed' | 'postponed' | 'canceled';

export type HeroGame = {
	id: string; // the game id, passed back by Match details
	status: HeroStatus;
	tipTime: string; // already formatted, e.g. "10:30 PM ET"
	arena: string | null; // null: unknown, left out
	away: HeroSide;
	home: HeroSide;
};
