// The one view of a game side or an opponent, and its two rules: the tile text
// (the code, or the initials of the display name) and the label text (the code,
// or the name). Every feed that shows an opponent maps it through teamMark();
// future features (full calendar, brackets) reuse it.
// SEE: docs/adr/0025-guest-teams.md, docs/adr/0026-one-guest-team-rule.md

import { initials } from '#lib/format/initials.ts';

export type TeamMarkTeam = {
	code: string | null; // null: a guest team whose source sent no code
	name: string | null;
	city: string | null;
	guest: boolean; // a team outside the league: never a link
};

/** The view of a feed side or opponent; a feed built before the guest field has no key: a league team. */
export function teamMark(team: {
	code: string | null;
	name: string | null;
	city: string | null;
	guest?: boolean;
}): TeamMarkTeam {
	return { code: team.code, name: team.name, city: team.city, guest: team.guest ?? false };
}

/** The tile text: the code, else the initials of the display name (the city and the name, or the name alone). */
export function teamTile(team: TeamMarkTeam): string {
	if (team.code !== null) return team.code;
	return initials([team.city, team.name].filter(Boolean).join(' '));
}

/** The label text: the code, else the name, else nothing. */
export function teamLabel(team: TeamMarkTeam): string {
	return team.code ?? team.name ?? '';
}
