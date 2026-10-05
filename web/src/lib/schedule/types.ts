import type { HeroPlayer } from '#lib/hero/types.ts';

export type ScheduleTeam = {
	code: string; // three letters, monogram
	name: string; // e.g. "Warriors"
	city: string; // e.g. "Golden State", muted
};

export type GameStatus =
	| { state: 'scheduled'; tipTime: string; tipSuffix: string; network: string } // "9:00", "PM ET", already formatted
	| { state: 'live'; period: string; clock: string; awayScore: number; homeScore: number } // "Q3", "4:12", already formatted
	| { state: 'final'; awayScore: number; homeScore: number };

export type PanelPlayer = Pick<HeroPlayer, 'firstName' | 'lastName' | 'teamCode' | 'photo'>;

export type Leader = PanelPlayer & { points: number; rebounds: number; assists: number };

export type TeamStatLine = {
	fieldGoalPct: number; // 0 to 1
	threePointPct: number; // 0 to 1
	rebounds: number;
	assists: number;
	turnovers: number;
};

export type GameDetails =
	| { kind: 'scheduled'; venue: string; playersToWatch: { away: PanelPlayer; home: PanelPlayer } }
	| {
			kind: 'played'; // live or final
			periods: { away: number[]; home: number[] }; // points per period played so far, overtime included
			leaders: { away: Leader; home: Leader };
			stats: { away: TeamStatLine; home: TeamStatLine };
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
