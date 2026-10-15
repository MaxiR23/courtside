// Props of the playoffs page. Components get pre-formatted strings and never a contract type.

import type {
	Conference,
	LeaderCategory,
	PlayInGameKind,
	PlayoffStage,
	PlayoffStageStatus,
	SeriesId
} from '#lib/contract/playoffs.ts';
import type { HeadToHeadStat } from '#lib/contract/playoffs-finals.ts';
import type { ChartBoundaries, ChartPoint } from '#lib/game/win-probability.ts';
import type { HighlightVideo, Leader } from '#lib/schedule/types.ts';
import type { ClinchView } from '#lib/standings/types.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';
import type { GameLink } from '#lib/team/types.ts';

export type PlayoffsSectionId =
	| 'picture'
	| 'bracket'
	| 'play-in'
	| 'finals-mvp'
	| 'series'
	| 'road'
	| 'head-to-head'
	| 'leaders'
	| 'awards';

export type PlayoffStageView = {
	key: PlayoffStage;
	label: string; // "Round 1"
	dates: string; // "Apr 18 – May 3", a single date, or "TBD"
	status: PlayoffStageStatus;
	statusLabel: string; // "In progress"
};

export type ChampionHeroView = {
	tag: string; // "2026 NBA Finals"
	result: string; // "Harbor Owls win series 4–1 · Jun 4 – Jun 19"
	title: string; // "Champions"
	plateLabel: string; // "2026 champions"
	trophyTitle: string; // the accessible title of the drawing
	team: TeamMarkTeam;
	city: string | null;
	strip: { primary: string; secondary: string } | null;
	stats: {
		key: 'record' | 'home' | 'road' | 'diff';
		label: string;
		value: string;
		accent: boolean;
	}[];
};

export type PlayoffsHeaderView = {
	season: string;
	stateLine: string;
	stages: PlayoffStageView[];
	hero: ChampionHeroView | null; // only when the postseason is complete
	tag: string | null; // "Season 2004-05" on a past season
};

export type PictureRowView = {
	team: TeamMarkTeam;
	seed: string; // "1", or "—"
	record: string; // "52-30", or "—"
	gamesBehind: string;
	clinch: ClinchView | null;
	strip: { primary: string; secondary: string } | null;
	line: 'playoffs' | 'playin' | null; // the line drawn under the row
};

export type PictureTableView = { key: Conference; title: string; rows: PictureRowView[] };

export type PlayInSlotView = {
	team: TeamMarkTeam | null;
	label: string; // the team name, or "To be decided"
	place: string | null; // the regular season place of an undecided slot: "7th", "Loser of 7th vs 8th"
	currently: string | null; // "Currently QXA"
};

export type PlayInGameView = GameLink & {
	key: PlayInGameKind;
	title: string; // "7th vs 8th"
	top: PlayInSlotView;
	bottom: PlayInSlotView;
	score: { top: string; bottom: string } | null;
	when: string | null; // "Apr 14 · 7:30 PM ET" while the game is not final
	outcomes: string[]; // "QXA → No. 7", "QXB out"
};

export type PlayInView = { key: Conference; title: string; games: PlayInGameView[] };

export type FinalsMvpView = {
	name: string;
	photo: string | null;
	team: string;
	stats: {
		key: 'ppg' | 'best' | 'rebast' | 'games';
		label: string;
		value: string;
		accent: boolean;
	}[];
} | null;

export type ConferenceMvpView = {
	key: 'east' | 'west';
	name: string;
	photo: string | null;
	label: string; // "East finals MVP"
	team: string;
};

export type FinalsChartView = {
	points: ChartPoint[];
	boundaries: ChartBoundaries | null;
	deficit: { label: string; left: number } | null; // left: 0 to 1 of the chart
};

export type SeriesGameView = GameLink & {
	key: string;
	tab: string; // "G3"
	winner: string; // the winner's code
	championWon: boolean;
	score: string; // "112–104", the winner's points first
	overtime: boolean;
	video: HighlightVideo | null;
	chart: FinalsChartView | null;
	scoreLine: string; // "QXB 104 – 112 QXA"
	leaders: { away: Leader; home: Leader } | null;
};

export type RoadSeriesView = {
	key: string;
	round: string; // "Conference finals"
	opponentSeed: string; // "#4" or "—"
	opponent: TeamMarkTeam;
	strip: { primary: string; secondary: string } | null;
	result: string; // "4–1 W", or "—"
	loss: boolean;
};

export type RoadCardView = {
	team: TeamMarkTeam;
	name: string;
	seedLine: string; // "#1 seed · 64-18"
	postseason: string; // "16-6", or "—"
	series: RoadSeriesView[];
};

export type BarSideView = {
	value: string; // "112.4", or "—"
	share: number; // 0 to 1 of its half
	better: boolean;
	color: string | null; // the finalist's primary color
};

export type BarView = { key: HeadToHeadStat; label: string; sides: [BarSideView, BarSideView] };

export type AverageRowView = {
	id: string;
	name: string;
	photo: string | null;
	points: string;
	rebounds: string;
	assists: string;
	blocks: string;
	fieldGoalPct: string;
};

export type HeadToHeadView = {
	records: { team: string; record: string }[];
	bars: BarView[];
	averages: { key: string; label: string; rows: AverageRowView[] }[];
};

export type LeaderRowView = {
	id: string;
	rank: string;
	name: string;
	photo: string | null;
	team: string;
	value: string;
};

export type LeaderTabView = {
	key: LeaderCategory;
	label: string;
	first: LeaderRowView | null;
	rest: LeaderRowView[];
};

export type AwardView = {
	key: string;
	name: string;
	code: string | null; // the short code chip of a player award
	kind: 'player' | 'team';
	winners: { id: string; name: string; photo: string | null; team: string }[];
};

export type SeriesSideView = {
	team: TeamMarkTeam | null;
	seed: string; // "1", or "—" (current season); "" with no team, or no seed on a past season
	wins: string; // "3", or "—"; "" with no team
	strip: { primary: string; secondary: string } | null;
	label: string; // the team's code or name, or the slot label ("East #1 seed")
	note: string | null; // an undecided side: "Currently QXA" or "To be decided"
	loser: boolean;
};

export type SeriesGameRowView = GameLink & {
	key: string; // the game id
	label: string; // "G1 · at QXA"
	away: { code: string; score: string; loser: boolean };
	home: { code: string; score: string; loser: boolean };
	final: boolean;
	overtime: boolean;
	when: string | null; // "Apr 19 · Example Arena" while the game is not final
};

export type SeriesCardView = {
	id: SeriesId;
	name: string; // the accessible name: "East · Round 1 · QXA · QXH"
	roundTitle: string; // "East · Round 1", "NBA Finals"
	top: SeriesSideView;
	bottom: SeriesSideView;
	decided: 'both' | 'one' | 'none';
	final: boolean; // the NBA Finals card
	complete: boolean;
	champion: boolean; // final and complete: the accent border and the Champion label
	score: string; // the summary, else "3–1" from the wins, else "—"
	games: SeriesGameRowView[];
};

export type PlayoffBracketView = { series: SeriesCardView[] };

export type PlayoffsView = {
	header: PlayoffsHeaderView;
	sections: PlayoffsSectionId[];
	picture: PictureTableView[];
	playIn: PlayInView[];
	playInCollapsed: boolean;
	finalsMvp: FinalsMvpView;
	conferenceMvps: ConferenceMvpView[];
	series: SeriesGameView[];
	bracket: PlayoffBracketView;
	road: RoadCardView[];
	headToHead: HeadToHeadView | null;
	leaders: LeaderTabView[];
	awards: AwardView[];
};

export type PlayoffsPageState =
	{ kind: 'loading' } | { kind: 'unavailable' } | { kind: 'ready'; view: PlayoffsView };

// A postseason game's mark: its tag, context line and stakes flag, already written (ADR 0035).
export type PostseasonMarkView = {
	tag: string; // "Play-In", "Playoffs", "NBA Finals"
	finals: boolean; // true: the solid accent tag
	context: string; // "West finals · Game 7"
	stakes: string | null; // "Can clinch"; null: no stakes
};

// A title badge on the team header, already written.
export type TitleView = {
	text: string; // "2027 NBA Champions"
	solid: boolean; // true only for the NBA title
};
