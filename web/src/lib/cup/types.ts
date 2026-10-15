// Props of the Cup page. Components get pre-formatted strings and never a contract type.

import type { CupRound, SlotId, StageStatus } from '#lib/contract/cup.ts';
import type { InjuryTagStatus } from '#lib/game/types.ts';
import type { HeroStatus } from '#lib/hero/types.ts';
import type { ClinchView } from '#lib/standings/types.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';
import type { GameLink, TeamInjuryRow } from '#lib/team/types.ts';

export type CupSectionId = 'groups' | 'wild-card' | 'bracket' | 'games';

export type StageView = {
	key: CupRound;
	label: string; // "Group play"
	dates: string; // "Nov 4 – Dec 2", a single date, or "TBD"
	status: StageStatus;
	statusLabel: string; // "In progress"
};

export type CupHeaderView = {
	season: string;
	stateLine: string;
	champion: TeamMarkTeam | null; // only when the Cup is complete
	stages: StageView[];
	tag: string | null; // "Season 2023-24" on a past season
};

export type Signed = { value: string; accent: boolean }; // accent: a value of zero or more

export type GroupRowView = {
	team: TeamMarkTeam;
	position: string; // "1", or "—"
	record: string; // "3-1"
	gamesBehind: string;
	perGame: Signed;
	total: Signed;
	streak: { text: string; win: boolean }; // a null streak is { text: '—', win: false }
	pointsFor: string;
	pointsAgainst: string;
	home: string;
	away: string;
	overtime: string;
	tag: ClinchView | null;
	eliminated: boolean;
};

export type CupGroupView = {
	key: string; // "east-a"
	title: string; // "East Group A"
	meta: string; // "5 teams", "3 of 10 games" or "Final"
	teams: TeamMarkTeam[]; // the draw list, shown when there are no rows
	rows: GroupRowView[];
};

export type CupLegendEntry = { clinch: ClinchView; label: string };

export type WildCardRowView = {
	team: TeamMarkTeam;
	rank: string;
	group: string; // "East Group A", or "—"
	record: string;
	total: Signed;
	pointsFor: string;
	tag: ClinchView | null;
	lineAfter: boolean; // the dashed wild card line goes under this row
};

export type WildCardView = { key: string; title: string; rows: WildCardRowView[] };

export type CupSideView = { team: TeamMarkTeam; score: string | null; loser: boolean };

export type CupGameStatusView =
	{ kind: 'time'; text: string } | { kind: 'live' } | { kind: 'status'; status: HeroStatus };

export type CupGameRowView = GameLink & {
	stageLabel: string;
	away: CupSideView;
	home: CupSideView;
	status: CupGameStatusView;
	broadcast: string | null;
	notCounted: boolean;
};

export type CupDayView = { key: string; label: string; games: CupGameRowView[] };

export type CupFilterKey = 'all' | CupRound;

export type CupFilterView = {
	key: CupFilterKey;
	label: string;
	count: string;
	days: CupDayView[];
};

export type BracketSideView = {
	team: TeamMarkTeam | null; // null: undecided
	name: string; // the team's name, or "To be decided"
	label: string; // "East #1 seed"
	rule: string; // "Best group winner"
	currently: string | null; // "Currently QXA (3-1)", only from a projection
	meta: string | null; // "#1 seed · East Group A · 4-0", parts with no value left out
	score: string | null;
	winner: boolean;
};

export type BracketNodeView = {
	id: SlotId;
	roundLabel: string;
	mirrored: boolean; // the West half reads right to left
	final: boolean;
	top: BracketSideView;
	bottom: BracketSideView;
	date: string | null;
	venue: string | null;
	broadcast: string | null;
	neutral: boolean;
};

export type BracketView = {
	nodes: BracketNodeView[]; // in the feed's order
	known: Record<`${SlotId}:${'top' | 'bottom'}`, boolean>; // the feed's `known`, for the connectors
	rounds: Record<'quarterfinals' | 'semifinals' | 'championship', string>; // the round labels of the columns
	champion: string | null; // the champion's name, when the Cup is complete
};

export type CupView = {
	header: CupHeaderView;
	sections: CupSectionId[]; // in drawing order
	drawn: boolean;
	groups: CupGroupView[];
	legend: CupLegendEntry[];
	wildCard: WildCardView[];
	bracket: BracketView;
	filters: CupFilterView[];
};

export type PlayerCardView = {
	id: string;
	name: string;
	photo: string | null;
	team: string;
	number: string | null; // "#2"
	position: string | null;
	injury: InjuryTagStatus | null;
	points: string; // per game, one decimal, or "—"
	rebounds: string;
	assists: string;
	height: string | null;
	weight: string | null; // "200 lb"
	age: string | null;
	hometown: string | null;
	college: string | null;
	experience: string | null; // a number, or the rookie mark ("R")
};

export type MatchupPlayerRow = {
	id: string;
	name: string;
	number: string | null;
	position: string | null;
	injury: InjuryTagStatus | null; // shown in place of the position
	points: string;
	rebounds: string;
	assists: string;
	leader: { points: boolean; rebounds: boolean; assists: boolean };
	starter: boolean;
	card: PlayerCardView;
};

export type PathRowView = GameLink & {
	result: 'W' | 'L' | null;
	opponent: TeamMarkTeam;
	isHome: boolean;
	score: string | null; // "110-98", the team's score first
};

export type MatchupSideView = {
	team: TeamMarkTeam | null; // null: undecided, with no blocks
	name: string;
	label: string;
	score: string | null;
	path: PathRowView[];
	injuries: TeamInjuryRow[];
	roster: MatchupPlayerRow[];
};

export type MatchupStatusView =
	| { kind: 'final'; text: string } // "Final" or "Final/OT"
	| { kind: 'vs' }
	| { kind: 'status'; status: HeroStatus };

export type MatchupView = {
	header: {
		round: string; // "East · Semifinals", or "Championship"
		date: string | null;
		venue: string | null;
		broadcast: string | null;
		neutral: boolean;
		gameLink: GameLink | null; // null: no game yet
	};
	sides: [MatchupSideView, MatchupSideView];
	status: MatchupStatusView;
	note: boolean; // the championship does not count toward the record
	rosterNote: string | null; // a past season: the line shown in place of the injuries and the roster
};

export type MatchupPanelState =
	{ kind: 'loading' } | { kind: 'unavailable' } | { kind: 'ready'; view: MatchupView };

/** The player card that is open: a side of the matchup and a place in its roster. */
export type OpenCard = { side: 0 | 1; index: number };

export type CupPageState =
	{ kind: 'loading' } | { kind: 'unavailable' } | { kind: 'ready'; view: CupView };
export type CupTeamLineView = { group: string; record: string }; // "East Group A", "3-1"
