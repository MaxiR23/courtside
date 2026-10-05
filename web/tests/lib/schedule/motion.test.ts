// web/tests/lib/schedule/motion.test.ts
//
// Tests for the schedule list motion.
//
// Tested:
// - Each card enters 70ms after the previous one, from the token values
// - No entrance before the list has had a run, and none with reduced motion
// - The panel expand, content, tint and stat bar looks, durations and delays
// - The panel does not animate with reduced motion
//
// What is covered:
// - Happy path, edge case and the reduced-motion case
//
// Run with: cd web && pnpm exec vitest run tests/lib/schedule/motion.test.ts
//
// SEE: web/src/lib/schedule/motion.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { crossfade } from '../../../src/lib/hero/motion';
import {
	cardEntrance,
	panelContent,
	panelExpand,
	panelTint,
	statBar
} from '../../../src/lib/schedule/motion';

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

describe('panel motion', () => {
	function panelNode() {
		const root = document.documentElement.style;
		root.setProperty('--panel-expand-duration', '550ms');
		root.setProperty('--panel-content-duration', '450ms');
		root.setProperty('--panel-content-delay', '120ms');
		root.setProperty('--panel-content-offset', '-10px');
		root.setProperty('--panel-tint-duration', '350ms');
		root.setProperty('--stat-bar-duration', '900ms');
		root.setProperty('--stat-bar-delay', '200ms');
		root.setProperty('--ease', 'linear');
		const node = document.createElement('div');
		const animate = vi.fn(() => ({ cancel: vi.fn() }));
		Object.assign(node, { animate });
		document.body.append(node);
		return { node, animate };
	}

	function opens(factory: (open: boolean) => Parameters<typeof crossfade>[1]) {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node, animate } = panelNode();
		const action = crossfade(node, factory(false));
		action.update(factory(true));
		return animate.mock.calls[0] as unknown as [Keyframe[], KeyframeAnimationOptions];
	}

	it('expands the panel grid rows from 0fr to 1fr over the expand duration', () => {
		const [keyframes, options] = opens(panelExpand);
		expect(keyframes).toEqual([{ gridTemplateRows: '0fr' }, { gridTemplateRows: '1fr' }]);
		expect(options.duration).toBe(550);
		expect(options.delay).toBeUndefined();
	});

	it('fades the panel content in from the content offset after its delay', () => {
		const [keyframes, options] = opens(panelContent);
		expect(keyframes).toEqual([
			{ opacity: 0, transform: 'translateY(-10px)' },
			{ opacity: 1, transform: 'none' }
		]);
		expect(options.duration).toBe(450);
		expect(options.delay).toBe(120);
		expect(options.fill).toBe('backwards');
	});

	it('fades the open tint in over the tint duration', () => {
		const [keyframes, options] = opens(panelTint);
		expect(keyframes).toEqual([{ opacity: 0 }, { opacity: 1 }]);
		expect(options.duration).toBe(350);
	});

	it('grows a stat bar from zero after its delay', () => {
		const [keyframes, options] = opens(statBar);
		expect(keyframes).toEqual([{ transform: 'scaleX(0)' }, { transform: 'none' }]);
		expect(options.duration).toBe(900);
		expect(options.delay).toBe(200);
		expect(options.fill).toBe('backwards');
	});

	it('does not animate the panel with reduced motion', () => {
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		const { node, animate } = panelNode();
		const action = crossfade(node, panelExpand(false));
		action.update(panelExpand(true));
		expect(animate).not.toHaveBeenCalled();
	});
});
