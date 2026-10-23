// The order of the playoffs bracket's seven groups, shared by the desktop map (seven columns)
// and the phone tree (seven rows), so the two cannot drift apart. Pure data: no layout math.
// SEE: docs/design-playoffs.md, Bracket
import type { SeriesId } from '#lib/contract/playoffs.ts';
import { m } from '#lib/paraglide/messages.js';

export type BracketGroup = {
	key: 'east-r1' | 'east-r2' | 'east-r3' | 'finals' | 'west-r3' | 'west-r2' | 'west-r1';
	title: () => string;
	ids: SeriesId[];
	finals: boolean;
};

/** East round 1 to West round 1, left to right on the map and top to bottom in the tree. */
export const BRACKET_GROUPS: BracketGroup[] = [
	{
		key: 'east-r1',
		title: m.playoffs_col_east_r1,
		ids: ['east-r1-1', 'east-r1-2', 'east-r1-3', 'east-r1-4'],
		finals: false
	},
	{
		key: 'east-r2',
		title: m.playoffs_col_east_semis,
		ids: ['east-r2-1', 'east-r2-2'],
		finals: false
	},
	{ key: 'east-r3', title: m.playoffs_col_east_finals, ids: ['east-r3'], finals: false },
	{ key: 'finals', title: m.playoffs_col_nba_finals, ids: ['finals'], finals: true },
	{ key: 'west-r3', title: m.playoffs_col_west_finals, ids: ['west-r3'], finals: false },
	{
		key: 'west-r2',
		title: m.playoffs_col_west_semis,
		ids: ['west-r2-1', 'west-r2-2'],
		finals: false
	},
	{
		key: 'west-r1',
		title: m.playoffs_col_west_r1,
		ids: ['west-r1-1', 'west-r1-2', 'west-r1-3', 'west-r1-4'],
		finals: false
	}
];

// The tree's 8-column grid: round 1 spans two columns each, the semifinals sit between their
// feeders, the conference finals in the middle and the Finals across the center four.
const TREE_SPAN: Record<SeriesId, string> = {
	'east-r1-1': '1 / 3',
	'east-r1-2': '3 / 5',
	'east-r1-3': '5 / 7',
	'east-r1-4': '7 / 9',
	'east-r2-1': '2 / 4',
	'east-r2-2': '6 / 8',
	'east-r3': '4 / 6',
	finals: '3 / 7',
	'west-r3': '4 / 6',
	'west-r2-1': '2 / 4',
	'west-r2-2': '6 / 8',
	'west-r1-1': '1 / 3',
	'west-r1-2': '3 / 5',
	'west-r1-3': '5 / 7',
	'west-r1-4': '7 / 9'
};

/** The `grid-column` of a series card in the phone tree. */
export function treeSpan(id: SeriesId): string {
	return TREE_SPAN[id];
}
