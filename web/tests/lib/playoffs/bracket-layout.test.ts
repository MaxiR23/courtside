// web/tests/lib/playoffs/bracket-layout.test.ts
//
// Tests for the world geometry of the playoffs bracket.
//
// Tested:
// - The seven column x values and the row centers equal the design's, every card lies inside the 1400x650 world
// - 15 ids in SeriesId order and 14 connectors with their feeders
// - Connectors run between facing edges, West mirrored
// - seriesRect grows by the games gap and one row per game, and stays the card with none
// - step cycles with wrap-around and starts from null
// - The mobile groups follow the design's order and hold 15 ids
// - The sizes match the --playoffs-* tokens
//
// What is covered:
// - Happy path, mirroring, wrap-around and the token cross-check
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/bracket-layout.test.ts
//
// SEE: web/src/lib/playoffs/bracket-layout.ts
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import {
	CARD,
	championAt,
	COLUMN_STEP,
	COLUMN_WIDTH,
	connectors,
	GAME_ROW,
	GAMES_GAP,
	gamesAt,
	MOBILE_GROUPS,
	ROW_HEIGHT,
	SERIES_AT,
	SERIES_IDS,
	SERIES_ZOOM_MAX,
	seriesRect,
	step,
	WORLD
} from '../../../src/lib/playoffs/bracket-layout';

const tokensCss = readFileSync(join(process.cwd(), 'src/lib/styles/tokens.css'), 'utf8');
const token = (name: string): number => {
	const match = tokensCss.match(new RegExp(`${name}:\\s*([\\d.]+)(px)?;`));
	if (!match) throw new Error(`${name} is not a numeric token`);
	return Number(match[1]);
};

describe('series cards', () => {
	it('puts the seven columns at the design x values', () => {
		const columns = [
			['east-r1-1', 0],
			['east-r2-1', 204],
			['east-r3', 408],
			['finals', 612],
			['west-r3', 816],
			['west-r2-1', 1020],
			['west-r1-1', 1224]
		] as const;
		for (const [id, x] of columns) expect(SERIES_AT[id].x).toBe(x);
	});

	it('centers the rows at the design heights', () => {
		const center = (id: (typeof SERIES_IDS)[number]) => SERIES_AT[id].y + CARD.height / 2;
		expect(
			['east-r1-1', 'east-r1-2', 'east-r1-3', 'east-r1-4'].map((id) => center(id as never))
		).toEqual([105, 235, 365, 495]);
		expect([center('east-r2-1'), center('east-r2-2')]).toEqual([170, 430]);
		expect([center('east-r3'), center('finals'), center('west-r3')]).toEqual([300, 300, 300]);
		expect(center('west-r1-4')).toBe(495);
	});

	it('keeps every card inside the world', () => {
		for (const id of SERIES_IDS) {
			const at = SERIES_AT[id];
			expect(at.x).toBeGreaterThanOrEqual(0);
			expect(at.y).toBeGreaterThanOrEqual(0);
			expect(at.x + CARD.width).toBeLessThanOrEqual(WORLD.width);
			expect(at.y + CARD.height).toBeLessThanOrEqual(WORLD.height);
		}
	});

	it('lists the 15 ids in the feed order', () => {
		expect(SERIES_IDS).toHaveLength(15);
		expect(new Set(SERIES_IDS).size).toBe(15);
		expect(SERIES_IDS[0]).toBe('east-r1-1');
		expect(SERIES_IDS[7]).toBe('finals');
		expect(SERIES_IDS[14]).toBe('west-r1-4');
	});
});

describe('connectors', () => {
	const all = connectors();

	it('has 14 connectors, each series feeding once except the Finals', () => {
		expect(all).toHaveLength(14);
		expect(new Set(all.map((c) => c.from)).size).toBe(14);
		expect(all.filter((c) => c.to === 'finals').map((c) => c.from)).toEqual(['east-r3', 'west-r3']);
		expect(all.filter((c) => c.to === 'east-r2-1').map((c) => c.from)).toEqual([
			'east-r1-1',
			'east-r1-2'
		]);
		expect(all.filter((c) => c.to === 'west-r2-2').map((c) => c.from)).toEqual([
			'west-r1-3',
			'west-r1-4'
		]);
	});

	it('runs from the right edge of an East card to the left edge of the next', () => {
		const first = all.find((c) => c.from === 'east-r1-1')!;
		expect(first.d).toBe(
			`M ${COLUMN_WIDTH} 105 H ${(COLUMN_WIDTH + COLUMN_STEP) / 2} V 170 H ${COLUMN_STEP}`
		);
	});

	it('runs from the left edge of a West card to the right edge of the next', () => {
		const west = all.find((c) => c.from === 'west-r1-1')!;
		const x1 = 1224;
		const x2 = 1020 + COLUMN_WIDTH;
		expect(west.d).toBe(`M ${x1} 105 H ${(x1 + x2) / 2} V 170 H ${x2}`);
	});

	it('ends the conference finals on the facing sides of the Finals card', () => {
		expect(all.find((c) => c.from === 'east-r3')!.d).toBe('M 584 300 H 598 V 300 H 612');
		expect(all.find((c) => c.from === 'west-r3')!.d).toBe('M 816 300 H 802 V 300 H 788');
	});
});

describe('games list', () => {
	it('adds the gap and one row per game under the card', () => {
		const card = seriesRect('east-r1-1', 0);
		const grown = seriesRect('east-r1-1', 5);
		expect(card).toEqual({ x: 0, y: 72, width: 176, height: 66 });
		expect(grown.height).toBe(CARD.height + GAMES_GAP + 5 * GAME_ROW);
		expect(grown.y).toBe(card.y);
	});

	it('places the list right under the card', () => {
		expect(gamesAt('east-r1-1')).toEqual({ x: 0, y: 72 + CARD.height + GAMES_GAP });
	});

	it('anchors the Champion label above the Finals card, centered', () => {
		expect(championAt()).toEqual({ x: 612 + 88, y: 267 - 8 });
	});
});

describe('step', () => {
	it('goes to the next and previous series', () => {
		expect(step('east-r1-1', 1)).toBe('east-r1-2');
		expect(step('finals', -1)).toBe('east-r3');
	});

	it('wraps around at both ends', () => {
		expect(step('west-r1-4', 1)).toBe('east-r1-1');
		expect(step('east-r1-1', -1)).toBe('west-r1-4');
	});

	it('starts from the first series going forward and the last going back', () => {
		expect(step(null, 1)).toBe('east-r1-1');
		expect(step(null, -1)).toBe('west-r1-4');
	});
});

describe('mobile groups', () => {
	it('stacks the rounds in the design order with 15 ids in all', () => {
		expect(MOBILE_GROUPS.map((group) => group.length)).toEqual([4, 2, 1, 1, 1, 2, 4]);
		expect(MOBILE_GROUPS.map((group) => group[0])).toEqual([
			'east-r1-1',
			'east-r2-1',
			'east-r3',
			'finals',
			'west-r3',
			'west-r2-1',
			'west-r1-1'
		]);
		expect(new Set(MOBILE_GROUPS.flat()).size).toBe(15);
	});
});

describe('tokens', () => {
	it('mirrors the sizes of the --playoffs-* tokens', () => {
		expect(WORLD.width).toBe(token('--playoffs-world-width'));
		expect(WORLD.height).toBe(token('--playoffs-world-height'));
		expect(COLUMN_WIDTH).toBe(token('--playoffs-column-width'));
		expect(COLUMN_STEP).toBe(token('--playoffs-column-step'));
		expect(ROW_HEIGHT).toBe(token('--playoffs-row-height'));
		expect(SERIES_ZOOM_MAX).toBe(token('--playoffs-series-zoom-max'));
		expect(GAME_ROW).toBe(token('--playoffs-game-row-height'));
		expect(GAMES_GAP).toBe(token('--playoffs-games-gap'));
	});
});
