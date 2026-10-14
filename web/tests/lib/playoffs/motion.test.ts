// web/tests/lib/playoffs/motion.test.ts
//
// Tests for the playoffs bracket motion.
//
// Tested:
// - gamesFade fades the opacity and reads the games fade duration and delay tokens
// - sheetSlide moves from translateY(100%) to none and reads the sheet duration token
//
// What is covered:
// - The params; the play action itself is covered by the hero motion tests
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/motion.test.ts
//
// SEE: web/src/lib/playoffs/motion.ts
import { describe, expect, it } from 'vitest';

import { gamesFade, sheetSlide } from '../../../src/lib/playoffs/motion';

describe('gamesFade', () => {
	it('fades the opacity in over the games fade, after its delay', () => {
		expect(gamesFade.keyframes(() => '')).toEqual([{ opacity: 0 }, { opacity: 1 }]);
		expect(gamesFade.durationToken).toBe('--playoffs-games-fade');
		expect(gamesFade.delayToken).toBe('--playoffs-games-fade-delay');
	});
});

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
