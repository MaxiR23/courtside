// web/tests/lib/playoffs/motion.test.ts
//
// Tests for the playoffs bracket motion.
//
// Tested:
// - sheetSlide moves from translateY(100%) to none and reads the sheet duration token
//
// What is covered:
// - The params; the play action itself is covered by the hero motion tests
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/motion.test.ts
//
// SEE: web/src/lib/playoffs/motion.ts
import { describe, expect, it } from 'vitest';

import { sheetSlide } from '../../../src/lib/playoffs/motion';

describe('sheetSlide', () => {
	it('slides up from below over the sheet duration', () => {
		expect(sheetSlide.keyframes(() => '')).toEqual([
			{ transform: 'translateY(100%)' },
			{ transform: 'none' }
		]);
		expect(sheetSlide.durationToken).toBe('--playoffs-sheet-duration');
		expect(sheetSlide.delayToken).toBeUndefined();
	});
});
