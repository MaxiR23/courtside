// Props of the player page. Components get pre-formatted strings and never a contract type.
import type { InfoCell, InjuryTagStatus } from '#lib/game/types.ts';
import type { GameLink, NextGameView } from '#lib/team/types.ts';

export type PlayerSectionId =
	'profile' | 'averages' | 'seasons' | 'milestones' | 'game-log' | 'awards';

export type PlayerTab = { id: PlayerSectionId; label: string };

export type PlayerHeaderView = {
	teamCode: string; // "OKC", the team tag
	status: { label: string; injured: boolean }; // "Active", or the injury label in accent
	firstName: string;
	lastName: string;
	line: string; // "#2 · Guard · Oklahoma City Thunder"; a null number is left out
	injury: { status: InjuryTagStatus; comment: string | null; updated: string } | null; // updated: "Updated Oct 7 · 3:15 PM ET"
	photo: string | null; // null: the photo block is not rendered
	stats: { label: string; cells: InfoCell[] } | null; // null: no summary
};

export type LiveGameView = {
	gameId: string;
	opponent: string; // "vs DEN" or "@ DEN"
	score: string; // "78–74", the team's points first
	clock: string; // "Q3 · 4:12"
	line: InfoCell[] | null; // MIN, PTS, REB, AST, FG with no sub-line; null: not in the game yet
};

export type RecentGameRow = GameLink & {
	result: 'win' | 'loss';
	resultLabel: string; // "W"
	date: string; // "Apr 29"
	opponent: string; // "vs MEM", "@ MEM", or the All-Star label
	score: string; // "118–104"
	tag: string | null; // "NBA Cup"
	points: string; // "31"
	line: string; // "8 REB · 6 AST"
};

export type ProfileSection = {
	cells: InfoCell[];
	nextGame: NextGameView | null;
	live: LiveGameView | null; // takes precedence over nextGame
	recent: RecentGameRow[];
};

export type StatColumn = {
	key: string;
	label: string;
	muted?: boolean;
	points?: boolean;
	wide?: boolean; // a made–attempted column
};

export type StatCell = string | { mark: string; win: boolean; text: string }; // the object form is the game log's result cell

export type StatRowView = {
	key: string;
	label: string;
	sub: string | null;
	accent?: boolean;
	link?: GameLink | null;
	cells: StatCell[]; // follow the column order
};

export type StatTableView = { columns: StatColumn[]; rows: StatRowView[] };

export type AveragesSection = StatTableView;

export type SeasonsSection = {
	regular: { perGame: StatTableView; totals: StatTableView };
	playoffs: { perGame: StatTableView; totals: StatTableView } | null;
};

export type MilestonesSection = { meta: string; cells: InfoCell[] };

export type GameLogFilter = 'all' | 'regular' | 'cup' | 'playoffs';

export type GameLogSection = {
	meta: string;
	columns: StatColumn[];
	filters: { id: GameLogFilter; label: string; rows: StatRowView[] }[]; // only non-empty filters
};

export type AwardView = { count: string; name: string; seasons: string };

export type PlayerSections = {
	profile: ProfileSection;
	averages: AveragesSection | null;
	seasons: SeasonsSection | null;
	milestones: MilestonesSection | null;
	gameLog: GameLogSection | null;
	awards: AwardView[] | null;
};

export type PlayerView = {
	header: PlayerHeaderView;
	tabs: PlayerTab[];
	mini: string; // "#2 S. Gilgeous-Alexander"
	sections: PlayerSections;
};

export type PlayerPageState =
	| { kind: 'loading' }
	| { kind: 'unavailable' }
	| { kind: 'not-found' }
	| { kind: 'ready'; view: PlayerView };
