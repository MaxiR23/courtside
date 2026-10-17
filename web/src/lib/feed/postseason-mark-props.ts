// Props for the playoffs marks on the core feeds (ADR 0035, ADR 0031): the tag, context line and stakes flag of a game, and the titles of a team.
import type { GamePostseason, PlayInGameKind, Stakes } from '#lib/contract/games.ts';
import type { TeamTitle } from '#lib/contract/team.ts';
import { formatNumber } from '#lib/format/locale.ts';
import { m } from '#lib/paraglide/messages.js';
import type { PostseasonMarkView, TitleView } from '#lib/playoffs/types.ts';
import { teamLabel, teamMark } from '#lib/team/mark.ts';

type SideInput = Parameters<typeof teamMark>[0];
type SummarySide = { label: string; wins: number | null };

export const CONFERENCE_TITLE = { east: m.playoffs_east, west: m.playoffs_west };

export const PLAY_IN_TITLE: Record<PlayInGameKind, () => string> = {
	seven_eight: m.playoffs_playin_7v8,
	nine_ten: m.playoffs_playin_9v10,
	eighth_seed: m.playoffs_playin_8th
};

const TAG: Record<GamePostseason['stage'], () => string> = {
	playin: m.playoffs_tag_playin,
	playoffs: m.playoffs_tag_playoffs,
	finals: m.playoffs_tag_finals
};

const SERIES_ROUND: Record<number, (inputs: { conference: string }) => string> = {
	1: m.playoffs_context_round_1,
	2: m.playoffs_context_round_2,
	3: m.playoffs_context_round_3
};

const FLAG: Record<Stakes, () => string> = {
	game_7: m.playoffs_flag_game_7,
	elimination: m.playoffs_flag_elimination,
	can_clinch: m.playoffs_flag_can_clinch,
	clinched: m.playoffs_flag_clinched
};

// The series summary, written from the structured wins and the winner (ADR 0055): the feed's English sentence is never shown.
// Null when either side's wins are missing.
export function seriesSummary(
	first: SummarySide,
	second: SummarySide,
	winner: 'first' | 'second' | null
): string | null {
	if (first.wins === null || second.wins === null) return null;
	const a = formatNumber(first.wins);
	if (winner !== null) {
		const won = winner === 'first' ? first : second;
		const lost = winner === 'first' ? second : first;
		return m.playoffs_series_wins({
			team: won.label,
			won: formatNumber(won.wins ?? 0),
			lost: formatNumber(lost.wins ?? 0)
		});
	}
	if (first.wins === second.wins) return m.game_series_tied({ wins: a });
	const leading = first.wins > second.wins ? first : second;
	const trailing = leading === first ? second : first;
	return m.playoffs_series_leads({
		team: leading.label,
		leading: formatNumber(leading.wins ?? 0),
		trailing: formatNumber(trailing.wins ?? 0)
	});
}

function markSummary(mark: GamePostseason, away: SideInput, home: SideInput): string | null {
	const winner =
		mark.seriesWinner === 'away' ? 'first' : mark.seriesWinner === 'home' ? 'second' : null;
	return seriesSummary(
		{ label: teamLabel(teamMark(away)), wins: mark.awayWins },
		{ label: teamLabel(teamMark(home)), wins: mark.homeWins },
		winner
	);
}

// The context line of a mark: null when the feed gives nothing to add to the tag (ADR 0050).
function context(mark: GamePostseason, away: SideInput, home: SideInput): string | null {
	const conference = mark.conference ? CONFERENCE_TITLE[mark.conference]() : '';
	if (mark.stage === 'playin') {
		const game = mark.playIn ? PLAY_IN_TITLE[mark.playIn]() : '';
		return m.playoffs_context_playin({ conference, game });
	}
	const n = mark.number === null ? null : formatNumber(mark.number);
	if (mark.stage === 'finals') {
		const summary = markSummary(mark, away, home);
		if (n !== null) {
			return summary ? m.playoffs_context_finals({ n, summary }) : m.playoffs_context_game({ n });
		}
		return summary;
	}
	const round = mark.round === null ? undefined : SERIES_ROUND[mark.round]?.({ conference });
	if (round !== undefined) {
		return n === null ? round : m.playoffs_context_series({ round, n });
	}
	return n === null ? null : m.playoffs_context_game({ n });
}

// A feed recorded before the mark has no key: not a play-in or playoff game.
export function postseasonMark(
	mark: GamePostseason | null | undefined,
	away: SideInput,
	home: SideInput
): PostseasonMarkView | null {
	if (!mark) return null;
	return {
		tag: TAG[mark.stage](),
		finals: mark.stage === 'finals',
		context: context(mark, away, home),
		stakes: mark.stakes ? FLAG[mark.stakes]() : null
	};
}

function title(entry: TeamTitle): TitleView {
	const year = String(entry.year ?? 0);
	if (entry.kind === 'nba_champions') {
		return { text: m.playoffs_title_champions({ year }), solid: true };
	}
	if (entry.kind === 'nba_cup_champions') {
		return { text: m.playoffs_title_cup({ year }), solid: false };
	}
	return {
		text: entry.conference === 'west' ? m.playoffs_title_west() : m.playoffs_title_east(),
		solid: false
	};
}

// A feed recorded before the titles has no key: no title.
export function teamTitles(titles: TeamTitle[] | null | undefined): TitleView[] | null {
	return titles ? titles.map(title) : null;
}
