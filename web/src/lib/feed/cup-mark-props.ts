// Props for the Cup marks on the core feeds (ADR 0028, ADR 0031): the tag on a game, the line on a team.
import type { Conference, CupGroupName, CupRound } from '#lib/contract/cup.ts';
import type { GameCup } from '#lib/contract/games.ts';
import type { TeamCup } from '#lib/contract/team.ts';
import type { CupTeamLineView } from '#lib/cup/types.ts';
import { formatNumber } from '#lib/format/locale.ts';
import { m } from '#lib/paraglide/messages.js';

export const CONFERENCE_SHORT: Record<Conference, () => string> = {
	east: m.game_conference_east,
	west: m.game_conference_west
};

export function groupTitle(name: CupGroupName): string {
	return m.cup_group_name({ conference: CONFERENCE_SHORT[name.conference](), letter: name.letter });
}

const TAG_STAGE: Record<CupRound, () => string> = {
	group: m.cup_stage_group,
	quarterfinals: m.cup_stage_quarterfinal,
	semifinals: m.cup_stage_semifinal,
	championship: m.cup_state_final
};

// A feed recorded before the mark has no key: not a Cup game.
export function cupTag(cup: GameCup | null | undefined): string | null {
	return cup ? m.cup_mark_tag({ stage: TAG_STAGE[cup.stage]() }) : null;
}

export function cupTeamLine(cup: TeamCup | null | undefined): CupTeamLineView | null {
	return cup
		? {
				group: groupTitle(cup.group),
				record: `${formatNumber(cup.wins)}-${formatNumber(cup.losses)}`
			}
		: null;
}
