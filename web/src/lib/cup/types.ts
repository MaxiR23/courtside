// Props of the Cup page. Components get pre-formatted strings and never a contract type.

import type { CupRound, StageStatus } from '#lib/contract/cup.ts';
import type { HeroStatus } from '#lib/hero/types.ts';
import type { ClinchView } from '#lib/standings/types.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';
import type { GameLink } from '#lib/team/types.ts';

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

export type CupView = {
	header: CupHeaderView;
	sections: CupSectionId[]; // in drawing order
	drawn: boolean;
	groups: CupGroupView[];
	legend: CupLegendEntry[];
	wildCard: WildCardView[];
	bracketText: string;
	filters: CupFilterView[];
};

export type CupPageState =
	{ kind: 'loading' } | { kind: 'unavailable' } | { kind: 'ready'; view: CupView };
