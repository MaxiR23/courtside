// Props of the game detail page. Components get pre-formatted strings and never a contract type.
import type { Side } from '#lib/schedule/stats.ts';
import type { GameHighlights, PanelPlayer, TeamStatLine } from '#lib/schedule/types.ts';

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

export type LineScoreTeam = { code: string; name: string; periods: number[]; total: number };

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
	awayCode: string;
	homeCode: string;
	middle: string; // "50%", formatted
	meta: string; // "GSW 68%" or "OKC win", formatted
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
	code: string;
	name: string;
	starters: BoxRow[];
	bench: BoxRow[];
	totals: BoxTotals;
};
export type BoxScoreSection = { away: BoxScoreTeam; home: BoxScoreTeam };

export type StarCard = PanelPlayer & { teamName: string }; // teamName: "Golden State Warriors"
export type PlayersSection = { away: StarCard; home: StarCard };

export type InjuryTagStatus = 'out' | 'doubtful' | 'questionable' | 'probable' | 'day-to-day';
export type InjuryRow = { name: string; status: InjuryTagStatus; comment: string | null }; // comment as given
export type InjuryTeam = { code: string; name: string; injuries: InjuryRow[] }; // empty: none reported
export type InjuriesSection = { away: InjuryTeam; home: InjuryTeam };

export type LastGameRow = {
	result: 'win' | 'loss';
	resultLabel: string; // "W", translated
	date: string; // "Oct 5"
	opponent: string; // "vs DEN" or "@ DEN"
	score: string; // "118–104", the team's points first
};
export type LastGamesTeam = {
	code: string;
	name: string;
	strip: { result: 'win' | 'loss'; label: string }[]; // oldest to newest
	rows: LastGameRow[]; // newest first, as the feed sends them
};
export type LastGamesSection = { away: LastGamesTeam; home: LastGamesTeam };

export type StandingRow = {
	code: string;
	name: string;
	conference: string; // "3rd West"
	record: string; // "12–5"
	home: string;
	away: string;
	lastTen: string;
};
export type StandingsSection = { away: StandingRow; home: StandingRow };

export type SeriesRow = {
	date: string; // "Jan 10"
	awayCode: string;
	awayPoints: number;
	homePoints: number;
	homeCode: string;
	arena: string;
};
export type SeasonSeriesSection = {
	summary: string; // "OKC lead 2–1", "Series tied 1–1" or "First meeting"
	meta: string; // "2 of 4 games played"
	games: SeriesRow[]; // feed order
};

export type VideoLink = { title: string; duration: string; thumbnail: string | null; href: string };
export type VideosSection = VideoLink[];

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
	videos: VideosSection | null;
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
