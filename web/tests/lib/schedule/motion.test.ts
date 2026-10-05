// web/tests/lib/schedule/motion.test.ts
//
// Tests for the schedule list motion.
//
// Tested:
// - Each card enters 70ms after the previous one, from the token values
// - No entrance before the list has had a run, and none with reduced motion
//
// What is covered:
// - Happy path, edge case and the reduced-motion case
//
// Run with: cd web && pnpm exec vitest run tests/lib/schedule/motion.test.ts
//
// SEE: web/src/lib/schedule/motion.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { cardEntrance } from '../../../src/lib/schedule/motion';

function fakeNode() {
	const root = document.documentElement.style;
	root.setProperty('--list-entrance-offset', '18px');
	root.setProperty('--list-entrance-duration', '600ms');
	root.setProperty('--list-entrance-stagger', '70ms');
	root.setProperty('--ease', 'linear');
	const node = document.createElement('li');
	const animate = vi.fn(() => ({ cancel: vi.fn() }));
	Object.assign(node, { animate });
	document.body.append(node);
	return { node, animate };
}

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.replaceChildren();
});

describe('cardEntrance', () => {
	it('staggers each card 70ms after the previous one', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node, animate } = fakeNode();
		for (const index of [0, 1, 2]) cardEntrance(node, { index, run: 1 });
		const calls = animate.mock.calls as unknown as [Keyframe[], KeyframeAnimationOptions][];
		expect(calls.map(([, options]) => options.delay)).toEqual([0, 70, 140]);
		expect(calls[0][1].duration).toBe(600);
		expect(calls[0][0][0].opacity).toBe(0);
		expect(calls[0][0][0].transform).toBe('translateY(18px)');
	});

	it('does not play before the list has had an entrance run', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node, animate } = fakeNode();
		cardEntrance(node, { index: 0, run: 0 });
		expect(animate).not.toHaveBeenCalled();
	});

	it('does not play with reduced motion', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		const { node, animate } = fakeNode();
		cardEntrance(node, { index: 0, run: 1 });
		expect(animate).not.toHaveBeenCalled();
	});
});
