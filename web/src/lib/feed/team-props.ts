import type {
	Conference,
	GameTag,
	InjuryStatus,
	NextGame,
	RosterPlayer,
	ScheduleGame,
	ScheduleGroup,
	SplitRecord,
	TeamFeed,
	TeamInjury,
	TeamLeader
} from '#lib/contract/team.ts';
import { tipParts } from '#lib/feed/props.ts';
import { formatDate, formatNumber } from '#lib/format/locale.ts';
import type { InfoCell, InjuryTagStatus } from '#lib/game/types.ts';
import { m } from '#lib/paraglide/messages.js';
import type {
	LeaderCard,
	LeadersSection,
	NextGameView,
	OverviewSection,
	RecordSection,
	RosterRow,
	RosterStatusTone,
	ScheduleGroupView,
	ScheduleRowView,
	ScheduleSection,
	TeamHeaderView,
	TeamInjuryRow,
	TeamSectionId,
	TeamTab,
	TeamView
} from '#lib/team/types.ts';
import { teamMark } from '#lib/team/mark.ts';

const TIME_ZONE = 'America/New_York';
const SEPARATOR = ' · ';
const NO_VALUE = '—';
const FINALS_ROUND = 4;
const PLAYOFFS_KEY = 'playoffs';

const TEAM_TAB_LABELS: Record<TeamSectionId, () => string> = {
	overview: m.team_tab_overview,
	record: m.team_tab_record,
	leaders: m.team_tab_leaders,
	roster: m.team_tab_roster,
	injuries: m.game_tab_injuries,
	schedule: m.team_tab_schedule
};

const TAB_ORDER: TeamSectionId[] = [
	'overview',
	'record',
	'leaders',
	'roster',
	'injuries',
	'schedule'
];

const CONFERENCE_SHORT: Record<Conference, () => string> = {
	east: m.game_conference_east,
	west: m.game_conference_west
};

const CONFERENCE_LONG: Record<Conference, () => string> = {
	east: m.team_conference_east,
	west: m.team_conference_west
};

const INJURY_LABELS: Record<InjuryStatus, () => string> = {
	out: m.injury_status_out,
	doubtful: m.injury_status_doubtful,
	questionable: m.injury_status_questionable,
	probable: m.injury_status_probable,
	'day-to-day': m.injury_status_day_to_day
};

const STATUS_TONES: Record<InjuryStatus, RosterStatusTone> = {
	out: 'out',
	doubtful: 'ink',
	questionable: 'ink',
	probable: 'muted',
	'day-to-day': 'muted'
};

const percent = (v: number) =>
	formatNumber(v, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });

const oneDecimal: Intl.NumberFormatOptions = { minimumFractionDigits: 1, maximumFractionDigits: 1 };

const record = (r: { wins: number; losses: number }) =>
	`${formatNumber(r.wins)}–${formatNumber(r.losses)}`;

// A contract date has no time: "1998-07-12" is UTC midnight, so it is formatted in UTC to keep the day.
export function feedDate(date: string, options: Intl.DateTimeFormatOptions): string {
	return formatDate(new Date(date), { ...options, timeZone: 'UTC' });
}

const etDate = (startTime: string, options: Intl.DateTimeFormatOptions) =>
	formatDate(new Date(startTime), { timeZone: TIME_ZONE, ...options });

const rank = (value: number, name: string) =>
	m.game_standings_rank({ rank: value, conference: name });

const numberAndPosition = (number: string | null, position: string | null): string | null => {
	const parts = [number === null ? null : `#${number}`, position].filter(
		(part): part is string => part !== null
	);
	return parts.length > 0 ? parts.join(SEPARATOR) : null;
};

/** The label of a game tag: "NBA Cup", "West R1 · G3", "Finals", "Playoffs" or "All-Star". */
export function gameTagLabel(tag: GameTag): string {
	let label: string;
	if (tag.kind === 'cup') {
		label = m.team_tag_cup();
	} else if (tag.kind === 'allstar') {
		label = m.team_tag_allstar();
	} else if (tag.round === FINALS_ROUND) {
		label = m.team_tag_finals();
	} else if (tag.round !== null && tag.conference !== null) {
		label = m.team_tag_round({
			conference: CONFERENCE_SHORT[tag.conference](),
			round: tag.round
		});
	} else {
		label = m.team_tag_playoffs();
	}
	return tag.game === null ? label : `${label}${SEPARATOR}${m.team_tag_game({ game: tag.game })}`;
}

function playoffLabel(playoff: NonNullable<TeamFeed['record']['playoff']>): string {
	if (playoff.status === 'seed') return m.team_playoff_seed({ seed: playoff.seed });
	return playoff.status === 'playin' ? m.team_playoff_playin() : m.team_playoff_out();
}

function streakLabel(streak: NonNullable<TeamFeed['record']['streak']>): string {
	const count = formatNumber(streak.count);
	return streak.kind === 'win' ? m.team_streak_win({ count }) : m.team_streak_loss({ count });
}

function header(feed: TeamFeed): TeamHeaderView {
	const r = feed.record;
	const cells: InfoCell[] = [
		{
			label: m.team_cell_conference(),
			value: rank(r.conferenceRank, CONFERENCE_SHORT[feed.conference]()),
			sub: null
		}
	];
	if (r.streak)
		cells.push({ label: m.team_cell_streak(), value: streakLabel(r.streak), sub: null });
	cells.push({ label: m.team_cell_last_ten(), value: record(r.lastTen), sub: null });
	if (r.playoff) {
		cells.push({ label: m.team_cell_playoffs(), value: playoffLabel(r.playoff), sub: null });
	}
	return {
		code: feed.code,
		city: feed.city,
		name: feed.name,
		conferenceLine: [
			CONFERENCE_LONG[feed.conference](),
			m.team_division({ division: feed.division })
		].join(SEPARATOR),
		colors: { primary: feed.colors.primary, secondary: feed.colors.secondary },
		record: record(r),
		winPct: percent(r.winPct),
		cells
	};
}

export function nextGameView(game: NextGame): NextGameView {
	const { tipTime, tipSuffix } = tipParts(game.startTime);
	const time = `${tipTime} ${tipSuffix}`;
	return {
		gameId: game.gameId,
		linked: game.detailAvailable,
		tag: game.tag ? gameTagLabel(game.tag) : null,
		date: etDate(game.startTime, { weekday: 'long', month: 'long', day: 'numeric' }),
		opponent: { team: teamMark(game.opponent), isHome: game.isHome },
		place: [game.arena, game.city].filter((part): part is string => part !== null).join(SEPARATOR),
		time: [time, game.broadcast].filter((part): part is string => part !== null).join(SEPARATOR)
	};
}

function overview(feed: TeamFeed): OverviewSection {
	return {
		arena: { name: feed.arena.name, city: feed.arena.city, photo: feed.arena.photoUrl },
		coach: feed.coach
			? {
					label: m.team_coach_label(),
					value: feed.coach.name,
					sub:
						feed.coach.seasons === null ? null : m.team_coach_seasons({ count: feed.coach.seasons })
				}
			: null,
		colors: [{ hex: feed.colors.primary }, { hex: feed.colors.secondary }],
		nextGame: feed.nextGame ? nextGameView(feed.nextGame) : null
	};
}

function splitCell(label: string, split: SplitRecord): InfoCell {
	return { label, value: record(split), sub: percent(split.winPct) };
}

function recordSection(feed: TeamFeed): RecordSection {
	const r = feed.record;
	const detail: InfoCell[] = [];
	if (r.streak)
		detail.push({ label: m.team_record_streak(), value: streakLabel(r.streak), sub: null });
	detail.push({
		label: m.team_record_games_behind(),
		value:
			r.gamesBehind === null ? NO_VALUE : formatNumber(r.gamesBehind, { maximumFractionDigits: 1 }),
		sub: null
	});
	if (r.playoff) {
		detail.push({
			label: m.team_record_playoff_position(),
			value: playoffLabel(r.playoff),
			sub: null
		});
	}
	detail.push(
		{
			label: m.team_record_conference(),
			value: rank(r.conferenceRank, CONFERENCE_SHORT[feed.conference]()),
			sub: null
		},
		{
			label: m.team_record_division(),
			value: rank(r.divisionRank, feed.division),
			sub: null
		},
		{
			label: m.team_record_points_for(),
			value: formatNumber(r.pointsFor.perGame, oneDecimal),
			sub: formatNumber(r.pointsFor.total)
		},
		{
			label: m.team_record_points_against(),
			value: formatNumber(r.pointsAgainst.perGame, oneDecimal),
			sub: formatNumber(r.pointsAgainst.total)
		},
		{
			label: m.team_record_differential(),
			value: formatNumber(r.differential.perGame, { ...oneDecimal, signDisplay: 'exceptZero' }),
			sub: formatNumber(r.differential.total, { signDisplay: 'exceptZero' })
		}
	);
	return {
		meta: m.team_record_meta({ season: r.season }),
		large: [
			splitCell(m.team_record_overall(), r),
			splitCell(m.team_record_home(), r.home),
			splitCell(m.team_record_away(), r.away),
			splitCell(m.team_record_last_ten(), r.lastTen)
		],
		detail
	};
}

function leaderCard(label: string, leader: TeamLeader): LeaderCard {
	return {
		playerId: leader.playerId,
		label,
		value: formatNumber(leader.value, oneDecimal),
		name: leader.name,
		line: numberAndPosition(leader.number, leader.position) ?? '',
		photo: leader.photoUrl
	};
}

function leadersSection(feed: TeamFeed): LeadersSection | null {
	const { points, rebounds, assists, season } = feed.leaders;
	const cards = [
		points && leaderCard(m.team_leader_points(), points),
		rebounds && leaderCard(m.team_leader_rebounds(), rebounds),
		assists && leaderCard(m.team_leader_assists(), assists)
	].filter((card): card is LeaderCard => card !== null);
	if (cards.length === 0) return null;
	return { meta: m.team_leaders_meta({ season }), cards };
}

function rosterRow(player: RosterPlayer): RosterRow {
	return {
		id: player.id,
		name: player.name,
		photo: player.photoUrl,
		number: player.number,
		position: player.position,
		height: player.height,
		weight: player.weight === null ? null : formatNumber(player.weight),
		age: player.age === null ? null : formatNumber(player.age),
		born: player.birthDate
			? feedDate(player.birthDate, { month: 'short', day: 'numeric', year: 'numeric' })
			: null,
		birthplace: player.birthplace,
		college: player.college,
		experience:
			player.experience === null
				? null
				: player.experience === 0
					? m.team_roster_rookie()
					: formatNumber(player.experience),
		status:
			player.status === 'active'
				? { label: m.team_status_active(), tone: 'muted' }
				: { label: INJURY_LABELS[player.status](), tone: STATUS_TONES[player.status] }
	};
}

function injuryRow(injury: TeamInjury): TeamInjuryRow {
	return {
		name: injury.name,
		line: numberAndPosition(injury.number, injury.position),
		status: injury.status satisfies InjuryTagStatus,
		comment: injury.comment
	};
}

function groupLabel(key: string): string {
	if (key === PLAYOFFS_KEY) return m.team_schedule_playoffs();
	return formatDate(new Date(`${key}-01T00:00:00Z`), { month: 'short', timeZone: 'UTC' });
}

function scheduleRow(game: ScheduleGame): ScheduleRowView {
	const tags = [
		game.tag ? gameTagLabel(game.tag) : null,
		game.isNext ? m.team_tag_next() : null
	].filter((tag): tag is string => tag !== null);
	const base = {
		gameId: game.gameId,
		linked: game.detailAvailable,
		weekday: etDate(game.startTime, { weekday: 'short' }),
		date: etDate(game.startTime, { month: 'short', day: 'numeric' }),
		opponent: { team: teamMark(game.opponent), isHome: game.isHome },
		tags,
		next: game.isNext
	};
	if (game.result !== null) {
		return {
			...base,
			outcome: {
				kind: 'played',
				result: game.result,
				resultLabel: game.result === 'win' ? m.game_last_game_win() : m.game_last_game_loss(),
				score:
					game.teamScore === null || game.opponentScore === null
						? null
						: `${formatNumber(game.teamScore)}–${formatNumber(game.opponentScore)}`,
				side: game.isHome ? m.team_schedule_home() : m.team_schedule_away()
			}
		};
	}
	const { tipTime, tipSuffix } = tipParts(game.startTime);
	return {
		...base,
		outcome: { kind: 'upcoming', time: `${tipTime} ${tipSuffix}`, broadcast: game.broadcast }
	};
}

function scheduleGroup(group: ScheduleGroup): ScheduleGroupView {
	return { key: group.key, label: groupLabel(group.key), rows: group.games.map(scheduleRow) };
}

function scheduleSection(feed: TeamFeed): ScheduleSection | null {
	if (!feed.schedule) return null;
	return {
		groups: feed.schedule.groups.map(scheduleGroup),
		defaultKey: feed.schedule.defaultGroup
	};
}

/** Turns the team feed into the team page props. Every value is formatted here. */
export function toTeamView(feed: TeamFeed): TeamView {
	const sections = {
		overview: overview(feed),
		record: recordSection(feed),
		leaders: leadersSection(feed),
		roster: feed.roster.length > 0 ? feed.roster.map(rosterRow) : null,
		injuries: feed.injuries.map(injuryRow),
		schedule: scheduleSection(feed)
	};
	const tabs: TeamTab[] = TAB_ORDER.filter((id) => sections[id] !== null).map((id) => ({
		id,
		label: TEAM_TAB_LABELS[id]()
	}));
	return {
		header: header(feed),
		tabs,
		mini: `${feed.code} ${record(feed.record)}`,
		sections
	};
}
