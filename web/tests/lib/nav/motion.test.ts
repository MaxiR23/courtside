// web/tests/lib/nav/motion.test.ts
//
// Tests for the nav motion.
//
// Tested:
// - navSheetSlide moves from translateY(100%) to none and reads the nav sheet duration token, with no delay
//
// What is covered:
// - The params; the play action itself is covered by the hero motion tests
//
// Run with: cd web && pnpm exec vitest run tests/lib/nav/motion.test.ts
//
// SEE: web/src/lib/nav/motion.ts
import { describe, expect, it } from 'vitest';

import { navSheetSlide } from '../../../src/lib/nav/motion';

describe('navSheetSlide', () => {
	it('slides up from below over the nav sheet duration', () => {
		expect(navSheetSlide.keyframes(() => '')).toEqual([
			{ transform: 'translateY(100%)' },
			{ transform: 'none' }
		]);
		expect(navSheetSlide.durationToken).toBe('--nav-sheet-duration');
		expect(navSheetSlide.delayToken).toBeUndefined();
	});
});
