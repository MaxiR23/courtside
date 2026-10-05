// web/tests/lib/skeleton/motion.test.ts
//
// Tests for the skeleton shimmer motion.
//
// Tested:
// - The shimmer loops opacity from 1 to the token value and back, with the token duration
// - The shimmer does nothing with reduced motion
//
// What is covered:
// - Happy path and reduced motion
//
// Run with: cd web && pnpm exec vitest run tests/lib/skeleton/motion.test.ts
//
// SEE: web/src/lib/skeleton/motion.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { play } from '../../../src/lib/hero/motion';
import { shimmer } from '../../../src/lib/skeleton/motion';

function fakeNode() {
	const node = document.createElement('div');
	document.documentElement.style.setProperty('--skeleton-shimmer-duration', '1.6s');
	document.documentElement.style.setProperty('--skeleton-shimmer-opacity', '0.5');
	const animate = vi.fn(() => ({ cancel: vi.fn() }));
	Object.assign(node, { animate });
	document.body.append(node);
	return { node, animate };
}

function reducedMotion(reduced: boolean) {
	vi.stubGlobal('matchMedia', () => ({ matches: reduced }));
}

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.replaceChildren();
});

describe('shimmer', () => {
	it('loops the shimmer from full opacity to the shimmer opacity and back, with the token duration', () => {
		reducedMotion(false);
		const { node, animate } = fakeNode();
		play(node, shimmer);
		expect(animate).toHaveBeenCalledTimes(1);
		expect(animate).toHaveBeenCalledWith(
			[{ opacity: 1 }, { opacity: '0.5' }, { opacity: 1 }],
			expect.objectContaining({ duration: 1600, iterations: Infinity, easing: 'ease-in-out' })
		);
	});

	it('does not shimmer with reduced motion', () => {
		reducedMotion(true);
		const { node, animate } = fakeNode();
		play(node, shimmer);
		expect(animate).not.toHaveBeenCalled();
	});
});
