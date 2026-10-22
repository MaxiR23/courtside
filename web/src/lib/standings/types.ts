// Props of the standings page. Components get pre-formatted strings and never a contract type.

import type { TeamMarkTeam } from '#lib/team/mark.ts';

export type StandingsGrouping = 'conference' | 'division';

export type ClinchTone = 'accent' | 'ink' | 'muted';

export type ClinchView = { code: string; tone: ClinchTone }; // code as the feed sends it: "*", "xp"

export type StandingsLine = 'playoff' | 'play-in';

export type StandingsRowView = {
	code: string; // "OKC", the link: today's code
	team: TeamMarkTeam; // the box: the logo, else the code (the season code of a historical row)
	seed: string; // "1", or "—"
	city: string;
	name: string;
	strip: { primary: string; secondary: string } | null; // null: plain tile; always null for a historical row
	clinch: ClinchView | null;
	eliminated: boolean;
	wins: string;
	losses: string;
	pct: string;
	gamesBehind: string; // "—" when null
	streak: { text: string; win: boolean }; // a null streak is { text: '—', win: false }
	home: string;
	away: string;
	lastTen: string;
	division: string;
	conference: string;
	pointsFor: string;
	pointsAgainst: string;
	differential: { value: string; accent: boolean };
	total: { value: string; accent: boolean };
	lineAfter: StandingsLine | null; // conference groups only
};

export type StandingsGroupView = {
	key: string;
	title: string;
	meta: string;
	rows: StandingsRowView[];
};

export type StandingsHeaderView = { season: string; stateLine: string; tag?: string | null }; // tag: "Season 2004-05" on a past season

export type StandingsKeyEntry = { clinch: ClinchView; label: string };

export type StandingsView = {
	header: StandingsHeaderView;
	conference: StandingsGroupView[];
	division: StandingsGroupView[];
	key: StandingsKeyEntry[]; // the 7 codes in table order
	lines: boolean; // the dashed seed lines are drawn: false on a past season
};

export type StandingsPageState =
	{ kind: 'loading' } | { kind: 'unavailable' } | { kind: 'ready'; view: StandingsView };
