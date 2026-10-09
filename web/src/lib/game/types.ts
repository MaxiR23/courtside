// Props of the game detail page. Components get pre-formatted strings and never a contract type.
import type { Side } from '#lib/schedule/stats.ts';
import type { GameHighlights, PanelPlayer, TeamStatLine } from '#lib/schedule/types.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';

export type GameLayout = 'pre-game' | 'live' | 'final';

// A game side (ADR 0025, ADR 0026): the code is null for a guest without one.
export type HeaderTeam = TeamMarkTeam & {
	name: string; // e.g. "Warriors"
	city: string; // e.g. "Golden State"
	record: string | null; // "12–5", already formatted; null: a guest team has no record
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
	city: string | null; // no city: the arena name alone
	photo: string | null; // no photo: the grid with the arena name
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
	| 'season-series';

export type SectionTab = { id: SectionId; label: string };

export type MiniScore = {
	awayTeam: TeamMarkTeam;
	away: number;
	home: number;
	homeTeam: TeamMarkTeam;
};

export type LineScoreTeam = { team: TeamMarkTeam; periods: number[]; total: number };

export type DetailTeamStatLine = TeamStatLine & {
	freeThrowPct: number;
	steals: number;
	blocks: number;
};
export type StatLeads = Record<keyof DetailTeamStatLine, Side | null>; // from the feed's leaders

export type ScoreSection = {
	lineScore: { away: LineScoreTeam; home: LineScoreTeam };
	stats: { away: DetailTeamStatLine; home: DetailTeamStatLine; leads: StatLeads } | null; // null: no team stats in the feed
};

export type WinProbabilitySection = {
	away: TeamMarkTeam;
	home: TeamMarkTeam;
	middle: string; // "50%", formatted
	meta: string; // "GSW 68%", "Even" or "OKC win", formatted
	points: { elapsedSeconds: number; homeWinProbability: number }[]; // at least one, feed order
	boundaries: { periods: { label: string; start: number }[]; end: number } | null; // null: no period boundaries in the feed
};

export type BoxRow = {
	id: string;
	name: string;
	minutes: string;
	points: string;
	fieldGoals: string; // "8-15"
	threePoints: string;
	freeThrows: string;
	offensiveRebounds: string;
	defensiveRebounds: string;
	rebounds: string;
	assists: string;
	turnovers: string;
	steals: string;
	blocks: string;
	fouls: string;
	plusMinus: string; // "+4", "0", "-3"
	plusMinusPositive: boolean;
	guest?: boolean; // a player of a guest team: no link
};
export type BoxTotals = Omit<
	BoxRow,
	'id' | 'name' | 'minutes' | 'plusMinus' | 'plusMinusPositive'
> & {
	fieldGoalPct: string; // "50.0%"
	threePointPct: string;
	freeThrowPct: string;
};
export type BoxScoreTeam = {
	team: TeamMarkTeam;
	starters: BoxRow[];
	bench: BoxRow[];
	totals: BoxTotals;
};
export type BoxScoreSection = { away: BoxScoreTeam; home: BoxScoreTeam };

export type StarCard = PanelPlayer & { id: string; teamName: string }; // id: the player id; teamName: "Golden State Warriors"
export type PlayersSection = { away: StarCard | null; home: StarCard | null }; // null: a guest team has no star

export type InjuryTagStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';
export type InjuryRow = {
	id: string | null; // the player id, null when the feed has none
	name: string;
	status: InjuryTagStatus;
	comment: string | null;
}; // comment as given
export type InjuryTeam = { code: string; name: string; injuries: InjuryRow[] }; // empty: none reported
export type InjuriesSection = { away: InjuryTeam | null; home: InjuryTeam | null }; // null: a guest team

export type LastGameRow = {
	result: 'win' | 'loss';
	resultLabel: string; // "W", translated
	date: string; // "Oct 5"
	opponent: { team: TeamMarkTeam; isHome: boolean }; // drawn "vs DEN" or "@ DEN"
	score: string; // "118–104", the team's points first
};
export type LastGamesTeam = {
	code: string;
	name: string;
	strip: { result: 'win' | 'loss'; label: string }[]; // oldest to newest
	rows: LastGameRow[]; // newest first, as the feed sends them
};
export type LastGamesSection = { away: LastGamesTeam | null; home: LastGamesTeam | null }; // null: a guest team

export type StandingRow = {
	code: string;
	name: string;
	conference: string; // "3rd West"
	record: string; // "12–5"
	home: string;
	away: string;
	lastTen: string;
};
export type StandingsSection = { away: StandingRow | null; home: StandingRow | null }; // null: a guest team

export type SeriesRow = {
	date: string; // "Jan 10", or "This game" for the current game
	current: boolean;
	awayCode: string;
	awayPoints: number | null; // null when the game has no score yet
	homePoints: number | null;
	homeCode: string;
	loser: 'away' | 'home' | null; // from the feed winner
	arena: string;
};
export type SeasonSeriesSection = {
	summary: string; // "OKC lead 2–1", "Series tied 1–1" or "First meeting"
	meta: string; // "2 of 4 games played"
	games: SeriesRow[]; // feed order
};

export type GameSections = {
	highlights: GameHighlights | null;
	players: PlayersSection | null;
	score: ScoreSection | null;
	winProbability: WinProbabilitySection | null;
	boxScore: BoxScoreSection | null;
	injuries: InjuriesSection | null;
	lastGames: LastGamesSection | null;
	standings: StandingsSection | null;
	seasonSeries: SeasonSeriesSection | null;
};

export type GameView = {
	header: GameHeaderView;
	tabs: SectionTab[];
	miniScore: MiniScore | null; // live and final only
	sections: GameSections; // a section is null when its tab is hidden
};

export type GamePageState =
	| { kind: 'loading' }
	| { kind: 'unavailable' }
	| { kind: 'not-found' }
	| { kind: 'ready'; view: GameView };
