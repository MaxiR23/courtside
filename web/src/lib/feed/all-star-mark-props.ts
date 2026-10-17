// Props for the All-Star marks on the core feeds (ADR 0038, ADR 0031): the tag and context line of a game, and the tag of a player.
import type { AllStarMarkView } from '#lib/all-star/types.ts';
import type { GameAllStar } from '#lib/contract/games.ts';
import { m } from '#lib/paraglide/messages.js';

const ROUNDS: Record<string, () => string> = {
	championship: m.allstar_round_championship,
	semifinals: m.allstar_round_semifinals,
	'round robin': m.allstar_round_robin,
	'all-star game': m.allstar_round_game
};

/** A round label in the page language; a label the page does not know is shown as sent (ADR 0054). */
export function allStarRound(label: string | null): string | null {
	if (label === null) return null;
	return ROUNDS[label.trim().toLowerCase()]?.() ?? label;
}

export function allStarMark(mark: GameAllStar | null | undefined): AllStarMarkView | null {
	// A feed recorded before the mark has no key: not an All-Star game.
	if (!mark) return null;
	return {
		tag: m.allstar_stage_tag(),
		context: mark.championship
			? m.allstar_round_championship()
			: (allStarRound(mark.roundLabel) ?? mark.roundLabel),
		championship: mark.championship
	};
}

export function allStarPlayerTag(year: number | null | undefined): string | null {
	if (year === null || year === undefined) return null;
	return m.allstar_tag({ year: String(year) });
}
