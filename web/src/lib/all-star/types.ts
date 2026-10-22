// Props of the All-Star page. Components get pre-formatted strings and never a contract type.
// SEE: docs/design-all-star.md, docs/api/all-star.md

import type { AllStarState } from '#lib/contract/all-star.ts';
import type { HighlightVideo, Leader } from '#lib/schedule/types.ts';
import type { TeamMarkTeam } from '#lib/team/mark.ts';

/** The All-Star mark of a core game (ADR 0038): the stage tag and the round line. */
export type AllStarMarkView = {
	tag: string; // "All-Star"
	context: string; // "Round Robin", "Championship"
	championship: boolean; // true: the solid accent tag
};

export type AllStarSectionId = 'last-time' | 'mvp' | 'games' | 'teams';

/** A league team's mark (its logo, else its code) and the two colors of its bar (null when the feed has none). */
export type LeagueMarkView = {
	code: string;
	team: TeamMarkTeam;
	primary: string | null;
	secondary: string | null;
};

export type StatCellView = {
	key: string;
	label: string;
	value: string;
	accent: boolean;
	countTo: number | null; // the integer the count-up reaches; null: shown as is, the count-up does not touch it
};

export type ScoreRowView = {
	team: TeamMarkTeam | null; // null: a slot still to be determined
	name: string;
	score: string; // "—" until the game is played
	winner: boolean; // the sigla gets the accent border
	loser: boolean; // the row is muted
};

export type PlateView =
	| {
			kind: 'mvp';
			name: string;
			photo: string | null;
			jersey: string | null;
			labels: string; // "27 PTS · 2 games"
	  }
	| { kind: 'score'; rows: ScoreRowView[] }
	| {
			kind: 'live';
			gameId: string;
			header: string; // "Live · Semifinals"
			formatLine: string | null;
			rows: ScoreRowView[];
			clock: string; // as the feed sends it, "—" when it sends none
			status: string | null; // the status text as the feed sends it
			next: string | null; // "Next: Championship"
	  }
	| { kind: 'tipoff'; gameId: string; text: string }
	| { kind: 'year'; year: string | null };

export type HeaderButtonView = {
	key: 'games' | 'mvp' | 'last-time';
	label: string;
	primary: boolean;
};

export type AllStarHeaderView = {
	state: AllStarState;
	tag: string; // "All-Star 2027"
	meta: string | null; // "Feb 14 · Example Arena"
	kicker: string;
	title: string; // the champion's name after, else "All-Star"
	score: string | null; // "25–23", the Championship after
	stats: StatCellView[]; // empty before
	rows: { key: 'date' | 'venue' | 'format'; label: string; value: string }[]; // before only
	buttons: HeaderButtonView[];
	plate: PlateView;
	seasonTag: string | null; // "Season 2004-05" on a past season
};

export type GameCardView = {
	id: string;
	round: { text: string; championship: boolean } | null;
	status: { kind: 'final' | 'live' | 'tipoff'; text: string };
	label: string; // "STR · WAV", or "To be determined"
	rows: ScoreRowView[]; // two rows
};

export type Top5RowView = {
	key: string;
	playerId: string;
	rank: string; // "#1"
	top: boolean; // #1: the rank is drawn in accent
	name: string;
	photo: string | null;
	league: LeagueMarkView | null;
	teamLine: string; // "Team Stripes · BOS"
	points: string;
	line: string; // "PTS · 4 REB · 3 AST"
};

export type TeamStatView = {
	key: string;
	label: string;
	away: string;
	home: string;
	awayShare: number; // 0 to 1: the drawing scale of the bar, the larger value is 1
	homeShare: number;
	better: 'away' | 'home' | null; // the feed's
};

export type GameDetailView = {
	id: string;
	scheduled: { title: string; body: string } | null; // the one centered card of a game not started
	video: HighlightVideo | null;
	placeholder: string | null; // the text of the 16:9 placeholder when there is no video
	live: boolean; // the placeholder's play button is muted while live or scheduled
	venueStrip: { key: string; label: string; value: string }[];
	top5: Top5RowView[];
	scoreboard: { rows: ScoreRowView[]; status: string };
	leaders: { away: Leader; home: Leader } | null;
	teamStats: TeamStatView[] | null;
};

export type BoxRowView = {
	id: string;
	jersey: string;
	name: string;
	position: string;
	minutes: string;
	points: string;
	rebounds: string;
	assists: string;
	steals: string;
	blocks: string;
	fieldGoals: string; // "4-8"
	threePoints: string;
	plusMinus: string;
	starter: boolean;
	topPoints: boolean; // the feed's: the team's highest points
	negative: boolean; // plus-minus below 0: muted
	photo: string | null;
	league: LeagueMarkView | null;
	mobileMeta: string; // "#5 · G · 24:10"
};

export type BoxTotalsView = {
	points: string;
	rebounds: string;
	assists: string;
	steals: string;
	blocks: string;
	fieldGoals: string;
	threePoints: string;
};

export type BoxTeamView = {
	tab: string; // the All-Star team's label
	rows: BoxRowView[];
	totals: BoxTotalsView;
};

export type GameBoxView = { away: BoxTeamView; home: BoxTeamView };

export type MvpLineView = {
	key: string;
	round: string;
	championship: boolean;
	result: string; // "W 47–21 vs Team Stripes"
	stat: string; // "27 PTS · 5 REB · 4 AST"
};

export type MvpView = {
	playerId: string;
	name: string;
	photo: string | null;
	jersey: string | null;
	league: LeagueMarkView | null;
	lines: MvpLineView[];
	total: string; // "47 PTS · across 2 games"
};

export type ScorelineView = {
	gameId: string;
	rows: ScoreRowView[]; // the winner first
	overtime: boolean;
};

export type TeamResultView = {
	key: string;
	win: boolean;
	mark: string; // "W" or "L"
	text: string; // "Round Robin · vs STR · OT"
	score: string; // "21–18"
};

export type RosterTileView = {
	playerId: string;
	name: string;
	photo: string | null;
	title: string; // "Ada Example · BOS"
	league: LeagueMarkView | null;
};

export type TeamCardView = {
	key: string;
	team: TeamMarkTeam;
	name: string;
	placement: string; // "Champion"
	champion: boolean;
	record: string; // "2–1"
	results: TeamResultView[];
	roster: RosterTileView[];
};

export type LastTimeView = {
	champion: { kicker: string; name: string; meta: string; score: string };
	mvp: {
		playerId: string;
		name: string;
		photo: string | null;
		league: LeagueMarkView | null;
		summary: string;
	} | null;
	video: string | null; // the previous edition's video URL; null: the card does not link
	link: string; // "Every game, box score and highlight from 2026 →"
};

export type AllStarView = {
	header: AllStarHeaderView;
	sections: AllStarSectionId[];
	lastTime: LastTimeView | null;
	mvp: MvpView | null;
	scoreline: ScorelineView | null;
	formatLine: string | null;
	games: GameCardView[];
	details: Record<string, GameDetailView>;
	boxes: Record<string, GameBoxView | null>;
	defaultGame: string | null; // the feed's defaultGameId
	teams: TeamCardView[];
	editionVideo: HighlightVideo | null; // replaces the selected game's media when present
};

export type AllStarPageState =
	{ kind: 'loading' } | { kind: 'unavailable' } | { kind: 'ready'; view: AllStarView };
