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

export type ChampionGameView = {
	key: string; // the game id
	label: string; // "G3"
	score: string; // "105–95", the champion's points first; "—" without a score
	win: boolean; // the champion won it: ink; otherwise muted
};

export type ChampionHeroView = {
	label: string; // "2027 NBA Champions", also the trophy's accessible title
	team: TeamMarkTeam; // the logo comes from team.logo
	city: string | null; // first line of the h1; null: the h1 has only the team line
	name: string; // "Owls": the team name, else its label
	subline: string; // "Won the series 4–1 over Summit · Jun 4 – Jun 19"
	accent: string | null; // the champion's resolved color from the feed (ADR 0072); null: the neutral accent
	games: ChampionGameView[]; // one per final Finals game, in feed order
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
	teamName: string; // the team's full name, or the drawn code when the team is not in the bracket
	mark: TeamMarkTeam; // the logo tile; the monogram of the drawn code when the team is not found
	accent: string | null; // the team's resolved color from the feed (ADR 0072); null: the neutral accent
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
	teamName: string; // the team's full name, or the drawn code when the team is not in the bracket
	mark: TeamMarkTeam; // the logo tile; the monogram of the drawn code when the team is not found
	accent: string | null; // the team's resolved color from the feed (ADR 0072); null: the neutral accent
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
	averages: { key: string; label: string; rows: AverageRowView[] }[] | null;
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
	when: string | null; // "Apr 19 · Example Arena" while the game is not final; the date alone when the arena is unknown
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

export type SeriesHeroSideView = {
	team: TeamMarkTeam; // the logo comes from team.logo
	code: string; // "QXA", the season code for a historical side
	seed: string | null; // "No. 1 seed"; null: no seed line (a null seed on a past season)
	wins: string; // "4", or "—"
	accent: string | null; // the feed's resolved color (ADR 0072); null: the neutral accent
	lead: boolean; // the score in ink; false only for the trailing side
	loser: boolean; // the series is complete and this side lost: drawn at 60%
};

export type SeriesPageGameSideView = {
	team: TeamMarkTeam;
	code: string;
	score: string; // "105", or "—"
	loser: boolean; // a final game this side lost: drawn at 50%
};

export type SeriesPageGameView = GameLink & {
	key: string; // the game id
	title: string; // "Game 3"
	meta: string; // "Apr 19 · Example Arena", or "Apr 19 · at QXA" with no venue
	overtimeTag: string | null; // "OT", "2OT"; null in regulation
	sides: [SeriesPageGameSideView, SeriesPageGameSideView]; // top team first
	leaders: string | null; // Finals only: "Aaron Away1 25 PTS · Bea Home1 22 PTS"
	rule: { accent: string | null } | null; // the winner's line; null: no winner yet
};

export type SeriesPageView = {
	kicker: string; // "2027 NBA Playoffs"
	round: string; // "East · Round 1", "NBA Finals"
	top: SeriesHeroSideView;
	bottom: SeriesHeroSideView;
	status: string | null; // "QXA wins the series 4–1"; null when a side's wins are missing
	dates: string | null; // "Apr 19 – Apr 29"; null with no games
	games: SeriesPageGameView[];
};

export type SeriesPageState =
	| { kind: 'loading' }
	| { kind: 'unavailable' }
	| { kind: 'not-found' }
	| { kind: 'ready'; view: SeriesPageView };

// A postseason game's mark: its tag, context line and stakes flag, already written (ADR 0035).
export type PostseasonMarkView = {
	tag: string; // "Play-In", "Playoffs", "NBA Finals"
	finals: boolean; // true: the solid accent tag
	context: string | null; // "West finals · Game 7"; null: nothing to add to the tag
	stakes: string | null; // "Can clinch"; null: no stakes
};

// A title badge on the team header, already written.
export type TitleView = {
	text: string; // "2027 NBA Champions"
	solid: boolean; // true only for the NBA title
};
