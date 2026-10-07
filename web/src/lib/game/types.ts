// Props of the game detail page. Components get pre-formatted strings and never a contract type.

export type GameLayout = 'pre-game' | 'live' | 'final';

export type HeaderTeam = {
	code: string; // three letters, monogram
	name: string; // e.g. "Warriors"
	city: string; // e.g. "Golden State"
	record: string; // "12–5", already formatted
};

export type StatusLine =
	| { state: 'scheduled' | 'final'; text: string } // the whole line, already joined with " · "
	| { state: 'delayed' | 'postponed' | 'canceled'; text: string } // shown after the StatusTag
	| { state: 'live'; text: string }; // shown after the LiveBadge: "Q3 · 4:12 · Chase Center"

export type ScoreboardCenter =
	| { kind: 'score'; away: number; home: number; loser: 'away' | 'home' | null } // loser only on final
	| {
			kind: 'tip-off';
			tipTime: string; // "9:00", already formatted
			tipSuffix: string; // "PM ET", already formatted
			broadcast: string | null; // no network when unknown
			delayed: boolean; // shows "Scheduled" before the original time
	  }
	| { kind: 'none' }; // postponed, canceled

export type InfoCell = {
	label: string;
	value: string;
	sub: string | null; // muted line under the value
};

export type VenueStrip = {
	arena: string;
	city: string;
	photo: string | null; // no photo: the bare grid
	cells: InfoCell[];
};

export type GameHeaderView = {
	layout: GameLayout;
	status: StatusLine;
	away: HeaderTeam;
	home: HeaderTeam;
	center: ScoreboardCenter;
	venue: VenueStrip | null; // pre-game only
};

export type SectionId =
	| 'highlights'
	| 'players'
	| 'score'
	| 'win-probability'
	| 'box-score'
	| 'injuries'
	| 'last-games'
	| 'standings'
	| 'season-series'
	| 'videos';

export type SectionTab = { id: SectionId; label: string };

export type MiniScore = { awayCode: string; away: number; home: number; homeCode: string };

export type GameView = {
	header: GameHeaderView;
	tabs: SectionTab[];
	miniScore: MiniScore | null; // live and final only
};

export type GamePageState =
	| { kind: 'loading' }
	| { kind: 'unavailable' }
	| { kind: 'not-found' }
	| { kind: 'ready'; view: GameView };
