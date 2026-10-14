// web/tests/lib/all-star/motion.test.ts
//
// Tests for the live dot's pulse.
//
// Tested:
// - The keyframes go from full opacity and scale to the token values and back
// - The duration is the live dot token, the pulse loops forever and eases in and out
//
// What is covered:
// - The params object with a fake token reader; no animation runs
//
// Run with: cd web && pnpm exec vitest run tests/lib/all-star/motion.test.ts
//
// SEE: web/src/lib/all-star/motion.ts
import { describe, expect, it } from 'vitest';

import { livePulse } from '../../../src/lib/all-star/motion';

describe('livePulse', () => {
	it('pulses from 1 to the token opacity and scale and back', () => {
		const tokens: Record<string, string> = {
			'--allstar-live-dot-opacity': '0.35',
			'--allstar-live-dot-scale': '0.7'
		};
		expect(livePulse.keyframes((name) => tokens[name])).toEqual([
			{ opacity: 1, transform: 'scale(1)' },
			{ opacity: '0.35', transform: 'scale(0.7)' },
			{ opacity: 1, transform: 'scale(1)' }
		]);
	});

	it('loops with the dot duration token', () => {
		expect(livePulse.durationToken).toBe('--allstar-live-dot-duration');
		expect(livePulse.iterations).toBe(Infinity);
		expect(livePulse.easing).toBe('ease-in-out');
	});
});
