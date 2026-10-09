// Props layer of the search overlay: turns the search feed's teams and players into row views.
import type { SearchPlayer, SearchTeam } from '#lib/contract/search.ts';
import { m } from '#lib/paraglide/messages.js';
import type { SearchPlayerRow, SearchTeamRow } from '#lib/search/types.ts';

const SEPARATOR = ' · ';

export function toSearchTeamRow(team: SearchTeam): SearchTeamRow {
	const { primary, secondary } = team.colors;
	return {
		code: team.code,
		city: team.city,
		name: team.name,
		meta:
			team.divisionRank === null
				? team.code
				: m.search_team_meta({
						code: team.code,
						rank: team.divisionRank,
						division: team.division
					}),
		record: team.record,
		strip: primary !== null && secondary !== null ? { primary, secondary } : null
	};
}

const joined = (parts: (string | null)[]): string =>
	parts.filter((part): part is string => part !== null).join(SEPARATOR);

export function toSearchPlayerRow(player: SearchPlayer): SearchPlayerRow {
	const { number, position, positionAbbr } = player;
	const numberPart = number === null ? null : `#${number}`;
	const longPosition =
		position && positionAbbr ? `${position} (${positionAbbr})` : (position ?? positionAbbr);
	return {
		id: player.id,
		name: player.name,
		shortName: player.shortName,
		line: joined([numberPart, longPosition]),
		lineShort: joined([numberPart, positionAbbr]),
		photo: player.photoUrl,
		injury: player.injury?.status ?? null,
		teamCode: player.team.code,
		teamColor: player.team.primary
	};
}
