// web/tests/lib/bracket/geometry.test.ts
//
// Tests for the connector geometry shared by the brackets.
//
// Tested:
// - elbowPath runs from the right edge middle to the left edge middle
// - Mirrored, it runs from the left edge to the right edge
// - With the Cup's node size it returns the Cup's path
//
// What is covered:
// - Happy path and the mirrored case
//
// Run with: cd web && pnpm exec vitest run tests/lib/bracket/geometry.test.ts
//
// SEE: web/src/lib/bracket/geometry.ts
import { describe, expect, it } from 'vitest';

import { elbowPath } from '../../../src/lib/bracket/geometry';

const NODE = { width: 100, height: 40 };

describe('elbowPath', () => {
	it('runs from the right edge middle to the left edge middle', () => {
		expect(elbowPath({ x: 0, y: 0 }, { x: 200, y: 100 }, NODE, false)).toBe(
			'M 100 20 H 150 V 120 H 200'
		);
	});

	it('runs from the left edge to the right edge when mirrored', () => {
		expect(elbowPath({ x: 400, y: 100 }, { x: 200, y: 0 }, NODE, true)).toBe(
			'M 400 120 H 350 V 20 H 300'
		);
	});

	it('returns the same path as the Cup bracket for its node size', () => {
		const cup = { width: 1100, height: 560 };
		expect(elbowPath({ x: 0, y: 0 }, { x: 1300, y: 380 }, cup, false)).toBe(
			'M 1100 280 H 1200 V 660 H 1300'
		);
	});
});
