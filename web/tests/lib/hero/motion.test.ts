// web/tests/lib/hero/motion.test.ts
//
// Tests for the hero motion helpers.
//
// Tested:
// - parseMs converts seconds and milliseconds and ignores anything else
// - play animates with token values, and does nothing with reduced motion
// - crossfade animates only when the active state changes
//
// What is covered:
// - Happy path, reduced motion, missing animation support
//
// Run with: cd web && pnpm exec vitest run tests/lib/hero/motion.test.ts
//
// SEE: web/src/lib/hero/motion.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { crossfade, entrance, parseMs, play } from '../../../src/lib/hero/motion';

function fakeNode() {
	const node = document.createElement('div');
	document.documentElement.style.setProperty('--hero-entrance-duration', '1s');
	document.documentElement.style.setProperty('--hero-delay-tag', '100ms');
	document.documentElement.style.setProperty('--hero-entrance-offset', '28px');
	document.documentElement.style.setProperty('--hero-crossfade-duration', '0.5s');
	document.documentElement.style.setProperty('--ease', 'linear');
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

describe('parseMs', () => {
	it('converts seconds and milliseconds', () => {
		expect(parseMs('1s')).toBe(1000);
		expect(parseMs('0.5s')).toBe(500);
		expect(parseMs(' 250ms ')).toBe(250);
	});

	it('returns 0 for an unparseable value', () => {
		expect(parseMs('')).toBe(0);
		expect(parseMs('fast')).toBe(0);
	});
});

describe('play', () => {
	it('animates with the duration, delay and offset read from tokens', () => {
		reducedMotion(false);
		const { node, animate } = fakeNode();
		play(node, entrance('--hero-delay-tag'));
		expect(animate).toHaveBeenCalledTimes(1);
		const [keyframes, options] = animate.mock.calls[0] as unknown as [
			Keyframe[],
			KeyframeAnimationOptions
		];
		expect(keyframes[0].transform).toBe('translateY(28px)');
		expect(options.duration).toBe(1000);
		expect(options.delay).toBe(100);
	});

	it('multiplies the delay token by delaySteps for a stagger', () => {
		reducedMotion(false);
		const { node, animate } = fakeNode();
		play(node, { ...entrance('--hero-delay-tag'), delaySteps: 3 });
		const [, options] = animate.mock.calls[0] as unknown as [Keyframe[], KeyframeAnimationOptions];
		expect(options.delay).toBe(300);
	});

	it('does not animate with reduced motion', () => {
		reducedMotion(true);
		const { node, animate } = fakeNode();
		play(node, entrance('--hero-delay-tag'));
		expect(animate).not.toHaveBeenCalled();
	});

	it('does nothing when animations are not supported', () => {
		reducedMotion(false);
		const node = document.createElement('div');
		expect(() => play(node, entrance('--hero-delay-tag'))).not.toThrow();
	});
});

describe('crossfade', () => {
	const params = (active: boolean) => ({
		active,
		hidden: () => ({ opacity: 0 }),
		shown: { opacity: 1 },
		durationToken: '--hero-crossfade-duration'
	});

	it('animates from shown to hidden when it becomes inactive', () => {
		reducedMotion(false);
		const { node, animate } = fakeNode();
		const action = crossfade(node, params(true));
		action.update(params(false));
		expect(animate).toHaveBeenCalledTimes(1);
		const [keyframes, options] = animate.mock.calls[0] as unknown as [
			Keyframe[],
			KeyframeAnimationOptions
		];
		expect(keyframes).toEqual([{ opacity: 1 }, { opacity: 0 }]);
		expect(options.duration).toBe(500);
	});

	it('does not animate when the active state is unchanged', () => {
		reducedMotion(false);
		const { node, animate } = fakeNode();
		const action = crossfade(node, params(true));
		action.update(params(true));
		expect(animate).not.toHaveBeenCalled();
	});

	it('does not animate with reduced motion', () => {
		reducedMotion(true);
		const { node, animate } = fakeNode();
		const action = crossfade(node, params(true));
		action.update(params(false));
		expect(animate).not.toHaveBeenCalled();
	});
});
