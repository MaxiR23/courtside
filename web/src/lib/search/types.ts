// Row views of the search overlay. Components get pre-formatted strings and never a contract type.
import type { InjuryTagStatus } from '#lib/game/types.ts';

export type SearchTeamRow = {
	code: string; // "OKC", monogram
	city: string;
	name: string;
	meta: string; // "OKC · 1st in Northwest", or just the code when there is no division rank
	record: string;
	strip: { primary: string; secondary: string } | null; // null: plain tile
};

export type SearchPlayerRow = {
	id: string;
	name: string;
	shortName: string; // mobile
	line: string; // "#2 · Guard (G)"; empty when every part is null
	lineShort: string; // mobile: "#2 · G"
	photo: string | null;
	injury: InjuryTagStatus | null;
	teamCode: string;
	teamColor: string | null; // null: plain bar
};
