// World geometry of the Cup bracket: where the 7 nodes sit, the connectors between them, the round
// labels and the champion anchor of the desktop world, and the rows of the mobile tree. Pure, in world
// units. The sizes mirror the --bracket-* tokens; tests/lib/cup/bracket-layout.test.ts pins them.

import { elbowPath, type Point } from '#lib/bracket/geometry.ts';
import type { SlotId } from '#lib/contract/cup.ts';

export type WorldKind = 'desktop';
export type World = { kind: WorldKind; width: number; height: number };
export type { Point } from '#lib/bracket/geometry.ts';
export type RoundKey = 'quarterfinals' | 'semifinals' | 'championship';

export const DESKTOP_WORLD: World = { kind: 'desktop', width: 6300, height: 1320 };
export const NODE = { width: 1100, height: 560 };

/** World units kept free around the world when it is fitted: room for the round labels. */
export const FIT_MARGIN = 160;

/** Length of the corner ticks of a node frame, in world units. */
export const TICK_SIZE = 40;

const LABEL_GAP = 120;
const CHAMPION_GAP = 60;

export const SLOT_IDS: SlotId[] = [
	'east-qf-1',
	'east-qf-2',
	'east-sf',
	'final',
	'west-sf',
	'west-qf-1',
	'west-qf-2'
];

export const DESKTOP_NODES: Record<SlotId, Point> = {
	'east-qf-1': { x: 0, y: 0 },
	'east-qf-2': { x: 0, y: 760 },
	'east-sf': { x: 1300, y: 380 },
	final: { x: 2600, y: 380 },
	'west-sf': { x: 3900, y: 380 },
	'west-qf-1': { x: 5200, y: 0 },
	'west-qf-2': { x: 5200, y: 760 }
};

export type Connector = { from: SlotId; to: SlotId; side: 'top' | 'bottom'; d: string };
export type RoundLabel = { key: RoundKey; x: number; y: number };

const NODES_BY_KIND: Record<WorldKind, Record<SlotId, Point>> = { desktop: DESKTOP_NODES };

export const nodesOf = (world: World): Record<SlotId, Point> => NODES_BY_KIND[world.kind];

type Feeder = { from: SlotId; to: SlotId; side: 'top' | 'bottom' };

// Quarterfinal 1 feeds the semifinal's top, quarterfinal 2 its bottom; the East semifinal feeds the
// final's top, the West one its bottom.
const FEEDERS: Feeder[] = [
	{ from: 'east-qf-1', to: 'east-sf', side: 'top' },
	{ from: 'east-qf-2', to: 'east-sf', side: 'bottom' },
	{ from: 'west-qf-1', to: 'west-sf', side: 'top' },
	{ from: 'west-qf-2', to: 'west-sf', side: 'bottom' },
	{ from: 'east-sf', to: 'final', side: 'top' },
	{ from: 'west-sf', to: 'final', side: 'bottom' }
];

const isWest = (id: SlotId): boolean => id.startsWith('west');

/** The 6 orthogonal connectors, in feeder order, each ending on the `side` of its `to` node. */
export function connectors(world: World): Connector[] {
	const nodes = nodesOf(world);
	return FEEDERS.map(({ from, to, side }) => ({
		from,
		to,
		side,
		d: elbowPath(nodes[from], nodes[to], NODE, isWest(from))
	}));
}

const COLUMNS: { key: RoundKey; ids: SlotId[] }[] = [
	{ key: 'quarterfinals', ids: ['east-qf-1', 'east-qf-2'] },
	{ key: 'semifinals', ids: ['east-sf'] },
	{ key: 'championship', ids: ['final'] },
	{ key: 'semifinals', ids: ['west-sf'] },
	{ key: 'quarterfinals', ids: ['west-qf-1', 'west-qf-2'] }
];

/** One label per column, centered above the top node of its group. */
export function roundLabels(world: World): RoundLabel[] {
	const nodes = nodesOf(world);
	return COLUMNS.map(({ key, ids }) => {
		const points = ids.map((id) => nodes[id]);
		const top = Math.min(...points.map((p) => p.y));
		const left = Math.min(...points.map((p) => p.x));
		const right = Math.max(...points.map((p) => p.x + NODE.width));
		const x = (left + right) / 2;
		return { key, x, y: top - LABEL_GAP };
	});
}

/** Where the champion's name goes: centered under the final node. */
export function championAnchor(world: World): Point {
	const final = nodesOf(world).final;
	return { x: final.x + NODE.width / 2, y: final.y + NODE.height + CHAMPION_GAP };
}

export type TreeCard = { id: SlotId; column: string }; // a grid-column value of the 8-column row
export type TreeRow = { key: RoundKey; cards: TreeCard[] };

/** The mobile tree: three rows of an 8-column grid, East on the left (docs/design-cup.md, "Mobile"). */
export const TREE_ROWS: TreeRow[] = [
	{
		key: 'quarterfinals',
		cards: [
			{ id: 'east-qf-1', column: '1 / 3' },
			{ id: 'east-qf-2', column: '3 / 5' },
			{ id: 'west-qf-1', column: '5 / 7' },
			{ id: 'west-qf-2', column: '7 / 9' }
		]
	},
	{
		key: 'semifinals',
		cards: [
			{ id: 'east-sf', column: '2 / 4' },
			{ id: 'west-sf', column: '6 / 8' }
		]
	},
	{ key: 'championship', cards: [{ id: 'final', column: '3 / 7' }] }
];
