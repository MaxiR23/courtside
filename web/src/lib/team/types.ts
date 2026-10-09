// Props of the team page. Components get pre-formatted strings and never a contract type.
import type { InfoCell, InjuryTagStatus } from '#lib/game/types.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';

export type TeamSectionId = 'overview' | 'record' | 'leaders' | 'roster' | 'injuries' | 'schedule';

export type TeamTab = { id: TeamSectionId; label: string };

export type TeamHeaderView = {
	code: string; // three letters, monogram
	city: string; // e.g. "Oklahoma City"
	name: string; // e.g. "Thunder"
	conferenceLine: string; // "Western Conference · Northwest Division"
	colors: { primary: string; secondary: string }; // hex values from the feed
	record: string; // "57–25"
	winPct: string; // "69.5%"
	recordSeason: string; // "2025-26 record", the season of the record
	cells: InfoCell[]; // Conference, Streak, Last 10, Playoffs; a cell with no data is left out
};

export type GameLink = { gameId: string; linked: boolean }; // linked: the feed's detailAvailable

export type NextGameView = GameLink & {
	tag: string | null; // "NBA Cup"
	date: string; // "Wednesday, October 7"
	opponent: { team: TeamMarkTeam; isHome: boolean }; // drawn "vs DEN" or "@ DEN"
	place: string; // "Ball Arena · Denver, CO", or the arena alone
	time: string; // "7:30 PM ET · Courtside TV", or the time alone
};

export type OverviewSection = {
	arena: { name: string; city: string | null; photo: string | null }; // no photo: a stat cell
	coach: InfoCell | null;
	colors: { hex: string }[]; // primary, secondary
	nextGame: NextGameView | null; // null: "Season over."
};

export type RecordSection = { meta: string; large: InfoCell[]; detail: InfoCell[] };

export type LeaderCard = {
	playerId: string;
	label: string; // "Points"
	value: string; // "31.8"
	name: string;
	line: string; // "#2 · Guard", or "Guard"
	photo: string | null;
};
export type LeadersSection = { meta: string; cards: LeaderCard[] }; // 1 to 3 cards

export type RosterStatusTone = 'out' | 'ink' | 'muted';
// A null field is an empty cell.
export type RosterRow = {
	id: string;
	name: string;
	photo: string | null;
	number: string | null;
	position: string | null;
	height: string | null;
	weight: string | null;
	age: string | null;
	born: string | null;
	birthplace: string | null;
	college: string | null;
	experience: string | null;
	status: { label: string; tone: RosterStatusTone };
};

export type TeamInjuryRow = {
	name: string;
	line: string | null; // "#2 · G"; null when there is neither a number nor a position
	status: InjuryTagStatus;
	comment: string | null;
};

export type ScheduleRowView = GameLink & {
	weekday: string; // "Wed"
	date: string; // "Oct 7"
	opponent: { team: TeamMarkTeam; isHome: boolean }; // drawn "vs DEN" or "@ DEN"
	tags: string[]; // the game tag, then "Next" on the next game
	next: boolean;
	outcome:
		| {
				kind: 'played';
				result: 'win' | 'loss';
				resultLabel: string; // "W"
				score: string | null; // "118–104", the team's points first; null when the feed has no score
				side: string; // "Home" or "Away"
		  }
		| { kind: 'upcoming'; time: string; broadcast: string | null };
};
export type ScheduleGroupView = { key: string; label: string; rows: ScheduleRowView[] };
export type ScheduleSection = { groups: ScheduleGroupView[]; defaultKey: string };

export type TeamSections = {
	overview: OverviewSection;
	record: RecordSection;
	leaders: LeadersSection | null;
	roster: RosterRow[] | null;
	injuries: TeamInjuryRow[];
	schedule: ScheduleSection | null; // null: hidden with its tab
};

export type TeamView = {
	header: TeamHeaderView;
	tabs: TeamTab[];
	mini: string; // "OKC 57–25"
	sections: TeamSections;
};

export type TeamPageState =
	| { kind: 'loading' }
	| { kind: 'unavailable' }
	| { kind: 'not-found' }
	| { kind: 'ready'; view: TeamView };
