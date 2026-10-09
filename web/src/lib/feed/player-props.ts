import type {
	AverageRow,
	Averages,
	GameLogEntry,
	InjuryStatus,
	Milestones,
	Opponent,
	PlayerFeed,
	PlayerLive,
	Profile,
	SeasonAverageRow,
	SeasonRow,
	SeasonSplit,
	StatRow
} from '#lib/contract/player.ts';
import { periodText } from '#lib/feed/game-props.ts';
import { tipParts } from '#lib/feed/props.ts';
import { feedDate, gameTagLabel, nextGameView } from '#lib/feed/team-props.ts';
import { formatDate, formatNumber } from '#lib/format/locale.ts';
import type { InfoCell } from '#lib/game/types.ts';
import { m } from '#lib/paraglide/messages.js';
import type {
	AveragesSection,
	AwardView,
	GameLogFilter,
	GameLogSection,
	LiveGameView,
	MilestonesSection,
	PlayerHeaderView,
	PlayerSectionId,
	PlayerSections,
	PlayerTab,
	PlayerView,
	ProfileSection,
	RecentGameRow,
	SeasonsSection,
	StatCell,
	StatColumn,
	StatRowView,
	StatTableView
} from '#lib/player/types.ts';
import { teamMark } from '#lib/team/mark.ts';

const TIME_ZONE = 'America/New_York';
const SEPARATOR = ' · ';
const NO_VALUE = '—';

const TAB_LABELS: Record<PlayerSectionId, () => string> = {
	profile: m.player_tab_profile,
	averages: m.player_tab_averages,
	seasons: m.player_tab_seasons,
	milestones: m.player_tab_milestones,
	'game-log': m.player_tab_game_log,
	awards: m.player_tab_awards
};

const TAB_ORDER: PlayerSectionId[] = [
	'profile',
	'averages',
	'seasons',
	'milestones',
	'game-log',
	'awards'
];

const KEY_OF: Record<PlayerSectionId, keyof PlayerSections> = {
	profile: 'profile',
	averages: 'averages',
	seasons: 'seasons',
	milestones: 'milestones',
	'game-log': 'gameLog',
	awards: 'awards'
};

const INJURY_LABELS: Record<InjuryStatus, () => string> = {
	out: m.injury_status_out,
	doubtful: m.injury_status_doubtful,
	questionable: m.injury_status_questionable,
	probable: m.injury_status_probable,
	'day-to-day': m.injury_status_day_to_day
};

const percent = (v: number) =>
	formatNumber(v, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });

const oneDecimal: Intl.NumberFormatOptions = { minimumFractionDigits: 1, maximumFractionDigits: 1 };
const twoDecimals: Intl.NumberFormatOptions = {
	minimumFractionDigits: 2,
	maximumFractionDigits: 2
};

const one = (v: number) => formatNumber(v, oneDecimal);
const whole = (v: number) => formatNumber(v, { maximumFractionDigits: 0 });
const range = (made: string, attempted: string) => `${made}–${attempted}`;

const score = (team: number, opponent: number) => `${formatNumber(team)}–${formatNumber(opponent)}`;

const opponentOf = (game: { opponent: Opponent; isHome: boolean }) => ({
	team: teamMark(game.opponent),
	isHome: game.isHome
});

function initialAndLast(feed: PlayerFeed): string {
	const initial = Array.from(feed.firstName)[0] ?? '';
	return initial ? `${initial}. ${feed.lastName}` : feed.lastName;
}

function numbered(feed: PlayerFeed, name: string): string {
	return feed.number === null ? name : `#${feed.number} ${name}`;
}

function header(feed: PlayerFeed): PlayerHeaderView {
	const parts = [
		feed.number === null ? null : `#${feed.number}`,
		feed.position,
		`${feed.team.city} ${feed.team.name}`
	].filter((part): part is string => part !== null);
	const injury = feed.injury;
	let updated = '';
	if (injury) {
		const { tipTime, tipSuffix } = tipParts(injury.updatedAt);
		const day = formatDate(new Date(injury.updatedAt), {
			timeZone: TIME_ZONE,
			month: 'short',
			day: 'numeric'
		});
		updated = m.player_injury_updated({ date: `${day}${SEPARATOR}${tipTime} ${tipSuffix}` });
	}
	const summary = feed.summary;
	const ranked = (label: string, value: string, rank: number | null): InfoCell => ({
		label,
		value,
		sub: rank === null ? null : m.player_rank({ rank })
	});
	return {
		teamCode: feed.team.code,
		status: injury
			? { label: INJURY_LABELS[injury.status](), injured: true }
			: { label: m.team_status_active(), injured: false },
		firstName: feed.firstName,
		lastName: feed.lastName,
		line: parts.join(SEPARATOR),
		injury: injury ? { status: injury.status, comment: injury.comment, updated } : null,
		photo: feed.photoUrl,
		stats: summary
			? {
					label: m.team_leaders_meta({ season: summary.season }),
					cells: [
						ranked(m.team_leader_points(), one(summary.points.value), summary.points.rank),
						ranked(m.team_leader_rebounds(), one(summary.rebounds.value), summary.rebounds.rank),
						ranked(m.team_leader_assists(), one(summary.assists.value), summary.assists.rank),
						ranked(
							m.panel_stat_field_goals(),
							percent(summary.fieldGoalPct.value),
							summary.fieldGoalPct.rank
						)
					]
				}
			: null
	};
}

function profileCells(profile: Profile): InfoCell[] {
	const cells: InfoCell[] = [];
	if (profile.height) {
		cells.push({
			label: m.player_profile_height(),
			value: profile.height.display,
			sub: m.player_height_cm({ cm: formatNumber(profile.height.cm) })
		});
	}
	if (profile.weight) {
		cells.push({
			label: m.player_profile_weight(),
			value: m.player_weight_lb({ lb: formatNumber(profile.weight.lb) }),
			sub: m.player_weight_kg({ kg: formatNumber(profile.weight.kg) })
		});
	}
	if (profile.birthDate) {
		cells.push({
			label: m.team_roster_born(),
			value: feedDate(profile.birthDate, { month: 'long', day: 'numeric', year: 'numeric' }),
			sub: profile.age === null ? null : m.player_age({ age: formatNumber(profile.age) })
		});
	}
	if (profile.birthplace) {
		cells.push({
			label: m.team_roster_birthplace(),
			value: profile.birthplace.place,
			sub: profile.birthplace.country
		});
	}
	if (profile.college) {
		cells.push({ label: m.team_roster_college(), value: profile.college, sub: null });
	}
	cells.push(
		profile.draft
			? {
					label: m.player_profile_draft(),
					value: m.player_draft_pick({
						year: profile.draft.year,
						round: profile.draft.round,
						pick: profile.draft.pick
					}),
					sub: profile.draft.teamName
				}
			: { label: m.player_profile_draft(), value: m.player_undrafted(), sub: null }
	);
	if (profile.seasons !== null) {
		cells.push({
			label: m.player_tab_seasons(),
			value: formatNumber(profile.seasons),
			sub: profile.debutSeason === null ? null : m.player_debut({ season: profile.debutSeason })
		});
	}
	return cells;
}

function liveView(live: PlayerLive): LiveGameView {
	const line = live.line;
	return {
		gameId: live.gameId,
		opponent: opponentOf(live),
		score: score(live.teamScore, live.opponentScore),
		clock: periodText(live.period, live.clock),
		line: line
			? [
					{ label: m.box_minutes(), value: line.minutes, sub: null },
					{ label: m.box_points(), value: formatNumber(line.points), sub: null },
					{ label: m.box_rebounds(), value: formatNumber(line.rebounds), sub: null },
					{ label: m.box_assists(), value: formatNumber(line.assists), sub: null },
					{
						label: m.box_field_goals(),
						value: range(formatNumber(line.fieldGoalsMade), formatNumber(line.fieldGoalsAttempted)),
						sub: null
					}
				]
			: null
	};
}

// null: the All-Star game, which has no opponent.
const opponentView = (game: GameLogEntry) =>
	game.opponent === null ? null : opponentOf({ opponent: game.opponent, isHome: game.isHome });

function recentRow(game: GameLogEntry): RecentGameRow {
	return {
		gameId: game.gameId,
		linked: game.detailAvailable,
		result: game.result,
		resultLabel: game.result === 'win' ? m.game_last_game_win() : m.game_last_game_loss(),
		date: feedDate(game.date, { month: 'short', day: 'numeric' }),
		opponent: opponentView(game),
		score: score(game.teamScore, game.opponentScore),
		tag: game.tag ? gameTagLabel(game.tag) : null,
		points: formatNumber(game.points),
		line: [
			`${formatNumber(game.rebounds)} ${m.box_rebounds()}`,
			`${formatNumber(game.assists)} ${m.box_assists()}`
		].join(SEPARATOR)
	};
}

function profileSection(feed: PlayerFeed): ProfileSection {
	return {
		cells: profileCells(feed.profile),
		nextGame: feed.nextGame ? nextGameView(feed.nextGame) : null,
		live: feed.live ? liveView(feed.live) : null,
		recent: feed.lastGames.map(recentRow)
	};
}

const averagesColumns = (): StatColumn[] => [
	{ key: 'gp', label: m.player_games_played(), muted: true },
	{ key: 'min', label: m.box_minutes(), muted: true },
	{ key: 'fgPct', label: m.panel_stat_field_goals() },
	{ key: 'tpPct', label: m.panel_stat_three_points() },
	{ key: 'ftPct', label: m.panel_stat_free_throws() },
	{ key: 'reb', label: m.box_rebounds() },
	{ key: 'ast', label: m.box_assists() },
	{ key: 'blk', label: m.box_blocks() },
	{ key: 'stl', label: m.box_steals() },
	{ key: 'pf', label: m.box_fouls(), muted: true },
	{ key: 'tov', label: m.box_turnovers(), muted: true },
	{ key: 'pts', label: m.box_points(), points: true }
];

const averagesCells = (row: AverageRow): StatCell[] => [
	formatNumber(row.gamesPlayed),
	one(row.minutes),
	percent(row.fieldGoalPct),
	percent(row.threePointPct),
	percent(row.freeThrowPct),
	one(row.rebounds),
	one(row.assists),
	one(row.blocks),
	one(row.steals),
	one(row.fouls),
	one(row.turnovers),
	one(row.points)
];

function averagesSection(averages: Averages): AveragesSection | null {
	const { regular, playoffs, career } = averages;
	if (!regular && !playoffs && !career) return null;
	const columns = averagesColumns();
	const empty = (): StatCell[] => columns.map(() => NO_VALUE);
	const row = (
		key: string,
		label: string,
		source: AverageRow | null,
		season: string | null,
		accent = false
	): StatRowView => ({
		key,
		label,
		sub: season,
		accent,
		cells: source ? averagesCells(source) : empty()
	});
	const seasonOf = (own: SeasonAverageRow | null, other: SeasonAverageRow | null) =>
		own?.season ?? other?.season ?? null;
	return {
		columns,
		rows: [
			row('regular', m.player_regular_season(), regular, seasonOf(regular, playoffs)),
			row('playoffs', m.team_schedule_playoffs(), playoffs, seasonOf(playoffs, regular)),
			row('career', m.player_career(), career, null, true)
		]
	};
}

const seasonColumns = (totals: boolean): StatColumn[] => [
	{ key: 'gp', label: m.player_games_played(), muted: true },
	{ key: 'gs', label: m.player_games_started(), muted: true },
	...(totals ? [] : [{ key: 'min', label: m.box_minutes(), muted: true }]),
	{ key: 'fg', label: m.box_field_goals(), wide: true },
	{ key: 'fgPct', label: m.panel_stat_field_goals() },
	{ key: 'tp', label: m.box_three_points(), wide: true },
	{ key: 'tpPct', label: m.panel_stat_three_points() },
	{ key: 'ft', label: m.box_free_throws(), wide: true },
	{ key: 'ftPct', label: m.panel_stat_free_throws() },
	{ key: 'oreb', label: m.box_offensive_rebounds() },
	{ key: 'dreb', label: m.box_defensive_rebounds() },
	{ key: 'reb', label: m.box_rebounds() },
	{ key: 'ast', label: m.box_assists() },
	{ key: 'blk', label: m.box_blocks() },
	{ key: 'stl', label: m.box_steals() },
	{ key: 'pf', label: m.box_fouls(), muted: true },
	{ key: 'tov', label: m.box_turnovers(), muted: true },
	{ key: 'pts', label: m.box_points(), points: true }
];

function seasonCells(row: StatRow, totals: boolean): StatCell[] {
	const n = totals ? whole : one;
	return [
		formatNumber(row.gamesPlayed),
		formatNumber(row.gamesStarted),
		...(totals || row.minutes === null ? [] : [one(row.minutes)]),
		range(n(row.fieldGoalsMade), n(row.fieldGoalsAttempted)),
		percent(row.fieldGoalPct),
		range(n(row.threePointsMade), n(row.threePointsAttempted)),
		percent(row.threePointPct),
		range(n(row.freeThrowsMade), n(row.freeThrowsAttempted)),
		percent(row.freeThrowPct),
		n(row.offensiveRebounds),
		n(row.defensiveRebounds),
		n(row.rebounds),
		n(row.assists),
		n(row.blocks),
		n(row.steals),
		n(row.fouls),
		n(row.turnovers),
		n(row.points)
	];
}

function seasonTable(
	rows: SeasonRow[],
	career: StatRow | undefined,
	totals: boolean
): StatTableView {
	const views: StatRowView[] = rows.map((row) => ({
		key: row.season,
		label: row.season,
		sub: row.teams.join(SEPARATOR),
		cells: seasonCells(row, totals)
	}));
	if (career) {
		views.push({
			key: 'career',
			label: m.player_career(),
			sub: null,
			cells: seasonCells(career, totals)
		});
	}
	return { columns: seasonColumns(totals), rows: views };
}

const splitTables = (split: SeasonSplit) => ({
	perGame: seasonTable(split.perGame, split.career?.perGame, false),
	totals: seasonTable(split.totals, split.career?.totals, true)
});

function seasonsSection(feed: PlayerFeed): SeasonsSection | null {
	const { regular, playoffs } = feed.seasons;
	if (regular.perGame.length === 0) return null;
	return {
		regular: splitTables(regular),
		playoffs: playoffs.perGame.length > 0 ? splitTables(playoffs) : null
	};
}

function milestonesSection(milestones: Milestones | null): MilestonesSection | null {
	if (!milestones) return null;
	const { current, career } = milestones;
	const count = (label: string, now: number, total: number): InfoCell => ({
		label,
		value: formatNumber(now),
		sub: m.player_milestone_career({ value: formatNumber(total) })
	});
	const ratio = (label: string, now: number, total: number): InfoCell => ({
		label,
		value: formatNumber(now, twoDecimals),
		sub: m.player_milestone_career({ value: formatNumber(total, twoDecimals) })
	});
	return {
		meta: milestones.season,
		cells: [
			count(m.player_milestone_double_doubles(), current.doubleDoubles, career.doubleDoubles),
			count(m.player_milestone_triple_doubles(), current.tripleDoubles, career.tripleDoubles),
			count(
				m.player_milestone_disqualifications(),
				current.disqualifications,
				career.disqualifications
			),
			count(m.player_milestone_ejections(), current.ejections, career.ejections),
			count(m.player_milestone_technicals(), current.technicals, career.technicals),
			count(m.player_milestone_flagrants(), current.flagrants, career.flagrants),
			ratio(m.player_milestone_ast_to(), current.assistTurnoverRatio, career.assistTurnoverRatio),
			ratio(m.player_milestone_stl_to(), current.stealTurnoverRatio, career.stealTurnoverRatio)
		]
	};
}

const gameLogColumns = (): StatColumn[] => [
	{ key: 'result', label: m.player_column_result(), wide: true },
	{ key: 'min', label: m.box_minutes(), muted: true },
	{ key: 'fg', label: m.box_field_goals(), wide: true },
	{ key: 'fgPct', label: m.panel_stat_field_goals() },
	{ key: 'tp', label: m.box_three_points(), wide: true },
	{ key: 'tpPct', label: m.panel_stat_three_points() },
	{ key: 'ft', label: m.box_free_throws(), wide: true },
	{ key: 'ftPct', label: m.panel_stat_free_throws() },
	{ key: 'reb', label: m.box_rebounds() },
	{ key: 'ast', label: m.box_assists() },
	{ key: 'blk', label: m.box_blocks() },
	{ key: 'stl', label: m.box_steals() },
	{ key: 'pf', label: m.box_fouls(), muted: true },
	{ key: 'tov', label: m.box_turnovers(), muted: true },
	{ key: 'pts', label: m.box_points(), points: true }
];

function gameLogRow(game: GameLogEntry): StatRowView {
	const date = feedDate(game.date, { month: 'short', day: 'numeric' });
	return {
		key: game.gameId,
		label: date,
		sub: game.tag ? gameTagLabel(game.tag) : null,
		link: { gameId: game.gameId, linked: game.detailAvailable },
		opponent: opponentView(game),
		cells: [
			{
				mark: game.result === 'win' ? m.game_last_game_win() : m.game_last_game_loss(),
				win: game.result === 'win',
				text: score(game.teamScore, game.opponentScore)
			},
			whole(game.minutes),
			range(whole(game.fieldGoalsMade), whole(game.fieldGoalsAttempted)),
			percent(game.fieldGoalPct),
			range(whole(game.threePointsMade), whole(game.threePointsAttempted)),
			percent(game.threePointPct),
			range(whole(game.freeThrowsMade), whole(game.freeThrowsAttempted)),
			percent(game.freeThrowPct),
			whole(game.rebounds),
			whole(game.assists),
			whole(game.blocks),
			whole(game.steals),
			whole(game.fouls),
			whole(game.turnovers),
			whole(game.points)
		]
	};
}

function gameLogSection(feed: PlayerFeed): GameLogSection | null {
	const log = feed.gameLog;
	if (!log || log.entries.length === 0) return null;
	const pick = (kinds: GameLogEntry['kind'][]) =>
		log.entries.filter((entry) => kinds.includes(entry.kind)).map(gameLogRow);
	const candidates: { id: GameLogFilter; label: string; rows: StatRowView[] }[] = [
		{ id: 'all', label: m.player_filter_all(), rows: log.entries.map(gameLogRow) },
		{ id: 'regular', label: m.player_regular_season(), rows: pick(['regular', 'cup']) },
		{ id: 'cup', label: m.team_tag_cup(), rows: pick(['cup']) },
		{ id: 'playoffs', label: m.team_schedule_playoffs(), rows: pick(['playoffs']) },
		{ id: 'preseason', label: m.player_preseason(), rows: pick(['preseason']) }
	];
	return {
		meta: log.season,
		columns: gameLogColumns(),
		filters: candidates.filter((filter) => filter.rows.length > 0)
	};
}

function awardsSection(feed: PlayerFeed): AwardView[] | null {
	if (feed.awards.length === 0) return null;
	return feed.awards.map((award) => ({
		count: m.player_award_count({ count: formatNumber(award.count) }),
		name: award.name,
		seasons: award.seasons.join(SEPARATOR)
	}));
}

/** Turns the player feed into the player page props. Every value is formatted here. */
export function toPlayerView(feed: PlayerFeed): PlayerView {
	const sections: PlayerSections = {
		profile: profileSection(feed),
		averages: averagesSection(feed.averages),
		seasons: seasonsSection(feed),
		milestones: milestonesSection(feed.milestones),
		gameLog: gameLogSection(feed),
		awards: awardsSection(feed)
	};
	const tabs: PlayerTab[] = TAB_ORDER.filter((id) => sections[KEY_OF[id]] !== null).map((id) => ({
		id,
		label: TAB_LABELS[id]()
	}));
	return {
		header: header(feed),
		tabs,
		mini: numbered(feed, initialAndLast(feed)),
		sections
	};
}
