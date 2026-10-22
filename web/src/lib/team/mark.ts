// The one view of a game side or an opponent, and its two rules: the tile text
// (the code, or the initials of the display name) and the label text (the code,
// or the name). Every feed that shows an opponent maps it through teamMark();
// future features (full calendar, brackets) reuse it.
// A historical side of a past feed shows that season's code, and links with today's.
// SEE: docs/adr/0025-guest-teams.md, docs/adr/0026-one-guest-team-rule.md,
// docs/adr/0054-historical-sides-and-past-pages.md

import type { TeamLogo } from '#lib/contract/games.ts';
import { initials } from '#lib/format/initials.ts';

export type TeamMarkTeam = {
	code: string | null; // null: a guest team whose source sent no code
	name: string | null;
	city: string | null;
	guest: boolean; // a team outside the league: never a link
	historicalCode?: string | null; // the code of a past season to show for a historical side; absent: show code
	logo?: TeamLogo | null; // the feed's logo; absent or null: the monogram
};

/** The view of a feed side or opponent; a feed built before the guest field has no key: a league team. */
export function teamMark(team: {
	code: string | null;
	name: string | null;
	city: string | null;
	guest?: boolean;
	seasonCode?: string | null;
	historical?: boolean;
	logo?: TeamLogo | null;
}): TeamMarkTeam {
	return {
		code: team.code,
		name: team.name,
		city: team.city,
		guest: team.guest ?? false,
		...(team.historical === true && team.seasonCode ? { historicalCode: team.seasonCode } : {}),
		...(team.logo ? { logo: team.logo } : {})
	};
}

/** The tile text: the code, else the initials of the display name (the city and the name, or the name alone). */
export function teamTile(team: TeamMarkTeam): string {
	if (team.code !== null) return team.historicalCode ?? team.code;
	return initials([team.city, team.name].filter(Boolean).join(' '));
}

/** The label text: the code, else the name, else nothing. */
export function teamLabel(team: TeamMarkTeam): string {
	return team.historicalCode ?? team.code ?? team.name ?? '';
}
