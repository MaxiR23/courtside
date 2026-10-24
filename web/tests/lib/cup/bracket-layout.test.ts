// web/tests/lib/cup/bracket-layout.test.ts
//
// Tests for the world geometry of the Cup bracket.
//
// Tested:
// - The 7 desktop positions equal the design's, West is the East mirrored, every node lies inside its world
// - 6 connectors, orthogonal, starting and ending on node edges
// - Quarterfinal 1 feeds the top, quarterfinal 2 the bottom, the East semifinal the final's top
// - Round labels per column, and the champion anchor under the final
// - The sizes match the --bracket-* tokens
// - TREE_ROWS: the three rows, their cards and columns, every slot once, every column inside the 8 tracks
//
// What is covered:
// - Happy path, mirroring and the token cross-check
//
// Run with: cd web && pnpm exec vitest run tests/lib/cup/bracket-layout.test.ts
//
// SEE: web/src/lib/cup/bracket-layout.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
	championAnchor,
	connectors,
	DESKTOP_NODES,
	DESKTOP_WORLD,
	NODE,
	roundLabels,
	SLOT_IDS,
	TICK_SIZE,
	TREE_ROWS
} from '../../../src/lib/cup/bracket-layout';

const tokensCss = readFileSync(join(process.cwd(), 'src/lib/styles/tokens.css'), 'utf8');
const token = (name: string): number => {
	const match = tokensCss.match(new RegExp(`${name}:\\s*(\\d+)px;`));
	if (!match) throw new Error(`${name} is not a px token`);
	return Number(match[1]);
};

describe('desktop world', () => {
	it('places the 7 nodes where the design puts them', () => {
		expect(DESKTOP_NODES).toEqual({
			'east-qf-1': { x: 0, y: 0 },
			'east-qf-2': { x: 0, y: 760 },
			'east-sf': { x: 1300, y: 380 },
			final: { x: 2600, y: 380 },
			'west-sf': { x: 3900, y: 380 },
			'west-qf-1': { x: 5200, y: 0 },
			'west-qf-2': { x: 5200, y: 760 }
		});
	});

	it('mirrors the West nodes around the vertical axis of the world', () => {
		for (const id of ['qf-1', 'qf-2', 'sf'] as const) {
			const east = DESKTOP_NODES[`east-${id}`];
			const west = DESKTOP_NODES[`west-${id}`];
			expect(west.x).toBe(DESKTOP_WORLD.width - NODE.width - east.x);
			expect(west.y).toBe(east.y);
		}
		expect(DESKTOP_NODES.final.x).toBe((DESKTOP_WORLD.width - NODE.width) / 2);
	});

	it('keeps every node inside the world', () => {
		for (const id of SLOT_IDS) {
			const { x, y } = DESKTOP_NODES[id];
			expect(x).toBeGreaterThanOrEqual(0);
			expect(y).toBeGreaterThanOrEqual(0);
			expect(x + NODE.width).toBeLessThanOrEqual(DESKTOP_WORLD.width);
			expect(y + NODE.height).toBeLessThanOrEqual(DESKTOP_WORLD.height);
		}
	});
});

describe('connectors', () => {
	it('has 6 orthogonal paths in the desktop world', () => {
		const list = connectors(DESKTOP_WORLD);
		expect(list).toHaveLength(6);
		for (const { d } of list) {
			const commands = d.match(/[A-Za-z]/g);
			expect(commands?.every((c) => ['M', 'H', 'V'].includes(c))).toBe(true);
			expect(d.startsWith('M ')).toBe(true);
		}
	});

	it('maps quarterfinal 1 to the top, quarterfinal 2 to the bottom and the East semifinal to the final top', () => {
		const list = connectors(DESKTOP_WORLD);
		const side = (from: string) => list.find((c) => c.from === from);
		expect(side('east-qf-1')).toMatchObject({ to: 'east-sf', side: 'top' });
		expect(side('east-qf-2')).toMatchObject({ to: 'east-sf', side: 'bottom' });
		expect(side('west-qf-1')).toMatchObject({ to: 'west-sf', side: 'top' });
		expect(side('west-qf-2')).toMatchObject({ to: 'west-sf', side: 'bottom' });
		expect(side('east-sf')).toMatchObject({ to: 'final', side: 'top' });
		expect(side('west-sf')).toMatchObject({ to: 'final', side: 'bottom' });
	});

	it('runs the desktop paths between the facing edges, middle to middle', () => {
		const list = connectors(DESKTOP_WORLD);
		expect(list[0].d).toBe('M 1100 280 H 1200 V 660 H 1300');
		expect(list[1].d).toBe('M 1100 1040 H 1200 V 660 H 1300');
		expect(list[2].d).toBe('M 5200 280 H 5100 V 660 H 5000');
		expect(list[4].d).toBe('M 2400 660 H 2500 V 660 H 2600');
		expect(list[5].d).toBe('M 3900 660 H 3800 V 660 H 3700');
	});
});

describe('round labels and champion', () => {
	it('puts one label above each desktop column', () => {
		expect(roundLabels(DESKTOP_WORLD)).toEqual([
			{ key: 'quarterfinals', x: 550, y: -120 },
			{ key: 'semifinals', x: 1850, y: 260 },
			{ key: 'championship', x: 3150, y: 260 },
			{ key: 'semifinals', x: 4450, y: 260 },
			{ key: 'quarterfinals', x: 5750, y: -120 }
		]);
	});

	it('anchors the champion under the final', () => {
		expect(championAnchor(DESKTOP_WORLD)).toEqual({ x: 3150, y: 1000 });
	});
});

describe('tokens', () => {
	it('mirrors the sizes of the --bracket-* tokens', () => {
		expect(DESKTOP_WORLD.width).toBe(token('--bracket-world-width'));
		expect(DESKTOP_WORLD.height).toBe(token('--bracket-world-height'));
		expect(NODE.width).toBe(token('--bracket-node-width'));
		expect(NODE.height).toBe(token('--bracket-node-height'));
		expect(TICK_SIZE).toBe(token('--bracket-tick-size'));
	});
});

describe('mobile tree rows', () => {
	it('has the quarterfinals, semifinals and championship rows in order', () => {
		expect(TREE_ROWS.map((row) => row.key)).toEqual([
			'quarterfinals',
			'semifinals',
			'championship'
		]);
	});

	it('places the cards of each row on the issue columns, East first', () => {
		expect(TREE_ROWS.map((row) => row.cards.map((card) => [card.id, card.column]))).toEqual([
			[
				['east-qf-1', '1 / 3'],
				['east-qf-2', '3 / 5'],
				['west-qf-1', '5 / 7'],
				['west-qf-2', '7 / 9']
			],
			[
				['east-sf', '2 / 4'],
				['west-sf', '6 / 8']
			],
			[['final', '3 / 7']]
		]);
	});

	it('holds every slot exactly once', () => {
		const ids = TREE_ROWS.flatMap((row) => row.cards.map((card) => card.id));
		expect(ids).toHaveLength(SLOT_IDS.length);
		expect([...ids].sort()).toEqual([...SLOT_IDS].sort());
	});

	it('keeps every column inside the 8 tracks', () => {
		for (const card of TREE_ROWS.flatMap((row) => row.cards)) {
			const [start, end] = card.column.split(' / ').map(Number) as [number, number];
			expect(start).toBeGreaterThanOrEqual(1);
			expect(end).toBeLessThanOrEqual(9);
			expect(start).toBeLessThan(end);
		}
	});
});
