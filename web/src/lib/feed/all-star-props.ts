// Props of the All-Star page: turns the All-Star feed into the view the components draw.
// The feed carries every count, the default game, the next game, the leading side, the top
// scorers and the team results (docs/api/all-star.md), so this module formats and lays out:
// it counts, sums and compares nothing.
// SEE: docs/design-all-star.md

import type {
	AllStarBoxPlayer,
	AllStarEdition,
	AllStarFormat,
	AllStarFeed,
	AllStarGame,
	AllStarMvp,
	AllStarState,
	AllStarTeam,
	AllStarTeamBox,
	AllStarTeamStat,
	LeagueTeam,
	Opponent,
	Side,
	TeamStatKind,
	Top5Row
} from '#lib/contract/all-star.ts';
import { leader, tipParts, video } from '#lib/feed/props.ts';
import { allStarRound } from '#lib/feed/all-star-mark-props.ts';
import { feedDate } from '#lib/feed/team-props.ts';
import { formatNumber } from '#lib/format/locale.ts';
import { positionName } from '#lib/format/position.ts';
import { m } from '#lib/paraglide/messages.js';
import type {
	AllStarHeaderView,
	AllStarSectionId,
	AllStarView,
	BoxRowView,
	BoxTeamView,
	BoxTotalsView,
	GameBoxView,
	GameCardView,
	GameDetailView,
	HeaderButtonView,
	LastTimeView,
	LeagueMarkView,
	MvpView,
	PlateView,
	RosterTileView,
	ScoreRowView,
	ScorelineView,
	StatCellView,
	TeamCardView,
	TeamStatView,
	Top5RowView
} from '#lib/all-star/types.ts';
import { teamLabel, teamMark } from '#lib/team/mark.ts';

const NO_VALUE = '—';
const SEPARATOR = ' · ';
const SCORE_SEPARATOR = '–';

const integer = (value: number): string => formatNumber(value);
const percent = (value: number): string =>
	formatNumber(value, { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
const signed = (value: number): string => formatNumber(value, { signDisplay: 'exceptZero' });
/** The format line in the page language, from the feed's parts: "First to 40 · Untimed", "1 period · 12 min". */
export function formatLine(format: AllStarFormat | null): string | null {
	if (format === null) return null;
	const parts: string[] =
		format.targetPoints !== null
			? [
					m.allstar_format_first_to({ points: formatNumber(format.targetPoints) }),
					...(format.untimed ? [m.allstar_format_untimed()] : [])
				]
			: [
					m.allstar_format_periods({ count: format.periods ?? 0 }),
					m.allstar_format_minutes({ minutes: formatNumber(format.minutes ?? 0) })
				];
	return parts.join(SEPARATOR);
}

const orDash = (value: string | null | undefined): string => (value ? value : NO_VALUE);
const monthDay: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
const fullDate: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' };

// The edition drawn: the current one, or the previous one as its after view.
type Drawn = {
	year: number;
	state: AllStarState;
	edition: AllStarEdition;
	mvp: AllStarMvp | null;
};

const nameOf = (team: Opponent): string => team.name ?? team.code ?? NO_VALUE;

const league = (found: LeagueTeam | null): LeagueMarkView | null =>
	found
		? { code: found.code, primary: found.colors.primary, secondary: found.colors.secondary }
		: null;

const dateLine = (edition: Pick<AllStarEdition, 'date' | 'venue'>): string | null =>
	[edition.date ? feedDate(edition.date, monthDay) : null, edition.venue?.name]
		.filter(Boolean)
		.join(SEPARATOR) || null;

function tipText(startTime: string): string {
	const tip = tipParts(startTime);
	return `${tip.tipTime} ${tip.tipSuffix}`;
}

function status(game: AllStarGame): GameCardView['status'] {
	if (game.status === 'final') {
		return {
			kind: 'final',
			text: game.overtime ? m.allstar_status_final_ot() : m.allstar_status_final()
		};
	}
	if (game.status === 'live') {
		const parts = [game.statusText, game.clock].filter(Boolean).join(SEPARATOR);
		return { kind: 'live', text: m.allstar_status_live({ status: orDash(parts) }) };
	}
	return { kind: 'tipoff', text: tipText(game.startTime) };
}

const sides: Side[] = ['away', 'home'];

// The feed marks the winner of a final game and the leading side of a live one.
function scoreRows(game: AllStarGame, ahead: Side | null): ScoreRowView[] {
	return sides.map((side) => {
		const team = game[side];
		if (!team) {
			return {
				team: null,
				name: m.allstar_to_be_determined(),
				score: NO_VALUE,
				winner: false,
				loser: false
			};
		}
		return {
			team: teamMark(team),
			name: nameOf(team),
			score: game.score ? integer(game.score[side]) : NO_VALUE,
			winner: ahead === side,
			loser: ahead !== null && ahead !== side
		};
	});
}

const rowsOfFinal = (game: AllStarGame): ScoreRowView[] => scoreRows(game, game.winner);

function matchup(game: AllStarGame): string {
	if (!game.away || !game.home) return m.allstar_to_be_determined();
	return `${teamLabel(teamMark(game.away))}${SEPARATOR}${teamLabel(teamMark(game.home))}`;
}

function card(game: AllStarGame): GameCardView {
	return {
		id: game.id,
		round: game.roundLabel
			? {
					text: game.championship
						? m.allstar_round_championship()
						: (allStarRound(game.roundLabel) ?? game.roundLabel),
					championship: game.championship
				}
			: null,
		status: status(game),
		label: matchup(game),
		rows: rowsOfFinal(game)
	};
}

const STAT_LABEL: Record<TeamStatKind, () => string> = {
	field_goal_pct: m.allstar_stat_fg,
	three_points_made: m.allstar_stat_3pm,
	rebounds: m.allstar_stat_reb,
	assists: m.allstar_stat_ast,
	steals: m.allstar_stat_stl,
	blocks: m.allstar_stat_blk
};

// Each side is drawn at its value over the larger of the two: a drawing scale, not a statistic.
// Which side is better is the feed's `better`.
function statView(stat: AllStarTeamStat): TeamStatView {
	const format = stat.stat === 'field_goal_pct' ? percent : integer;
	const largest = Math.max(stat.away, stat.home);
	const share = (value: number): number => (largest <= 0 ? 0 : value / largest);
	return {
		key: stat.stat,
		label: STAT_LABEL[stat.stat](),
		away: format(stat.away),
		home: format(stat.home),
		awayShare: share(stat.away),
		homeShare: share(stat.home),
		better: stat.better
	};
}

function top5Row(game: AllStarGame, row: Top5Row, index: number): Top5RowView {
	const team = game[row.side];
	const found = league(row.leagueTeam);
	return {
		key: row.playerId,
		playerId: row.playerId,
		rank: `#${index + 1}`,
		top: index === 0,
		name: row.name,
		photo: row.photoUrl,
		league: found,
		teamLine: [team ? nameOf(team) : null, found?.code].filter(Boolean).join(SEPARATOR),
		points: integer(row.points),
		line: m.allstar_top5_line({
			rebounds: integer(row.rebounds),
			assists: integer(row.assists)
		})
	};
}

function broadcast(game: AllStarGame): string {
	const tv = game.broadcasts.find((entry) => entry.kind === 'tv');
	const streaming = game.broadcasts.find((entry) => entry.kind === 'streaming');
	return [tv?.name, streaming?.name].filter(Boolean).join(SEPARATOR) || NO_VALUE;
}

function detail(game: AllStarGame, edition: AllStarEdition): GameDetailView {
	const played = game.status === 'live' || game.status === 'final';
	const first = game.highlights?.[0];
	const venue = [edition.venue?.name, edition.venue?.city].filter(Boolean).join(', ');
	return {
		id: game.id,
		scheduled: played
			? null
			: {
					title: m.allstar_scheduled_title({ time: tipText(game.startTime) }),
					body: m.allstar_scheduled_body()
				},
		video: first ? video(first) : null,
		placeholder: first
			? null
			: game.status === 'final'
				? m.allstar_highlights_unavailable()
				: m.allstar_highlights_after_buzzer(),
		live: game.status !== 'final',
		venueStrip: [
			{ key: 'venue', label: m.allstar_venue(), value: orDash(venue) },
			{
				key: 'attendance',
				label: m.allstar_attendance(),
				value: game.attendance === null ? NO_VALUE : integer(game.attendance)
			},
			{ key: 'broadcast', label: m.allstar_broadcast(), value: broadcast(game) },
			{ key: 'tipoff', label: m.allstar_tipoff(), value: tipText(game.startTime) }
		],
		top5: game.top5.map((row, index) => top5Row(game, row, index)),
		scoreboard: { rows: rowsOfFinal(game), status: status(game).text },
		leaders:
			game.leaders && game.away && game.home
				? {
						away: leader(game.leaders.away, game.away),
						home: leader(game.leaders.home, game.home)
					}
				: null,
		teamStats: game.teamStats ? game.teamStats.map(statView) : null
	};
}

function boxRow(player: AllStarBoxPlayer): BoxRowView {
	const minutes = orDash(player.minutes);
	return {
		id: player.playerId,
		jersey: orDash(player.jersey),
		name: player.displayName,
		position: orDash(player.position && positionName(player.position)),
		minutes,
		points: integer(player.points),
		rebounds: integer(player.rebounds),
		assists: integer(player.assists),
		steals: integer(player.steals),
		blocks: integer(player.blocks),
		fieldGoals: `${player.fieldGoalsMade}-${player.fieldGoalsAttempted}`,
		threePoints: `${player.threePointsMade}-${player.threePointsAttempted}`,
		plusMinus: player.plusMinus === null ? NO_VALUE : signed(player.plusMinus),
		starter: player.starter,
		topPoints: player.topPoints,
		negative: (player.plusMinus ?? 0) < 0,
		photo: player.photoUrl,
		league: league(player.leagueTeam),
		mobileMeta: [
			player.jersey ? `#${player.jersey}` : NO_VALUE,
			orDash(player.position && positionName(player.position)),
			minutes
		].join(SEPARATOR)
	};
}

function boxTotals(box: AllStarTeamBox): BoxTotalsView {
	const totals = box.totals;
	return {
		points: integer(totals.points),
		rebounds: integer(totals.rebounds),
		assists: integer(totals.assists),
		steals: integer(totals.steals),
		blocks: integer(totals.blocks),
		fieldGoals: `${totals.fieldGoalsMade}-${totals.fieldGoalsAttempted}`,
		threePoints: `${totals.threePointsMade}-${totals.threePointsAttempted}`
	};
}

function boxView(game: AllStarGame): GameBoxView | null {
	if (!game.boxScore) return null;
	const box = game.boxScore;
	const team = (side: Side): BoxTeamView => {
		const opponent = game[side];
		return {
			tab: opponent ? teamLabel(teamMark(opponent)) || nameOf(opponent) : NO_VALUE,
			rows: box[side].players.map(boxRow),
			totals: boxTotals(box[side])
		};
	};
	return { away: team('away'), home: team('home') };
}

function scoreline(games: AllStarGame[]): ScorelineView | null {
	const final = games.find((game) => game.championship && game.status === 'final');
	if (!final || !final.winner || !final.away || !final.home) return null;
	const rows = rowsOfFinal(final);
	// The winner first.
	return {
		gameId: final.id,
		rows: final.winner === 'away' ? rows : [rows[1], rows[0]],
		overtime: final.overtime
	};
}

function mvpView(found: AllStarMvp, games: AllStarGame[]): MvpView {
	return {
		playerId: found.playerId,
		name: found.name,
		photo: found.photoUrl,
		jersey: found.jersey,
		league: league(found.leagueTeam),
		lines: found.lines.map((line) => ({
			key: line.gameId,
			round: orDash(allStarRound(line.roundLabel)),
			championship: games.find((game) => game.id === line.gameId)?.championship ?? false,
			result: [
				line.result === 'win' ? m.game_last_game_win() : m.game_last_game_loss(),
				`${line.teamScore}${SCORE_SEPARATOR}${line.opponentScore}`,
				m.game_last_game_home({ team: nameOf(line.opponent) })
			].join(' '),
			stat: m.panel_leader_line({
				points: integer(line.points),
				rebounds: integer(line.rebounds),
				assists: integer(line.assists)
			})
		})),
		total: m.allstar_mvp_summary({
			pts: integer(found.totals.points),
			n: integer(found.totals.games)
		})
	};
}

function teamCard(team: AllStarTeam): TeamCardView {
	const placement: Record<AllStarTeam['placement']['kind'], string> = {
		champion: m.allstar_placement_champion(),
		runner_up: m.allstar_placement_runner_up(),
		eliminated: m.allstar_placement_eliminated({
			round: orDash(allStarRound(team.placement.roundLabel))
		}),
		so_far: m.allstar_placement_so_far(),
		yet_to_play: m.allstar_placement_yet()
	};
	return {
		key: team.team.code ?? team.team.name ?? NO_VALUE,
		team: teamMark(team.team),
		name: nameOf(team.team),
		placement: placement[team.placement.kind],
		champion: team.placement.kind === 'champion',
		record: `${team.wins}${SCORE_SEPARATOR}${team.losses}`,
		results: team.results.map((result) => ({
			key: result.gameId,
			win: result.result === 'win',
			mark: result.result === 'win' ? m.game_last_game_win() : m.game_last_game_loss(),
			text:
				m.allstar_result_row({
					label: orDash(allStarRound(result.roundLabel)),
					opp: teamLabel(teamMark(result.opponent)) || NO_VALUE
				}) + (result.overtime ? `${SEPARATOR}${m.allstar_result_ot()}` : ''),
			score: `${result.teamScore}${SCORE_SEPARATOR}${result.opponentScore}`
		})),
		roster: team.roster.map((tile): RosterTileView => ({
			playerId: tile.playerId,
			name: tile.name,
			photo: tile.photoUrl,
			title: tile.leagueTeam
				? m.allstar_player_title({ name: tile.name, team: tile.leagueTeam.code })
				: tile.name,
			league: league(tile.leagueTeam)
		}))
	};
}

function livePlate(drawn: Drawn): PlateView | null {
	const { edition } = drawn;
	const game = edition.games.find((entry) => entry.id === edition.defaultGameId);
	if (!game) return null;
	if (game.status !== 'live') {
		return {
			kind: 'tipoff',
			gameId: game.id,
			text: m.allstar_scheduled_title({ time: tipText(game.startTime) })
		};
	}
	const next = edition.games.find((entry) => entry.isNext);
	return {
		kind: 'live',
		gameId: game.id,
		header: m.allstar_live_header({ round: orDash(allStarRound(game.roundLabel)) }),
		formatLine: formatLine(edition.format),
		rows: scoreRows(game, game.leading),
		clock: orDash(game.clock),
		status: game.statusText,
		next: next
			? m.allstar_next_game({ label: allStarRound(next.roundLabel) ?? matchup(next) })
			: null
	};
}

function header(
	drawn: Drawn,
	view: Pick<AllStarView, 'mvp' | 'scoreline' | 'sections'>,
	seasonTag: string | null
): AllStarHeaderView {
	const { edition, state, mvp } = drawn;
	const tag = m.allstar_tag({ year: String(drawn.year) });
	const meta = dateLine(edition);
	const buttons: HeaderButtonView[] = [];
	if (state === 'before') {
		if (view.sections.includes('last-time')) {
			buttons.push({ key: 'last-time', label: m.allstar_cta_last(), primary: true });
		}
		const row = (key: 'date' | 'venue' | 'format', label: string, value: string | null) => ({
			key,
			label,
			value: value ?? m.allstar_to_be_confirmed()
		});
		const venue = [edition.venue?.name, edition.venue?.city].filter(Boolean).join(', ');
		return {
			state,
			tag,
			meta: null,
			kicker: m.allstar_kicker_next(),
			title: m.allstar_title(),
			score: null,
			stats: [],
			rows: [
				row('date', m.allstar_row_date(), edition.date ? feedDate(edition.date, fullDate) : null),
				row('venue', m.allstar_row_venue(), venue || null),
				row('format', m.allstar_row_format(), formatLine(edition.format))
			],
			buttons,
			plate: { kind: 'year', year: String(drawn.year) },
			seasonTag
		};
	}
	if (state === 'live') {
		const counts = edition.counts;
		const stat = (key: string, label: string, value: number, accent = false): StatCellView => ({
			key,
			label,
			value: integer(value),
			accent,
			countTo: value
		});
		buttons.push({ key: 'games', label: m.allstar_cta_follow(), primary: true });
		return {
			state,
			tag,
			meta,
			kicker: m.allstar_kicker_live(),
			title: m.allstar_title(),
			score: null,
			stats: [
				stat('games', m.allstar_stat_games_today(), counts.games),
				stat('final', m.allstar_stat_final(), counts.final),
				stat('live', m.allstar_stat_live(), counts.live, true),
				stat('teams', m.allstar_stat_teams(), counts.teams)
			],
			rows: [],
			buttons,
			plate: livePlate(drawn) ?? { kind: 'year', year: String(drawn.year) },
			seasonTag
		};
	}
	const champion = edition.teams.find((team) => team.placement.kind === 'champion');
	const final = edition.games.find((game) => game.championship);
	const score = view.scoreline
		? view.scoreline.rows.map((row) => row.score).join(SCORE_SEPARATOR)
		: null;
	buttons.push({ key: 'games', label: m.allstar_cta_every_game(), primary: true });
	if (view.sections.includes('mvp') && view.mvp) {
		buttons.push({ key: 'mvp', label: m.allstar_cta_mvp(), primary: false });
	}
	const counts = edition.counts;
	return {
		state,
		tag,
		meta,
		kicker: m.allstar_kicker_champions(),
		title: champion ? nameOf(champion.team) : m.allstar_title(),
		score,
		stats: [
			{
				key: 'games',
				label: m.allstar_stat_games(),
				value: integer(counts.games),
				accent: false,
				countTo: counts.games
			},
			{
				key: 'teams',
				label: m.allstar_stat_teams(),
				value: integer(counts.teams),
				accent: false,
				countTo: counts.teams
			},
			{
				key: 'championship',
				label: m.allstar_stat_championship(),
				value: score ?? NO_VALUE,
				accent: true,
				countTo: null
			},
			{
				key: 'attendance',
				label: m.allstar_stat_attendance(),
				value: final?.attendance == null ? NO_VALUE : integer(final.attendance),
				accent: false,
				countTo: final?.attendance ?? null
			}
		],
		rows: [],
		buttons,
		plate: mvp
			? {
					kind: 'mvp',
					name: mvp.name,
					photo: mvp.photoUrl,
					jersey: mvp.jersey,
					labels: m.allstar_mvp_hero_labels({
						pts: integer(mvp.totals.points),
						n: integer(mvp.totals.games)
					})
				}
			: view.scoreline
				? { kind: 'score', rows: view.scoreline.rows }
				: { kind: 'year', year: String(drawn.year) },
		seasonTag
	};
}

function lastTime(feed: AllStarFeed): LastTimeView | null {
	const previous = feed.previous;
	if (!previous) return null;
	const result = previous.championship;
	const other: Side = result.winner === 'away' ? 'home' : 'away';
	return {
		champion: {
			kicker: m.allstar_kicker_champions(),
			name: nameOf(result[result.winner]),
			meta: dateLine(previous) ?? NO_VALUE,
			score: [result.score[result.winner], result.score[other]].map(integer).join(SCORE_SEPARATOR)
		},
		mvp: previous.mvp
			? {
					playerId: previous.mvp.playerId,
					name: previous.mvp.name,
					photo: previous.mvp.photoUrl,
					league: league(previous.mvp.leagueTeam),
					summary: m.allstar_mvp_summary({
						pts: integer(previous.mvp.totals.points),
						n: integer(previous.mvp.totals.games)
					})
				}
			: null,
		video: previous.editionHighlight?.embedUrl ?? null,
		link: m.allstar_last_link({ prev: String(previous.year) })
	};
}

function sectionsOf(
	drawn: Drawn,
	last: LastTimeView | null,
	mvp: MvpView | null,
	line: ScorelineView | null
): AllStarSectionId[] {
	const { edition, state } = drawn;
	const sections: AllStarSectionId[] = [];
	if (state === 'before') {
		if (last) sections.push('last-time');
		return sections;
	}
	if (state === 'after' && (mvp || line)) sections.push('mvp');
	if (edition.games.length > 0) sections.push('games');
	if (edition.teams.length > 0) sections.push('teams');
	return sections;
}

function build(drawn: Drawn, last: LastTimeView | null, seasonTag: string | null): AllStarView {
	const { edition } = drawn;
	const shown = drawn.state !== 'before';
	const mvp = shown && drawn.mvp ? mvpView(drawn.mvp, edition.games) : null;
	const line = drawn.state === 'after' ? scoreline(edition.games) : null;
	const sections = sectionsOf(drawn, last, mvp, line);
	return {
		header: header(drawn, { mvp, scoreline: line, sections }, seasonTag),
		sections,
		lastTime: last,
		mvp: drawn.state === 'after' ? mvp : null,
		scoreline: line,
		formatLine: formatLine(edition.format),
		games: edition.games.map(card),
		details: Object.fromEntries(edition.games.map((game) => [game.id, detail(game, edition)])),
		boxes: Object.fromEntries(edition.games.map((game) => [game.id, boxView(game)])),
		defaultGame: edition.defaultGameId,
		teams: edition.teams.map(teamCard),
		editionVideo: edition.editionHighlight ? video(edition.editionHighlight) : null
	};
}

/**
 * The view of the All-Star page. `current` is the edition of the season in its state;
 * `previous` is the previous edition drawn as its after view, null when the feed has none.
 * `pastLabel` is the calendar's label of a past season: it adds the season tag.
 */
export function toAllStarView(
	feed: AllStarFeed,
	which: 'current' | 'previous',
	options: { pastLabel?: string } = {}
): AllStarView | null {
	if (which === 'previous') {
		const earlier = feed.previousEdition;
		if (!earlier || !feed.previous) return null;
		const { mvp, ...edition } = earlier;
		return build({ year: feed.previous.year, state: 'after', edition, mvp }, null, null);
	}
	const last = feed.state === 'before' ? lastTime(feed) : null;
	const seasonTag = options.pastLabel ? m.past_season_tag({ label: options.pastLabel }) : null;
	return build(
		{ year: feed.year, state: feed.state, edition: feed.edition, mvp: feed.mvp },
		last,
		seasonTag
	);
}
