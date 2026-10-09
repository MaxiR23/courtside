import type { HeroPlayer } from '#lib/hero/types.ts';

export type ScheduleTeam = {
	code: string; // three letters, monogram
	name: string; // e.g. "Warriors"
	city: string; // e.g. "Golden State", muted
	guest?: boolean; // a team outside the league: no link (ADR 0025)
};

export type GameStatus =
	| { state: 'scheduled'; tipTime: string; tipSuffix: string; network: string | null } // "9:00", "PM ET", already formatted; no network when unknown
	| { state: 'live'; period: string; clock: string; awayScore: number; homeScore: number } // "Q3", "4:12", already formatted
	| { state: 'final'; awayScore: number; homeScore: number; winner: string } // winner: the winning team's code, from the feed
	| { state: 'delayed' | 'postponed' | 'canceled' }; // no score, no tip time

export type PanelPlayer = Pick<HeroPlayer, 'firstName' | 'lastName' | 'teamCode'> & {
	photo: string | null; // null: no photo, so initials
};

export type Leader = PanelPlayer & {
	points: number;
	rebounds: number;
	assists: number;
	guest?: boolean; // a player of a team outside the league: no team link
};

export type TeamStatLine = {
	fieldGoalPct: number; // 0 to 1
	threePointPct: number; // 0 to 1
	rebounds: number;
	assists: number;
	turnovers: number;
};

export type HighlightVideo = {
	id: string; // unique within its game
	title: string;
	channel: string;
	thumbnail: string; // image URL, provided with each highlight
	embedUrl: string; // embedded player URL, already set to autoplay by the props layer
};

export type GameHighlights = {
	platform: string; // the video platform's name, shown next to the kicker
	searchUrl: string; // where the pending state's link searches for the highlights
	videos: HighlightVideo[]; // empty until the highlights are in
};

export type GameDetails =
	| {
			kind: 'scheduled';
			venue: string;
			playersToWatch: { away: PanelPlayer | null; home: PanelPlayer | null };
	  } // null: a guest team has no star
	| {
			kind: 'played'; // live or final
			periods: { away: number[]; home: number[] }; // points per period played so far, overtime included
			leaders: { away: Leader; home: Leader };
			stats: { away: TeamStatLine; home: TeamStatLine };
			highlights?: GameHighlights; // shown on final games only
	  }
	| {
			kind: 'final-without-stats'; // a final game whose top performers and team stats are not in
			periods: { away: number[]; home: number[] };
			statsAvailability: 'pending' | 'unavailable';
			highlights?: GameHighlights;
	  };

export type ScheduleGame = {
	id: string;
	away: ScheduleTeam;
	home: ScheduleTeam;
	status: GameStatus;
	details?: GameDetails; // panel data; a card without it does not expand
};

export type ScheduleDay = { date: Date; games: ScheduleGame[] };

export type RowLayout = 'desktop' | 'mobile';
