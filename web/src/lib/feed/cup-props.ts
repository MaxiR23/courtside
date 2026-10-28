import type {
	BracketSlot,
	Conference,
	CupFeed,
	CupGame,
	CupGroup,
	CupRound,
	CupStage,
	CupTag,
	GroupRow,
	Opponent,
	PerGameDifferential,
	SlotRule,
	SlotSide,
	StageEntry,
	StageStatus,
	TotalDifferential,
	WildCardTable
} from '#lib/contract/cup.ts';
import type {
	BracketNodeView,
	BracketSideView,
	BracketView,
	CupDayView,
	CupFilterKey,
	CupFilterView,
	CupGameRowView,
	CupGameStatusView,
	CupGroupView,
	CupHeaderTeam,
	CupHeaderView,
	CupLegendEntry,
	CupSectionId,
	CupSideView,
	CupView,
	GroupRowView,
	Signed,
	StageView,
	WildCardView
} from '#lib/cup/types.ts';
import { CONFERENCE_SHORT, groupTitle } from '#lib/feed/cup-mark-props.ts';
import { feedDate } from '#lib/feed/team-props.ts';
import { formatNumber } from '#lib/format/locale.ts';
import { viewerTime } from '#lib/format/time.ts';
import { m } from '#lib/paraglide/messages.js';
import type { ClinchView } from '#lib/standings/types.ts';
import { teamLabel, teamMark, teamTile } from '#lib/team/mark.ts';

const NO_VALUE = '—';
const STAGE_DATE_SEPARATOR = ' – ';

const CONFERENCE_LONG: Record<Conference, () => string> = {
	east: m.team_conference_east,
	west: m.team_conference_west
};

export const ROUND_LABEL: Record<CupRound, () => string> = {
	group: m.cup_stage_group,
	quarterfinals: m.cup_state_qf,
	semifinals: m.cup_state_sf,
	championship: m.cup_state_final
};

const STATUS_LABEL: Record<StageStatus, () => string> = {
	complete: m.cup_status_complete,
	in_progress: m.cup_status_in_progress,
	next: m.cup_status_next,
	upcoming: m.cup_status_upcoming
};

const FILTER_LABEL: Record<CupFilterKey, () => string> = {
	all: m.cup_filter_all,
	group: m.cup_filter_group,
	quarterfinals: m.cup_filter_qf,
	semifinals: m.cup_filter_sf,
	championship: m.cup_filter_final
};

const FILTER_ORDER: CupFilterKey[] = [
	'all',
	'group',
	'quarterfinals',
	'semifinals',
	'championship'
];

const CUP_TAGS: Record<CupTag, ClinchView> = {
	won_group: { code: 'y', tone: 'accent' },
	wild_card: { code: 'x', tone: 'accent' },
	eliminated: { code: 'e', tone: 'muted' }
};

const TAG_LABEL: Record<CupTag, () => string> = {
	won_group: m.cup_tag_y,
	wild_card: m.cup_tag_x,
	eliminated: m.cup_tag_e
};

const TAG_ORDER: CupTag[] = ['won_group', 'wild_card', 'eliminated'];

const RULE_LABEL: Record<SlotRule, () => string> = {
	best_group_winner: m.cup_rule_best_group_winner,
	second_best_group_winner: m.cup_rule_second_best_group_winner,
	third_best_group_winner: m.cup_rule_third_best_group_winner,
	best_non_winner: m.cup_rule_best_non_winner,
	quarterfinal_winner: m.cup_rule_quarterfinal_winner,
	semifinal_winner: m.cup_rule_semifinal_winner
};

const GROUP_SECTIONS: CupSectionId[] = ['groups', 'wild-card', 'bracket', 'games'];
const KNOCKOUT_SECTIONS: CupSectionId[] = ['bracket', 'groups', 'wild-card', 'games'];

const number = (value: number | null): string => (value === null ? NO_VALUE : formatNumber(value));

const record = (wins: number, losses: number): string =>
	`${formatNumber(wins)}-${formatNumber(losses)}`;

function signed(value: PerGameDifferential | TotalDifferential | null): Signed {
	return value === null
		? { value: NO_VALUE, accent: false }
		: { value: value.value, accent: value.nonNegative };
}

function tagView(tag: CupTag | null): ClinchView | null {
	return tag === null ? null : CUP_TAGS[tag];
}

function streakView(streak: GroupRow['streak']): GroupRowView['streak'] {
	if (!streak) return { text: NO_VALUE, win: false };
	const count = formatNumber(streak.count);
	const win = streak.kind === 'win';
	return { text: win ? m.team_streak_win({ count }) : m.team_streak_loss({ count }), win };
}

function stateLine(feed: CupFeed): string {
	const states: Record<CupStage, () => string> = {
		draw: () => {
			if (!feed.drawn) return m.cup_not_drawn();
			const date =
				feed.firstGameDate === null
					? NO_VALUE
					: feedDate(feed.firstGameDate, { month: 'long', day: 'numeric' });
			return m.cup_state_draw({ date });
		},
		group: () => m.cup_state_group({ n: formatNumber(feed.groupGamesPlayed) }),
		quarterfinals: m.cup_state_qf,
		semifinals: m.cup_state_sf,
		championship: m.cup_state_final,
		complete: m.cup_state_complete
	};
	return states[feed.stage]();
}

function stageDates(entry: StageEntry): string {
	if (entry.firstDate === null || entry.lastDate === null) return m.cup_tbd();
	const options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
	const first = feedDate(entry.firstDate, options);
	if (entry.firstDate === entry.lastDate) return first;
	return `${first}${STAGE_DATE_SEPARATOR}${feedDate(entry.lastDate, options)}`;
}

// A historical team has no team color (ADR 0054); a missing secondary leaves no bar.
const strip = (team: Opponent): CupHeaderTeam['strip'] =>
	!team.historical && team.colors !== null && team.colors.secondary !== null
		? { primary: team.colors.primary, secondary: team.colors.secondary }
		: null;

// The champion once the Cup is complete, else the defending champion; no team, no decoration.
function headerTeam(feed: CupFeed): CupHeaderTeam | null {
	const complete = feed.stage === 'complete';
	const team = complete ? feed.champion : feed.defendingChampion;
	if (team === null) return null;
	const mark = teamMark(team);
	return {
		team: mark,
		label: complete ? m.cup_champion() : m.cup_defending_champion(),
		accent: complete ? feed.championAccent : feed.defendingChampionAccent,
		strip: strip(team),
		outline: teamTile(mark)
	};
}

// The city of the first game of the round, in the feed's order, that has one.
function roundCity(round: CupRound, bracket: BracketSlot[]): string | null {
	for (const slot of bracket) {
		if (slot.round === round && slot.game?.city) return slot.game.city;
	}
	return null;
}

function stageNote(stage: CupRound, bracket: BracketSlot[]): string | null {
	switch (stage) {
		case 'group':
			return m.cup_note_group();
		case 'quarterfinals':
			return m.cup_note_qf();
		case 'semifinals':
		case 'championship':
			return roundCity(stage, bracket);
	}
}

function stageView(entry: StageEntry, bracket: BracketSlot[]): StageView {
	return {
		key: entry.stage,
		label: ROUND_LABEL[entry.stage](),
		dates: stageDates(entry),
		status: entry.status,
		statusLabel: STATUS_LABEL[entry.status](),
		note: stageNote(entry.stage, bracket)
	};
}

function headerView(feed: CupFeed, past: boolean): CupHeaderView {
	return {
		season: feed.season,
		stateLine: stateLine(feed),
		team: headerTeam(feed),
		stages: feed.stages.map((entry) => stageView(entry, feed.bracket)),
		tag: past ? m.past_season_tag({ label: feed.season }) : null
	};
}

function groupMeta(group: CupGroup): string {
	if (group.rows.length === 0) return m.cup_group_teams({ n: group.teams.length });
	if (group.final) return m.cup_group_final();
	return m.cup_group_games({ n: formatNumber(group.gamesFinal) });
}

function rowView(row: GroupRow): GroupRowView {
	return {
		team: teamMark(row.team),
		position: row.position === null ? NO_VALUE : String(row.position),
		record: record(row.wins, row.losses),
		gamesBehind: row.gamesBehind ?? NO_VALUE,
		perGame: signed(row.differential),
		total: signed(row.total),
		streak: streakView(row.streak),
		pointsFor: number(row.pointsFor),
		pointsAgainst: number(row.pointsAgainst),
		home: row.home ?? NO_VALUE,
		away: row.away ?? NO_VALUE,
		overtime: row.overtime ?? NO_VALUE,
		tag: tagView(row.tag),
		eliminated: row.tag === 'eliminated'
	};
}

// Rows are drawn by position; a row with no position goes after the numbered ones, in the feed's order (the sort is stable).
const byPosition = (a: GroupRow, b: GroupRow): number =>
	(a.position ?? Infinity) === (b.position ?? Infinity)
		? 0
		: (a.position ?? Infinity) < (b.position ?? Infinity)
			? -1
			: 1;

function groupView(group: CupGroup): CupGroupView {
	return {
		key: `${group.name.conference}-${group.name.letter.toLowerCase()}`,
		title: groupTitle(group.name),
		meta: groupMeta(group),
		teams: group.teams.map(teamMark),
		rows: [...group.rows].sort(byPosition).map(rowView)
	};
}

function wildCardView(table: WildCardTable): WildCardView {
	return {
		key: table.conference,
		title: CONFERENCE_LONG[table.conference](),
		rows: table.rows.map((row) => ({
			team: teamMark(row.team),
			rank: formatNumber(row.rank),
			group: row.group === null ? NO_VALUE : groupTitle(row.group),
			record: record(row.wins, row.losses),
			total: signed(row.total),
			pointsFor: number(row.pointsFor),
			tag: tagView(row.tag),
			lineAfter: row.rank === 1
		}))
	};
}

function legend(): CupLegendEntry[] {
	return TAG_ORDER.map((tag) => ({ clinch: CUP_TAGS[tag], label: TAG_LABEL[tag]() }));
}

function sideView(game: CupGame, side: 'away' | 'home'): CupSideView {
	return {
		team: teamMark(game[side]),
		score: game.score ? formatNumber(game.score[side]) : null,
		loser: game.winner !== null && game.winner !== side
	};
}

function statusView(game: CupGame): CupGameStatusView {
	if (game.status === 'scheduled') {
		return { kind: 'time', text: viewerTime(game.startTime) };
	}
	if (game.status === 'live') return { kind: 'live' };
	return { kind: 'status', status: game.status };
}

function gameView(game: CupGame): CupGameRowView {
	return {
		gameId: game.id,
		linked: game.detailAvailable,
		stageLabel: ROUND_LABEL[game.stage](),
		away: sideView(game, 'away'),
		home: sideView(game, 'home'),
		status: statusView(game),
		broadcast: game.broadcast,
		notCounted: !game.countsInStandings
	};
}

/** The slot's label, or null for a seed slot with no seed (a past Cup's quarterfinal sides). */
export function slotLabel(label: SlotSide['label']): string | null {
	const conference = CONFERENCE_SHORT[label.conference]();
	switch (label.key) {
		case 'seed':
			return label.seed === null
				? null
				: m.cup_slot_seed({ conference, seed: formatNumber(label.seed) });
		case 'wild_card':
			return m.cup_slot_wild_card({ conference });
		case 'quarterfinal_winner':
			return m.cup_slot_qf_winner({ conference, n: formatNumber(label.quarterfinal ?? 0) });
		case 'semifinal_winner':
			return m.cup_slot_sf_winner({ conference });
	}
}

function standingMeta(standing: SlotSide['standing']): string | null {
	if (!standing) return null;
	const parts = [
		standing.seed === null ? null : m.cup_side_seed({ seed: formatNumber(standing.seed) }),
		standing.group === null ? null : groupTitle(standing.group),
		record(standing.wins, standing.losses)
	];
	return parts.filter((part) => part !== null).join(' · ');
}

function bracketSide(side: SlotSide, game: CupGame | null): BracketSideView {
	const team = side.team === null ? null : teamMark(side.team);
	// The game lists away and home; a side takes the score of the team it is.
	const place =
		game && side.team?.code != null
			? side.team.code === game.away.code
				? 'away'
				: side.team.code === game.home.code
					? 'home'
					: null
			: null;
	return {
		team,
		name: team ? (team.name ?? teamLabel(team)) : m.cup_tbd_slot(),
		label: slotLabel(side.label),
		rule: RULE_LABEL[side.rule](),
		currently: side.projected
			? m.cup_currently({
					team: teamLabel(teamMark(side.projected.team)),
					w: formatNumber(side.projected.wins),
					l: formatNumber(side.projected.losses)
				})
			: null,
		meta: standingMeta(side.standing),
		score: place && game?.score ? formatNumber(game.score[place]) : null,
		winner: place !== null && game?.winner === place
	};
}

// The accent of the side that won: the feed's resolved color (ADR 0072); null: the neutral accent.
function winnerAccent(slot: BracketSlot, top: BracketSideView, bottom: BracketSideView) {
	return top.winner
		? (slot.accent?.top ?? null)
		: bottom.winner
			? (slot.accent?.bottom ?? null)
			: null;
}

function bracketNode(slot: BracketSlot): BracketNodeView {
	const { game } = slot;
	const top = bracketSide(slot.top, game);
	const bottom = bracketSide(slot.bottom, game);
	return {
		id: slot.id,
		roundLabel: ROUND_LABEL[slot.round](),
		mirrored: slot.conference === 'west',
		final: slot.id === 'final',
		top,
		bottom,
		date: game ? feedDate(game.date, { month: 'short', day: 'numeric' }) : null,
		venue: game ? game.venue : null,
		broadcast: game ? game.broadcast : null,
		neutral: game ? game.neutralSite : false,
		gameLink: game ? { gameId: game.id, linked: game.detailAvailable } : null,
		rule: game?.winner ? { accent: winnerAccent(slot, top, bottom) } : null
	};
}

function treeLabel(bracket: BracketSlot[], round: CupRound): string {
	const city = roundCity(round, bracket);
	return city === null
		? ROUND_LABEL[round]()
		: m.cup_round_city({ round: ROUND_LABEL[round](), city });
}

function bracketView(feed: CupFeed): BracketView {
	const known = {} as BracketView['known'];
	for (const slot of feed.bracket) {
		known[`${slot.id}:top`] = slot.top.known;
		known[`${slot.id}:bottom`] = slot.bottom.known;
	}
	const champion = feed.stage === 'complete' ? feed.champion : null;
	return {
		nodes: feed.bracket.map(bracketNode),
		known,
		rounds: {
			quarterfinals: ROUND_LABEL.quarterfinals(),
			semifinals: ROUND_LABEL.semifinals(),
			championship: ROUND_LABEL.championship()
		},
		champion: champion ? (champion.name ?? teamLabel(teamMark(champion))) : null,
		// The Cup is played in the season's first year: "2026-27" is the 2026 NBA Cup.
		kicker: m.cup_bracket_kicker({ year: feed.season.slice(0, 4) }),
		treeLabels: {
			quarterfinals: ROUND_LABEL.quarterfinals(),
			semifinals: treeLabel(feed.bracket, 'semifinals'),
			championship: treeLabel(feed.bracket, 'championship')
		}
	};
}

function filters(feed: CupFeed): CupFilterView[] {
	return FILTER_ORDER.map((key) => {
		const days: CupDayView[] = [];
		for (const day of feed.games.days) {
			const games = day.games.filter((game) => key === 'all' || game.stage === key);
			if (games.length === 0) continue;
			days.push({
				key: day.date,
				label: feedDate(day.date, { weekday: 'long', month: 'long', day: 'numeric' }),
				games: games.map(gameView)
			});
		}
		return {
			key,
			label: FILTER_LABEL[key](),
			count: formatNumber(feed.games.counts[key]),
			days
		};
	});
}

/**
 * Turns the Cup feed into the page props. Groups and days keep the feed's order, group rows are drawn by position, and
 * every value is the feed's own: the page computes nothing.
 */
export function toCupView(feed: CupFeed, options: { past?: boolean } = {}): CupView {
	const header = headerView(feed, options.past ?? false);
	return {
		header,
		sections: feed.stage === 'draw' || feed.stage === 'group' ? GROUP_SECTIONS : KNOCKOUT_SECTIONS,
		drawn: feed.drawn,
		groups: feed.groups.map(groupView),
		legend: legend(),
		wildCard: feed.wildCard.map(wildCardView),
		bracket: bracketView(feed),
		filters: filters(feed)
	};
}
