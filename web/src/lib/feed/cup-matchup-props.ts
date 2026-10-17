import type {
	CupGame,
	CupMatchupFeed,
	MatchupPlayer,
	MatchupSide,
	PathGame
} from '#lib/contract/cup-matchup.ts';
import type {
	MatchupPlayerRow,
	MatchupSideView,
	MatchupStatusView,
	MatchupView,
	PathRowView,
	PlayerCardView
} from '#lib/cup/types.ts';
import { CONFERENCE_SHORT } from '#lib/feed/cup-mark-props.ts';
import { ROUND_LABEL, slotLabel } from '#lib/feed/cup-props.ts';
import { feedDate, injuryRow } from '#lib/feed/team-props.ts';
import { formatNumber } from '#lib/format/locale.ts';
import { positionName } from '#lib/format/position.ts';
import { m } from '#lib/paraglide/messages.js';
import { teamLabel, teamMark } from '#lib/team/mark.ts';

const NO_VALUE = '—';
const OVERTIME_FROM_PERIOD = 5; // periods 5 and up are overtimes, as in the games and detail feeds
const oneDecimal: Intl.NumberFormatOptions = { minimumFractionDigits: 1, maximumFractionDigits: 1 };

const average = (value: number | undefined): string =>
	value === undefined ? NO_VALUE : formatNumber(value, oneDecimal);

function cardOf(player: MatchupPlayer, team: string): PlayerCardView {
	return {
		id: player.id,
		name: player.name,
		photo: player.photoUrl,
		team,
		number: player.number === null ? null : `#${player.number}`,
		position: player.position === null ? null : positionName(player.position),
		injury: player.status === 'active' ? null : player.status,
		points: average(player.averages?.points),
		rebounds: average(player.averages?.rebounds),
		assists: average(player.averages?.assists),
		height: player.height,
		weight: player.weight === null ? null : m.player_weight_lb({ lb: formatNumber(player.weight) }),
		age: player.age === null ? null : formatNumber(player.age),
		hometown: player.birthplace,
		college: player.college,
		experience:
			player.experience === null
				? null
				: player.experience === 0
					? m.team_roster_rookie()
					: formatNumber(player.experience)
	};
}

function playerRow(player: MatchupPlayer, team: string): MatchupPlayerRow {
	const card = cardOf(player, team);
	return {
		id: player.id,
		name: player.name,
		number: player.number,
		position: player.position === null ? null : positionName(player.position),
		injury: card.injury,
		points: card.points,
		rebounds: card.rebounds,
		assists: card.assists,
		leader: { ...player.leader },
		starter: player.starter,
		card
	};
}

function pathRow(game: PathGame): PathRowView {
	const played = game.teamScore !== null && game.opponentScore !== null;
	return {
		gameId: game.gameId,
		linked: game.detailAvailable,
		result: game.result === null ? null : game.result === 'win' ? 'W' : 'L',
		opponent: teamMark(game.opponent),
		isHome: game.isHome,
		score: played
			? `${formatNumber(game.teamScore ?? 0)}-${formatNumber(game.opponentScore ?? 0)}`
			: null
	};
}

/** The score of the side whose team is the game's away or home team; none for a side that is neither. */
function sideScore(side: MatchupSide, game: CupGame | null): string | null {
	const code = side.team?.code ?? null;
	if (!game?.score || code === null) return null;
	if (code === game.away.code) return formatNumber(game.score.away);
	if (code === game.home.code) return formatNumber(game.score.home);
	return null;
}

function sideView(side: MatchupSide, game: CupGame | null): MatchupSideView {
	const team = side.team === null ? null : teamMark(side.team);
	const name = team ? (team.name ?? teamLabel(team)) : m.cup_tbd_slot();
	const details = side.details;
	return {
		team,
		name,
		label: slotLabel(side.label),
		score: sideScore(side, game),
		path: details ? details.path.map(pathRow) : [],
		injuries: details ? details.injuries.map(injuryRow) : [],
		roster: details ? details.roster.map((player) => playerRow(player, name)) : []
	};
}

function statusView(game: CupGame | null): MatchupStatusView {
	if (!game || game.status === 'scheduled') return { kind: 'vs' };
	if (game.status === 'final') {
		const overtime = game.period !== null && game.period >= OVERTIME_FROM_PERIOD;
		return { kind: 'final', text: overtime ? m.cup_final_ot() : m.cup_final() };
	}
	return { kind: 'status', status: game.status };
}

function round(feed: CupMatchupFeed): string {
	const label = ROUND_LABEL[feed.round]();
	return feed.conference === null ? label : `${CONFERENCE_SHORT[feed.conference]()} · ${label}`;
}

/**
 * Turns the matchup feed into the panel props. Paths, injuries and rosters keep the feed's order
 * and every value is the feed's own: the page computes nothing.
 */
export function toMatchupView(feed: CupMatchupFeed, options: { past?: boolean } = {}): MatchupView {
	const { game } = feed;
	return {
		header: {
			round: round(feed),
			date: game ? feedDate(game.date, { month: 'short', day: 'numeric' }) : null,
			venue: game ? game.venue : null,
			broadcast: game ? game.broadcast : null,
			neutral: game ? game.neutralSite : false,
			gameLink: game ? { gameId: game.id, linked: game.detailAvailable } : null
		},
		sides: [sideView(feed.top, game), sideView(feed.bottom, game)],
		status: statusView(game),
		note: feed.round === 'championship',
		rosterNote: options.past ? m.seasons_cup_no_roster() : null
	};
}
