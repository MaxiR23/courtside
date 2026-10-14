// Props for the All-Star marks on the core feeds (ADR 0038, ADR 0031): the tag and context line of a game, and the tag of a player.
import type { AllStarMarkView } from '#lib/all-star/types.ts';
import type { GameAllStar } from '#lib/contract/games.ts';
import { m } from '#lib/paraglide/messages.js';

export function allStarMark(mark: GameAllStar | null | undefined): AllStarMarkView | null {
	// A feed recorded before the mark has no key: not an All-Star game.
	if (!mark) return null;
	return {
		tag: m.allstar_stage_tag(),
		context: mark.championship ? m.allstar_round_championship() : mark.roundLabel,
		championship: mark.championship
	};
}

export function allStarPlayerTag(year: number | null | undefined): string | null {
	if (year === null || year === undefined) return null;
	return m.allstar_tag({ year: String(year) });
}
