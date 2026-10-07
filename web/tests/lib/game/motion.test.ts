// web/tests/lib/game/motion.test.ts
//
// Tests for the game detail motion.
//
// Tested:
// - A detail stat bar grows from 0 to its share over the duration token
// - It animates from the previous share to the new one when the value changes
// - It does not animate when the share is unchanged
// - It does not animate with reduced motion
//
// What is covered:
// - Happy path, edge case and the reduced-motion case
//
// Run with: cd web && pnpm exec vitest run tests/lib/game/motion.test.ts
//
// SEE: web/src/lib/game/motion.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { barWidth } from '../../../src/lib/game/motion';

function fakeNode() {
	const root = document.documentElement.style;
	root.setProperty('--detail-stat-bar-duration', '0.6s');
	root.setProperty('--ease', 'linear');
	const node = document.createElement('span');
	const cancel = vi.fn();
	const animate = vi.fn(() => ({ cancel }));
	Object.assign(node, { animate });
	document.body.append(node);
	return { node, animate, cancel };
}

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.replaceChildren();
});

type Call = [Keyframe[], KeyframeAnimationOptions];

describe('barWidth', () => {
	it('grows a detail stat bar from 0 to its share over the duration token', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node, animate } = fakeNode();
		barWidth(node, 0.5);
		const [frames, options] = animate.mock.calls[0] as unknown as Call;
		expect(frames).toEqual([{ width: '0%' }, { width: '50%' }]);
		expect(options.duration).toBe(600);
		expect(options.easing).toBe('linear');
	});

	it('animates from the previous share to the new one when the value changes', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node, animate, cancel } = fakeNode();
		const action = barWidth(node, 0.5);
		action.update(0.8);
		expect(cancel).toHaveBeenCalledTimes(1);
		const [frames] = animate.mock.calls[1] as unknown as Call;
		expect(frames).toEqual([{ width: '50%' }, { width: '80%' }]);
		action.destroy();
		expect(cancel).toHaveBeenCalledTimes(2);
	});

	it('does not animate when the share is unchanged', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node, animate } = fakeNode();
		const action = barWidth(node, 0.5);
		action.update(0.5);
		expect(animate).toHaveBeenCalledTimes(1);
	});

	it('does not animate with reduced motion', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		const { node, animate } = fakeNode();
		const action = barWidth(node, 0.5);
		action.update(0.8);
		action.destroy();
		expect(animate).not.toHaveBeenCalled();
	});
});
