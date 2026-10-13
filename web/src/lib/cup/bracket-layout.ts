// World geometry of the Cup bracket: where the 7 nodes sit, the connectors between them, the round
// labels and the champion anchor, for the desktop world and the vertical mobile world. Pure, in world
// units. The sizes mirror the --bracket-* tokens; tests/lib/cup/bracket-layout.test.ts pins them.

import type { SlotId } from '#lib/contract/cup.ts';

export type WorldKind = 'desktop' | 'mobile';
export type World = { kind: WorldKind; width: number; height: number };
export type Point = { x: number; y: number };
export type RoundKey = 'quarterfinals' | 'semifinals' | 'championship';

export const DESKTOP_WORLD: World = { kind: 'desktop', width: 6300, height: 1320 };
export const MOBILE_WORLD: World = { kind: 'mobile', width: 2400, height: 3600 };
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

export const MOBILE_NODES: Record<SlotId, Point> = {
	'east-qf-1': { x: 0, y: 0 },
	'east-qf-2': { x: 1300, y: 0 },
	'east-sf': { x: 650, y: 760 },
	final: { x: 650, y: 1520 },
	'west-sf': { x: 650, y: 2280 },
	'west-qf-1': { x: 0, y: 3040 },
	'west-qf-2': { x: 1300, y: 3040 }
};

export type Connector = { from: SlotId; to: SlotId; side: 'top' | 'bottom'; d: string };
export type RoundLabel = { key: RoundKey; x: number; y: number };

export const nodesOf = (world: World): Record<SlotId, Point> =>
	world.kind === 'desktop' ? DESKTOP_NODES : MOBILE_NODES;

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

function desktopPath(from: Point, to: Point, west: boolean): string {
	const y1 = from.y + NODE.height / 2;
	const y2 = to.y + NODE.height / 2;
	const x1 = west ? from.x : from.x + NODE.width;
	const x2 = west ? to.x + NODE.width : to.x;
	const xm = (x1 + x2) / 2;
	return `M ${x1} ${y1} H ${xm} V ${y2} H ${x2}`;
}

function mobilePath(from: Point, to: Point, west: boolean): string {
	const x1 = from.x + NODE.width / 2;
	const x2 = to.x + NODE.width / 2;
	const y1 = west ? from.y : from.y + NODE.height;
	const y2 = west ? to.y + NODE.height : to.y;
	const ym = (y1 + y2) / 2;
	return `M ${x1} ${y1} V ${ym} H ${x2} V ${y2}`;
}

/** The 6 orthogonal connectors, in feeder order, each ending on the `side` of its `to` node. */
export function connectors(world: World): Connector[] {
	const nodes = nodesOf(world);
	const path = world.kind === 'desktop' ? desktopPath : mobilePath;
	return FEEDERS.map(({ from, to, side }) => ({
		from,
		to,
		side,
		d: path(nodes[from], nodes[to], isWest(from))
	}));
}

const COLUMNS: { key: RoundKey; ids: SlotId[] }[] = [
	{ key: 'quarterfinals', ids: ['east-qf-1', 'east-qf-2'] },
	{ key: 'semifinals', ids: ['east-sf'] },
	{ key: 'championship', ids: ['final'] },
	{ key: 'semifinals', ids: ['west-sf'] },
	{ key: 'quarterfinals', ids: ['west-qf-1', 'west-qf-2'] }
];

/** One label per column (desktop) or per row (mobile), centered above the top node of its group. */
export function roundLabels(world: World): RoundLabel[] {
	const nodes = nodesOf(world);
	return COLUMNS.map(({ key, ids }) => {
		const points = ids.map((id) => nodes[id]);
		const top = Math.min(...points.map((p) => p.y));
		const left = Math.min(...points.map((p) => p.x));
		const right = Math.max(...points.map((p) => p.x + NODE.width));
		const x = world.kind === 'desktop' ? (left + right) / 2 : world.width / 2;
		return { key, x, y: top - LABEL_GAP };
	});
}

/** Where the champion's name goes: centered under the final node. */
export function championAnchor(world: World): Point {
	const final = nodesOf(world).final;
	return { x: final.x + NODE.width / 2, y: final.y + NODE.height + CHAMPION_GAP };
}
