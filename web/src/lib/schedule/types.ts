export type ScheduleTeam = {
	code: string; // three letters, monogram
	name: string; // e.g. "Warriors"
	city: string; // e.g. "Golden State", muted
};

export type GameStatus =
	| { state: 'scheduled'; tipTime: string; tipSuffix: string; network: string } // "9:00", "PM ET", already formatted
	| { state: 'live'; period: string; clock: string; awayScore: number; homeScore: number } // "Q3", "4:12", already formatted
	| { state: 'final'; awayScore: number; homeScore: number };

export type ScheduleGame = {
	id: string;
	away: ScheduleTeam;
	home: ScheduleTeam;
	status: GameStatus;
};

export type ScheduleDay = { date: Date; games: ScheduleGame[] };

export type RowLayout = 'desktop' | 'mobile';
