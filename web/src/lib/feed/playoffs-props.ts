import type {
	Award,
	AwardCode,
	Champion,
	LeaderCategory,
	PictureRow,
	PictureTable,
	PlayIn,
	PlayInGame,
	PlayInSlot,
	PlayoffStage,
	PlayoffStageEntry,
	PlayoffStageStatus,
	PlayoffTeam,
	PlayoffsFeed,
	PlayoffsState,
	Series,
	SeriesGame,
	SeriesSide
} from '#lib/contract/playoffs.ts';
import type {
	FinalsGame,
	FinalsMvp,
	HeadToHeadBar,
	HeadToHeadStat,
	PlayerPostseasonAverages,
	PlayoffsFinalsFeed,
	RoadTeam
} from '#lib/contract/playoffs-finals.ts';
import { CONFERENCE_TITLE, PLAY_IN_TITLE, seriesSummary } from '#lib/feed/postseason-mark-props.ts';
import { leader, tipParts, video } from '#lib/feed/props.ts';
import { clinchView } from '#lib/feed/standings-props.ts';
import { feedDate } from '#lib/feed/team-props.ts';
import { formatNumber } from '#lib/format/locale.ts';
import {
	domain,
	segments,
	type ChartBoundaries,
	type ChartPoint
} from '#lib/game/win-probability.ts';
import { m } from '#lib/paraglide/messages.js';
import type {
	AverageRowView,
	AwardView,
	BarSideView,
	BarView,
	ChampionHeroView,
	ConferenceMvpView,
	FinalsChartView,
	FinalsMvpView,
	HeadToHeadView,
	LeaderRowView,
	LeaderTabView,
	PictureRowView,
	PictureTableView,
	PlayInGameView,
	PlayInSlotView,
	PlayInView,
	PlayoffsHeaderView,
	PlayoffsSectionId,
	PlayoffBracketView,
	PlayoffsView,
	PlayoffStageView,
	RoadCardView,
	SeriesCardView,
	SeriesGameRowView,
	SeriesGameView,
	SeriesHeroSideView,
	SeriesPageGameSideView,
	SeriesPageGameView,
	SeriesPageView,
	SeriesSideView
} from '#lib/playoffs/types.ts';
import { teamLabel, teamMark, type TeamMarkTeam } from '#lib/team/mark.ts';

const NO_VALUE = '—';
const SEPARATOR = ' · ';
const DATE_SEPARATOR = ' – ';

const percent = (value: number): string =>
	formatNumber(value, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
const decimal = (value: number): string =>
	formatNumber(value, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const orDash = (value: number | null, format: (v: number) => string): string =>
	value === null ? NO_VALUE : format(value);
const integer = (value: number): string => formatNumber(value);

const STAGE_LABEL: Record<PlayoffStage, () => string> = {
	playin: m.playoffs_stage_playin,
	round_1: m.playoffs_stage_r1,
	round_2: m.playoffs_stage_r2,
	round_3: m.playoffs_stage_r3,
	finals: m.playoffs_stage_finals
};

const STATUS_LABEL: Record<PlayoffStageStatus, () => string> = {
	complete: m.playoffs_status_complete,
	in_progress: m.playoffs_status_in_progress,
	next: m.playoffs_status_next,
	upcoming: m.playoffs_status_upcoming
};

const ROUND_STATE: Record<number, () => string> = {
	1: m.playoffs_state_r1,
	2: m.playoffs_state_r2,
	3: m.playoffs_state_r3
};

const ROUND_LABEL: Record<number, () => string> = {
	1: m.playoffs_round_1,
	2: m.playoffs_round_2,
	3: m.playoffs_round_3,
	4: m.playoffs_round_4
};

const BAR_LABEL: Record<HeadToHeadStat, () => string> = {
	points: m.playoffs_bar_ppg,
	field_goal_pct: m.playoffs_bar_fg,
	effective_fg_pct: m.playoffs_bar_efg,
	assists: m.playoffs_bar_ast,
	rebounds: m.playoffs_bar_reb,
	blocks: m.playoffs_bar_blk,
	steals: m.playoffs_bar_stl,
	technical_fouls: m.playoffs_bar_tech
};

const BAR_FORMAT: Record<HeadToHeadStat, (value: number) => string> = {
	points: decimal,
	field_goal_pct: percent,
	effective_fg_pct: percent,
	assists: decimal,
	rebounds: decimal,
	blocks: decimal,
	steals: decimal,
	technical_fouls: integer
};

const LEADER_LABEL: Record<LeaderCategory, () => string> = {
	points: m.playoffs_leader_pts,
	rebounds: m.playoffs_leader_reb,
	assists: m.playoffs_leader_ast,
	steals: m.playoffs_leader_stl,
	blocks: m.playoffs_leader_blk,
	field_goal_pct: m.playoffs_leader_fg,
	threes_made: m.playoffs_leader_3pm,
	double_doubles: m.playoffs_leader_dd,
	minutes: m.playoffs_leader_min
};

// The code a row draws: that season's code, else today's (ADR 0055).
const drawn = (entry: { teamCode: string | null; seasonCode: string | null }): string =>
	entry.seasonCode ?? entry.teamCode ?? NO_VALUE;

const PLAYER_AWARD_NAME: Partial<Record<AwardCode, () => string>> = {
	mvp: m.playoffs_award_mvp,
	dpoy: m.playoffs_award_dpoy,
	roy: m.playoffs_award_roy,
	sixth_man: m.playoffs_award_6moy,
	mip: m.playoffs_award_mip,
	cpoy: m.playoffs_award_cpoy,
	finals_mvp: m.playoffs_award_fmvp,
	east_finals_mvp: m.playoffs_award_ecf,
	west_finals_mvp: m.playoffs_award_wcf,
	all_star_mvp: m.playoffs_award_asg,
	cup_mvp: m.playoffs_award_cup,
	twyman_stokes: m.playoffs_award_twyman
};

// The twyman_stokes award has no short code: its card has no code chip.
const AWARD_CODE: Partial<Record<AwardCode, () => string>> = {
	mvp: m.playoffs_code_mvp,
	dpoy: m.playoffs_code_dpoy,
	roy: m.playoffs_code_roy,
	sixth_man: m.playoffs_code_6moy,
	mip: m.playoffs_code_mip,
	cpoy: m.playoffs_code_cpoy,
	finals_mvp: m.playoffs_code_fmvp,
	east_finals_mvp: m.playoffs_code_ecf,
	west_finals_mvp: m.playoffs_code_wcf,
	all_star_mvp: m.playoffs_code_asg,
	cup_mvp: m.playoffs_code_cup
};

// One key per team number, so no ordinal is formatted in code.
const TEAM_AWARD_NAME: Partial<Record<AwardCode, Record<number, () => string>>> = {
	cup_all_tournament: { 0: m.playoffs_award_cup_team },
	all_nba: {
		1: m.playoffs_award_all_nba_1,
		2: m.playoffs_award_all_nba_2,
		3: m.playoffs_award_all_nba_3
	},
	all_rookie: { 1: m.playoffs_award_all_rookie_1, 2: m.playoffs_award_all_rookie_2 },
	all_defensive: { 1: m.playoffs_award_all_defense_1, 2: m.playoffs_award_all_defense_2 }
};

/** The name of an award written from its code and team number in the page language; null for a code the page does not know. */
export function awardName(code: AwardCode, team: number | null): string | null {
	const teamNames = TEAM_AWARD_NAME[code];
	if (teamNames) return teamNames[team ?? 0]?.() ?? null;
	return PLAYER_AWARD_NAME[code]?.() ?? null;
}

/** The short code of a player award in the page language; null when it has none. */
export function awardShortCode(code: AwardCode): string | null {
	return AWARD_CODE[code]?.() ?? null;
}

// A historical side has no team color: it is drawn as the guest sigla box (ADR 0054).
const strip = (team: PlayoffTeam): { primary: string; secondary: string } | null =>
	!team.historical && team.colors.primary !== null && team.colors.secondary !== null
		? { primary: team.colors.primary, secondary: team.colors.secondary }
		: null;

const fullName = (team: PlayoffTeam): string =>
	[team.city, team.name].filter(Boolean).join(' ') || teamLabel(teamMark(team));

const code = (team: {
	code: string | null;
	name: string | null;
	seasonCode?: string | null;
	historical?: boolean;
}): string =>
	team.historical && team.seasonCode ? team.seasonCode : (team.code ?? team.name ?? NO_VALUE);

const monthDay: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };

function dateRange(first: string, last: string): string {
	const start = feedDate(first, monthDay);
	return first === last ? start : `${start}${DATE_SEPARATOR}${feedDate(last, monthDay)}`;
}

function stageDates(entry: PlayoffStageEntry): string {
	if (entry.firstDate === null || entry.lastDate === null) return m.playoffs_tbd();
	return dateRange(entry.firstDate, entry.lastDate);
}

function stageView(entry: PlayoffStageEntry): PlayoffStageView {
	return {
		key: entry.stage,
		label: STAGE_LABEL[entry.stage](),
		dates: stageDates(entry),
		status: entry.status,
		statusLabel: STATUS_LABEL[entry.status]()
	};
}

// The Finals series is the bracket entry with no conference; its summary is composed from its wins (ADR 0055).
function finalsStateLine(feed: PlayoffsFeed): string {
	const finals = feed.bracket.find((series) => series.conference === null);
	const summary = finals ? seriesSummaryOf(finals) : null;
	return feed.finalsGame !== null && summary !== null
		? m.playoffs_state_finals_game({ n: formatNumber(feed.finalsGame), summary })
		: m.playoffs_state_finals();
}

function seriesSummaryOf(
	series: Series,
	words?: Parameters<typeof seriesSummary>[3]
): string | null {
	const topCode = series.top.team?.code ?? null;
	const bottomCode = series.bottom.team?.code ?? null;
	const winner =
		series.winner === null
			? null
			: series.winner === topCode
				? 'first'
				: series.winner === bottomCode
					? 'second'
					: null;
	return seriesSummary(
		{ label: series.top.team ? code(series.top.team) : NO_VALUE, wins: series.top.wins },
		{ label: series.bottom.team ? code(series.bottom.team) : NO_VALUE, wins: series.bottom.wins },
		winner,
		words
	);
}

function stateLine(feed: PlayoffsFeed): string {
	switch (feed.state) {
		case 'picture':
			return m.playoffs_state_picture();
		case 'playin':
			return m.playoffs_state_playin();
		case 'playoffs':
			return (
				(feed.currentRound === null ? undefined : ROUND_STATE[feed.currentRound]?.()) ??
				m.playoffs_title()
			);
		case 'finals':
			return finalsStateLine(feed);
		case 'complete':
			return m.playoffs_state_complete();
	}
}

function heroView(champion: Champion, finals: Series | undefined): ChampionHeroView {
	const year = feedDate(champion.lastDate, { year: 'numeric' });
	const mark = teamMark(champion.team);
	const opponentTeam = [finals?.top.team, finals?.bottom.team].find(
		(team) => team != null && team.code !== champion.team.code
	);
	const opponent = opponentTeam
		? (opponentTeam.city ?? opponentTeam.name ?? teamLabel(teamMark(opponentTeam)))
		: NO_VALUE;
	const games = (finals?.games ?? [])
		.filter((game) => game.status === 'final')
		.map((game) => {
			const side =
				game.home.code === champion.team.code
					? 'home'
					: game.away.code === champion.team.code
						? 'away'
						: null;
			const other = side === 'home' ? 'away' : 'home';
			const score =
				side && game.score
					? `${formatNumber(game.score[side])}–${formatNumber(game.score[other])}`
					: NO_VALUE;
			const win = side !== null && game.winner === side;
			return {
				key: game.id,
				label: m.playoffs_game_tab({ n: formatNumber(game.number) }),
				score,
				win,
				spoken: (win ? m.playoffs_hero_game_won : m.playoffs_hero_game_lost)({
					n: formatNumber(game.number),
					score
				})
			};
		});
	return {
		label: m.playoffs_hero_label({ year }),
		team: mark,
		city: champion.team.city,
		name: champion.team.name ?? teamLabel(mark),
		subline: m.playoffs_hero_subline({
			won: formatNumber(champion.wins),
			lost: formatNumber(champion.losses),
			opponent,
			dates: dateRange(champion.firstDate, champion.lastDate)
		}),
		accent: champion.accent ?? null,
		games
	};
}

function bracketKicker(feed: PlayoffsFeed): string {
	return m.playoffs_bracket_kicker({
		year: feedDate(feed.postseasonDates.lastDate, { year: 'numeric' })
	});
}

function headerView(feed: PlayoffsFeed, past: boolean): PlayoffsHeaderView {
	return {
		season: feed.season,
		stateLine: stateLine(feed),
		// A feed with no play-in has a `playin` entry that must not be drawn (ADR 0046).
		stages: feed.stages
			.filter((entry) => entry.stage !== 'playin' || feed.playIn !== null)
			.map(stageView),
		hero: feed.champion
			? heroView(
					feed.champion,
					feed.bracket.find((series) => series.conference === null)
				)
			: null,
		tag: past ? m.past_season_tag({ label: feed.season }) : null
	};
}

function pictureRow(row: PictureRow): PictureRowView {
	return {
		team: teamMark(row.team),
		seed: row.seed === null ? NO_VALUE : String(row.seed),
		record:
			row.wins === null || row.losses === null
				? NO_VALUE
				: `${formatNumber(row.wins)}-${formatNumber(row.losses)}`,
		gamesBehind: row.gamesBehind ?? NO_VALUE,
		clinch: row.clinch ? clinchView(row.clinch) : null,
		strip: strip(row.team),
		line: row.line
	};
}

function pictureView(table: PictureTable): PictureTableView {
	return {
		key: table.conference,
		title: CONFERENCE_TITLE[table.conference](),
		rows: table.rows.map(pictureRow)
	};
}

function slotPlace(slot: PlayInSlot): string | null {
	const { label } = slot;
	switch (label.key) {
		case 'place':
			return label.place === null
				? null
				: m.playoffs_playin_place({ place: formatNumber(label.place) });
		case 'loser_of':
			return label.game === null
				? null
				: m.playoffs_playin_loser({ game: PLAY_IN_TITLE[label.game]() });
		case 'winner_of':
			return label.game === null
				? null
				: m.playoffs_playin_winner({ game: PLAY_IN_TITLE[label.game]() });
	}
}

// The game is final and the other side won it.
function slotLoser(slot: PlayInSlot, game: PlayInGame['game']): boolean {
	if (!game || game.status !== 'final' || game.winner === null || slot.team?.code == null) {
		return false;
	}
	return game[game.winner].code !== slot.team.code;
}

function slotView(slot: PlayInSlot, game: PlayInGame['game']): PlayInSlotView {
	if (slot.team) {
		const team = teamMark(slot.team);
		return {
			team,
			label: teamLabel(team),
			place: null,
			currently: null,
			loser: slotLoser(slot, game)
		};
	}
	return {
		team: null,
		label: m.playoffs_tbd_slot(),
		place: slotPlace(slot),
		currently: slot.currently
			? m.playoffs_currently({ team: teamLabel(teamMark(slot.currently)) })
			: null,
		loser: false
	};
}

// The game lists away and home; a slot takes the score of the team it holds.
function slotScore(slot: PlayInSlot, game: PlayInGame['game']): string | null {
	if (!game?.score || slot.team?.code == null) return null;
	if (slot.team.code === game.away.code) return formatNumber(game.score.away);
	if (slot.team.code === game.home.code) return formatNumber(game.score.home);
	return null;
}

function notes(entry: PlayInGame): PlayInGameView['notes'] {
	const { game, outcome } = entry;
	if (!game || !outcome || game.winner === null) return [];
	const winner = code(game[game.winner]);
	const loser = code(game[game.winner === 'away' ? 'home' : 'away']);
	const lines: PlayInGameView['notes'] = [];
	if (outcome.seed !== null) {
		lines.push({
			text: m.playoffs_playin_to_seed({ team: winner, seed: formatNumber(outcome.seed) }),
			kind: 'seed'
		});
	}
	if (outcome.loserOut) lines.push({ text: m.playoffs_playin_out({ team: loser }), kind: 'out' });
	return lines;
}

function playInGame(entry: PlayInGame): PlayInGameView {
	const { game } = entry;
	const top = slotScore(entry.top, game);
	const bottom = slotScore(entry.bottom, game);
	const tip = game ? tipParts(game.startTime) : null;
	return {
		gameId: game?.id ?? '',
		linked: game?.detailAvailable ?? false,
		key: entry.kind,
		title: PLAY_IN_TITLE[entry.kind](),
		top: slotView(entry.top, game),
		bottom: slotView(entry.bottom, game),
		score: top !== null && bottom !== null ? { top, bottom } : null,
		when:
			game && tip && game.status !== 'final'
				? `${feedDate(game.date, monthDay)}${SEPARATOR}${tip.tipTime} ${tip.tipSuffix}`
				: null,
		notes: notes(entry)
	};
}

function playInView(playIn: PlayIn): PlayInView {
	return {
		key: playIn.conference,
		title: CONFERENCE_TITLE[playIn.conference](),
		games: playIn.games.map(playInGame)
	};
}

function finalsMvpView(mvp: FinalsMvp | null, feed: PlayoffsFeed): FinalsMvpView {
	if (mvp === null) return null;
	return {
		name: mvp.name,
		photo: mvp.photoUrl,
		team: drawn(mvp),
		...mvpTeam(feed, mvp),
		stats: [
			{
				key: 'ppg',
				label: m.playoffs_mvp_ppg(),
				value: orDash(mvp.points, decimal),
				accent: false
			},
			{
				key: 'best',
				label: m.playoffs_mvp_best(),
				value: mvp.bestGame ? integer(mvp.bestGame.points) : NO_VALUE,
				accent: true
			},
			{
				key: 'rebast',
				label: m.playoffs_mvp_reb_ast(),
				value: `${orDash(mvp.rebounds, decimal)}${SEPARATOR}${orDash(mvp.assists, decimal)}`,
				accent: false
			},
			{
				key: 'games',
				label: m.playoffs_mvp_games(),
				value: orDash(mvp.games, integer),
				accent: false
			}
		]
	};
}

function conferenceMvps(feed: PlayoffsFeed): ConferenceMvpView[] {
	const sources = [
		{ key: 'east', code: 'east_finals_mvp', label: m.playoffs_ecf_mvp },
		{ key: 'west', code: 'west_finals_mvp', label: m.playoffs_wcf_mvp }
	] as const;
	return sources.flatMap((source) => {
		const winner = feed.awards?.find((award) => award.code === source.code)?.winners[0];
		return winner
			? [
					{
						key: source.key,
						name: winner.name,
						photo: winner.photoUrl,
						label: source.label(),
						team: drawn(winner),
						...mvpTeam(feed, winner)
					}
				]
			: [];
	});
}

// A curve the geometry rejects (a bad probability, a game end before the last point) draws no chart.
function chartView(entry: FinalsGame): FinalsChartView | null {
	const curve = entry.winProbability;
	if (curve === null) return null;
	const points: ChartPoint[] = curve.points.map((point) => ({
		elapsedSeconds: point.elapsedSeconds,
		homeWinProbability: point.winProbability
	}));
	const boundaries: ChartBoundaries = {
		periods: curve.periods.periods.map((period) => ({
			label: String(period.number),
			start: period.startElapsedSeconds
		})),
		end: curve.periods.endElapsedSeconds
	};
	try {
		const span = domain(points, boundaries);
		segments(points);
		return {
			points,
			boundaries,
			deficit: entry.largestDeficit
				? {
						label: m.playoffs_largest_deficit({ n: formatNumber(entry.largestDeficit.points) }),
						left: Math.min(1, Math.max(0, entry.largestDeficit.elapsedSeconds / span))
					}
				: null
		};
	} catch (error) {
		if (error instanceof RangeError) return null;
		throw error;
	}
}

function seriesGame(entry: FinalsGame, champion: string | null): SeriesGameView {
	const { game } = entry;
	const winnerSide = game.winner;
	const winner = winnerSide ? code(game[winnerSide]) : NO_VALUE;
	let score = NO_VALUE;
	if (game.score) {
		const loserSide = winnerSide === 'away' ? 'home' : 'away';
		score = winnerSide
			? `${formatNumber(game.score[winnerSide])}–${formatNumber(game.score[loserSide])}`
			: `${formatNumber(game.score.away)}–${formatNumber(game.score.home)}`;
	}
	const highlight = entry.highlights?.[0];
	return {
		gameId: game.id,
		linked: game.detailAvailable,
		key: game.id,
		tab: m.playoffs_game_tab({ n: formatNumber(game.number) }),
		winner,
		championWon: champion !== null && winnerSide !== null && winner === champion,
		score,
		overtime: game.overtime,
		video: highlight ? video(highlight) : null,
		chart: chartView(entry),
		scoreLine: game.score
			? m.playoffs_game_score({
					away: code(game.away),
					awayScore: formatNumber(game.score.away),
					homeScore: formatNumber(game.score.home),
					home: code(game.home)
				})
			: NO_VALUE,
		leaders: entry.leaders
			? { away: leader(entry.leaders.away, game.away), home: leader(entry.leaders.home, game.home) }
			: null
	};
}

function slotLabel(label: SeriesSide['label']): string {
	const conference = CONFERENCE_TITLE[label.conference]();
	const part = (value: number | null): string => orDash(value, integer);
	switch (label.key) {
		case 'seed':
			return m.playoffs_slot_seed({ conference, seed: part(label.seed) });
		case 'playin_winner':
			return m.playoffs_slot_playin_winner({ conference });
		case 'round_1_winner':
			return m.playoffs_slot_r1_winner({ conference, n: part(label.series) });
		case 'round_2_winner':
			return m.playoffs_slot_r2_winner({ conference, n: part(label.series) });
		case 'round_3_winner':
			return m.playoffs_slot_r3_winner({ conference });
	}
}

function seriesSide(side: SeriesSide, series: Series, past: boolean): SeriesSideView {
	if (side.team) {
		return {
			team: teamMark(side.team),
			seed: side.seed === null && past ? '' : orDash(side.seed, integer),
			wins: orDash(side.wins, integer),
			strip: strip(side.team),
			accent: (side === series.top ? series.accent?.top : series.accent?.bottom) ?? null,
			filled: side.wins ?? 0,
			label: code(side.team),
			note: null,
			loser: series.winner !== null && side.team.code !== series.winner
		};
	}
	return {
		team: null,
		seed: '',
		wins: '',
		strip: null,
		accent: null,
		filled: 0,
		label: slotLabel(side.label),
		note: side.currently
			? m.playoffs_currently({ team: teamLabel(teamMark(side.currently)) })
			: m.playoffs_tbd_slot(),
		loser: false
	};
}

function roundTitle(series: Series): string {
	if (series.conference === null) return ROUND_LABEL[4]();
	const round = ROUND_LABEL[series.round]?.() ?? NO_VALUE;
	return `${CONFERENCE_TITLE[series.conference]()}${SEPARATOR}${round}`;
}

const scoreText = (value: number | null): string => orDash(value, integer);

// The resolved color of the side that won the game; null with no winner or no accent.
function winnerAccent(game: SeriesGame, series: Series): string | null {
	if (game.winner === null) return null;
	const winnerCode = game[game.winner].code;
	if (series.top.team?.code === winnerCode) return series.accent?.top ?? null;
	if (series.bottom.team?.code === winnerCode) return series.accent?.bottom ?? null;
	return null;
}

// A cell reads "G1", "at QXH" (the home team), the OT tag and, once final, the winner and its score.
function seriesGameRow(game: SeriesGame, series: Series): SeriesGameRowView {
	const final = game.status === 'final';
	const decided = final && game.winner !== null;
	const winnerSide = game.winner;
	const loserSide = winnerSide === 'away' ? 'home' : 'away';
	return {
		gameId: game.id,
		linked: game.detailAvailable,
		key: game.id,
		number: m.playoffs_game_n({ n: formatNumber(game.number) }),
		at: m.playoffs_series_at({ team: code(game.home) }),
		overtimeTag: overtimeTag(game),
		winner:
			decided && winnerSide !== null
				? {
						team: teamMark(game[winnerSide]),
						code: code(game[winnerSide]),
						score: game.score
							? `${scoreText(game.score[winnerSide])}–${scoreText(game.score[loserSide])}`
							: NO_VALUE
					}
				: null,
		accent: winnerAccent(game, series),
		away: {
			code: code(game.away),
			score: scoreText(game.score?.away ?? null),
			loser: decided && game.winner !== 'away'
		},
		home: {
			code: code(game.home),
			score: scoreText(game.score?.home ?? null),
			loser: decided && game.winner !== 'home'
		},
		final,
		overtime: game.overtime,
		when: final
			? null
			: `${feedDate(game.date, monthDay)}${game.venue ? `${SEPARATOR}${game.venue}` : ''}`
	};
}

// The side the result shows first: the winner, else the one with more wins, else the top.
function leadSide(series: Series): 'top' | 'bottom' {
	if (series.winner !== null) return series.bottom.team?.code === series.winner ? 'bottom' : 'top';
	const { top, bottom } = series;
	return top.wins !== null && bottom.wins !== null && bottom.wins > top.wins ? 'bottom' : 'top';
}

function seriesCard(series: Series, past: boolean): SeriesCardView {
	const top = seriesSide(series.top, series, past);
	const bottom = seriesSide(series.bottom, series, past);
	const teams = Number(series.top.team !== null) + Number(series.bottom.team !== null);
	const final = series.conference === null;
	const complete = series.status === 'complete';
	return {
		id: series.id,
		name: [roundTitle(series), top.label, bottom.label].join(SEPARATOR),
		roundTitle: roundTitle(series),
		top,
		bottom,
		decided: teams === 2 ? 'both' : teams === 1 ? 'one' : 'none',
		final,
		complete,
		champion: final && complete,
		score: seriesSummaryOf(series) ?? NO_VALUE,
		headline:
			seriesSummaryOf(series, {
				wins: m.playoffs_result_wins,
				leads: m.playoffs_result_leads
			}) ?? NO_VALUE,
		lead: leadSide(series),
		games: series.games.map((game) => seriesGameRow(game, series))
	};
}

function bracketView(feed: PlayoffsFeed, past: boolean): PlayoffBracketView {
	return {
		kicker: bracketKicker(feed),
		series: feed.bracket.map((series) => seriesCard(series, past))
	};
}

function roadCard(road: RoadTeam): RoadCardView {
	const team = teamMark(road.team);
	return {
		team,
		name: fullName(road.team),
		seedLine:
			road.seed === null && road.regularSeason === null
				? NO_VALUE
				: m.playoffs_road_seed({
						seed: road.seed === null ? NO_VALUE : formatNumber(road.seed),
						record: road.regularSeason ?? NO_VALUE
					}),
		postseason: road.postseason ?? NO_VALUE,
		series: road.series.map((series) => ({
			key: String(series.round),
			round: ROUND_LABEL[series.round]?.() ?? NO_VALUE,
			opponentSeed:
				series.opponentSeed === null
					? NO_VALUE
					: m.playoffs_road_opponent_seed({ seed: formatNumber(series.opponentSeed) }),
			opponent: teamMark(series.opponent),
			strip: strip(series.opponent),
			result:
				series.wins === null || series.losses === null
					? NO_VALUE
					: `${formatNumber(series.wins)}–${formatNumber(series.losses)}${
							series.result === 'win'
								? ` ${m.game_last_game_win()}`
								: series.result === 'loss'
									? ` ${m.game_last_game_loss()}`
									: ''
						}`,
			loss: series.result === 'loss'
		}))
	};
}

// The team object of a code among the bracket's sides; null when no side has it.
function bracketTeam(feed: PlayoffsFeed, teamCode: string | null): PlayoffTeam | null {
	if (teamCode === null) return null;
	for (const series of feed.bracket)
		for (const side of [series.top, series.bottom])
			if (side.team?.code === teamCode) return side.team;
	return null;
}

// The team name and logo of an MVP come from the bracket; the color is the feed's (ADR 0072).
function mvpTeam(
	feed: PlayoffsFeed,
	entry: { teamCode: string | null; seasonCode: string | null; accent: string | null }
): { teamName: string; mark: TeamMarkTeam; accent: string | null } {
	const team = bracketTeam(feed, entry.teamCode);
	return {
		teamName: team ? fullName(team) : drawn(entry),
		mark: team ? teamMark(team) : { code: drawn(entry), name: null, city: null, guest: false },
		accent: entry.accent ?? null
	};
}

// The primary color of a finalist; none for a historical team.
function colorOf(finals: PlayoffsFinalsFeed, teamCode: string): string | null {
	const team = finals.road.find((road) => road.team.code === teamCode)?.team;
	return team && !team.historical ? team.colors.primary : null;
}

// Each half is drawn at its value over the larger of the two: drawing scale, not a statistic.
// Which side is better is the feed's `better`.
function barView(bar: HeadToHeadBar, finals: PlayoffsFinalsFeed): BarView {
	const format = BAR_FORMAT[bar.stat];
	const largest = Math.max(...bar.values.map((entry) => entry.value ?? 0));
	const side = (entry: HeadToHeadBar['values'][number]): BarSideView => ({
		value: orDash(entry.value, format),
		share: entry.value === null || largest <= 0 ? 0 : entry.value / largest,
		better: bar.better !== null && bar.better === entry.teamCode,
		color: colorOf(finals, entry.teamCode)
	});
	return {
		key: bar.stat,
		label: BAR_LABEL[bar.stat](),
		sides: [side(bar.values[0]), side(bar.values[1])]
	};
}

function averageRow(player: PlayerPostseasonAverages): AverageRowView {
	return {
		id: player.playerId,
		name: player.name,
		photo: player.photoUrl,
		points: orDash(player.points, decimal),
		rebounds: orDash(player.rebounds, decimal),
		assists: orDash(player.assists, decimal),
		blocks: orDash(player.blocks, decimal),
		fieldGoalPct: orDash(player.fieldGoalPct, percent)
	};
}

function headToHeadView(finals: PlayoffsFinalsFeed): HeadToHeadView {
	return {
		records: finals.headToHead.records.map((entry) => ({
			team: drawn(entry),
			record: entry.record ?? NO_VALUE
		})),
		bars: finals.headToHead.bars.map((bar) => barView(bar, finals)),
		averages:
			finals.averages === null
				? null
				: finals.averages.map((roster) => ({
						key: roster.teamCode,
						label: drawn(roster),
						rows: roster.players.map(averageRow)
					}))
	};
}

function leaderTabs(feed: PlayoffsFeed): LeaderTabView[] {
	return (feed.leaders ?? []).map((group) => {
		const rows: LeaderRowView[] = group.leaders.map((entry) => ({
			id: entry.playerId,
			rank: String(entry.rank),
			name: entry.name,
			photo: entry.photoUrl,
			team: drawn(entry),
			value: entry.value
		}));
		return {
			key: group.category,
			label: LEADER_LABEL[group.category](),
			first: rows[0] ?? null,
			rest: rows.slice(1)
		};
	});
}

function awardView(award: Award): AwardView {
	const winners = award.winners.map((winner) => ({
		id: winner.playerId,
		name: winner.name,
		photo: winner.photoUrl,
		team: drawn(winner)
	}));
	if (TEAM_AWARD_NAME[award.code]) {
		return {
			key: `${award.code}-${award.team ?? 0}`,
			name: awardName(award.code, award.team) ?? NO_VALUE,
			code: null,
			kind: 'team',
			winners
		};
	}
	return {
		key: award.code,
		name: awardName(award.code, award.team) ?? NO_VALUE,
		code: awardShortCode(award.code),
		kind: 'player',
		winners: winners.slice(0, 1)
	};
}

const PLAY_IN_COLLAPSED: PlayoffsState[] = ['playoffs', 'finals', 'complete'];

// Section order by state. A section whose block is missing is removed; the others keep their order.
function sectionOrder(state: PlayoffsState): PlayoffsSectionId[] {
	switch (state) {
		case 'picture':
			return ['picture', 'bracket', 'play-in', 'leaders', 'awards'];
		case 'playin':
		case 'playoffs':
			return ['bracket', 'play-in', 'leaders', 'awards'];
		case 'finals':
			return [
				'bracket',
				'play-in',
				'finals-mvp',
				'series',
				'road',
				'head-to-head',
				'leaders',
				'awards'
			];
		case 'complete':
			return [
				'finals-mvp',
				'series',
				'road',
				'head-to-head',
				'leaders',
				'bracket',
				'play-in',
				'awards'
			];
	}
}

/**
 * Turns the playoffs feed, and the finals feed when it is in, into the page's props. Every
 * value is the feed's own: the page computes nothing. The code only decides which fixed
 * words to write and which section is present.
 */
export function toPlayoffsView(
	feed: PlayoffsFeed,
	finals: PlayoffsFinalsFeed | null,
	options: { past?: boolean } = {}
): PlayoffsView {
	const past = options.past ?? false;
	// Past seasons only (ADR 0049): the head to head needs a bar value, and a null seed draws no
	// number. The current season keeps its rules: the head to head follows the finals feed, a null
	// seed draws a dash.
	const statistics =
		finals !== null &&
		(!past || finals.headToHead.bars.some((bar) => bar.values.some((v) => v.value !== null)));
	const finalsMvp = finals ? finalsMvpView(finals.finalsMvp, feed) : null;
	const conference = conferenceMvps(feed);
	const present: Record<PlayoffsSectionId, boolean> = {
		picture: feed.state === 'picture',
		bracket: true,
		'play-in': feed.playIn !== null,
		'finals-mvp': finals !== null && (finalsMvp !== null || conference.length > 0),
		series: finals !== null && finals.games.length > 0,
		road: finals !== null,
		'head-to-head': statistics,
		leaders: feed.leaders !== null,
		awards: feed.awards !== null
	};
	return {
		header: headerView(feed, past),
		sections: sectionOrder(feed.state).filter((id) => present[id]),
		picture: feed.picture.map(pictureView),
		playIn: (feed.playIn ?? []).map(playInView),
		playInCollapsed: PLAY_IN_COLLAPSED.includes(feed.state),
		finalsMvp,
		conferenceMvps: conference,
		series: finals ? finals.games.map((entry) => seriesGame(entry, finals.champion)) : [],
		bracket: bracketView(feed, past),
		road: finals ? finals.road.map(roadCard) : [],
		headToHead: statistics && finals ? headToHeadView(finals) : null,
		leaders: leaderTabs(feed),
		awards: (feed.awards ?? []).map(awardView)
	};
}

// A feed stored before the exact count has only the flag.
function overtimeTag(game: SeriesGame): string | null {
	const periods = game.overtimePeriods ?? (game.overtime ? 1 : 0);
	if (periods <= 0) return null;
	return periods === 1 ? m.playoffs_ot() : m.playoffs_ot_n({ n: formatNumber(periods) });
}

function heroSide(
	side: SeriesSide,
	series: Series,
	accent: string | null | undefined,
	past: boolean
): SeriesHeroSideView {
	const team = side.team as PlayoffTeam;
	const other = side === series.top ? series.bottom : series.top;
	let lead = true;
	if (series.winner !== null) lead = team.code === series.winner;
	else if (side.wins !== null && other.wins !== null) lead = side.wins >= other.wins;
	return {
		team: teamMark(team),
		code: code(team),
		seed:
			side.seed === null && past
				? null
				: m.playoffs_series_seed({ seed: orDash(side.seed, integer) }),
		wins: orDash(side.wins, integer),
		accent: accent ?? null,
		lead,
		loser: series.status === 'complete' && series.winner !== null && team.code !== series.winner
	};
}

function pageGame(
	game: SeriesGame,
	series: Series,
	finals: PlayoffsFinalsFeed | null
): SeriesPageGameView {
	const topCode = series.top.team?.code ?? null;
	const order: ['away' | 'home', 'away' | 'home'] =
		game.home.code === topCode ? ['home', 'away'] : ['away', 'home'];
	const side = (key: 'away' | 'home'): SeriesPageGameSideView => ({
		team: teamMark(game[key]),
		code: code(game[key]),
		score: scoreText(game.score?.[key] ?? null),
		loser: game.status === 'final' && game.winner !== null && game.winner !== key
	});
	const entry =
		series.conference === null ? finals?.games.find((e) => e.game.id === game.id) : null;
	const pair = entry?.leaders
		? order.map((key) => {
				const lead = entry.leaders![key];
				return { name: lead.displayName, pts: orDash(lead.points, integer) };
			})
		: null;
	const rule: SeriesPageGameView['rule'] =
		game.winner === null ? null : { accent: winnerAccent(game, series) };
	return {
		gameId: game.id,
		linked: game.detailAvailable,
		key: game.id,
		title: m.playoffs_series_game({ n: formatNumber(game.number) }),
		meta: m.playoffs_series_game_venue({
			date: feedDate(game.date, monthDay),
			venue: game.venue ?? m.playoffs_series_at({ team: code(game.home) })
		}),
		overtimeTag: overtimeTag(game),
		sides: [side(order[0]), side(order[1])],
		leaders: pair
			? m.playoffs_series_leaders({
					name: pair[0].name,
					pts: pair[0].pts,
					name2: pair[1].name,
					pts2: pair[1].pts
				})
			: null,
		rule
	};
}

/**
 * The full series page's props for one series of the bracket. Null for an unknown id and for a
 * series with an undecided side: the page then says the series is not available.
 */
export function toSeriesPageView(
	feed: PlayoffsFeed,
	finals: PlayoffsFinalsFeed | null,
	id: string,
	options: { past?: boolean } = {}
): SeriesPageView | null {
	const series = feed.bracket.find((s) => s.id === id);
	if (!series || !series.top.team || !series.bottom.team) return null;
	const past = options.past ?? false;
	const first = series.games[0];
	const last = series.games[series.games.length - 1];
	return {
		kicker: bracketKicker(feed),
		round: roundTitle(series),
		top: heroSide(series.top, series, series.accent?.top, past),
		bottom: heroSide(series.bottom, series, series.accent?.bottom, past),
		status: seriesSummaryOf(series, {
			wins: m.playoffs_series_status_wins,
			leads: m.playoffs_series_status_leads
		}),
		dates: first ? dateRange(first.date, last.date) : null,
		games: series.games.map((game) => pageGame(game, series, finals))
	};
}
