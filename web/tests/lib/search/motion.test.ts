// web/tests/lib/search/motion.test.ts
//
// Tests for the search overlay motion.
//
// Tested:
// - The panel keyframes read --list-entrance-offset; the backdrop fades
// - playReverse resolves at once without animate and with reduced motion
// - Otherwise playReverse animates the keyframes reversed, forwards-filled, and resolves on finished
//
// What is covered:
// - Happy path, no-animate case and the reduced-motion case; animate is a mock
//
// Run with: cd web && pnpm exec vitest run tests/lib/search/motion.test.ts
//
// SEE: web/src/lib/search/motion.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { backdropFade, panelRise, playReverse } from '../../../src/lib/search/motion';

function fakeNode(finished: Promise<unknown> = Promise.resolve()) {
	const root = document.documentElement.style;
	root.setProperty('--list-entrance-offset', '18px');
	root.setProperty('--list-entrance-duration', '600ms');
	root.setProperty('--ease', 'linear');
	const node = document.createElement('div');
	const animate = vi.fn(() => ({ finished, cancel: vi.fn() }));
	Object.assign(node, { animate });
	document.body.append(node);
	return { node, animate };
}

afterEach(() => {
	vi.unstubAllGlobals();
	document.body.replaceChildren();
});

describe('keyframes', () => {
	it('rises by the list entrance offset', () => {
		const { node } = fakeNode();
		const read = (name: string) => getComputedStyle(node).getPropertyValue(name).trim();
		expect(panelRise.keyframes(read)).toEqual([
			{ opacity: 0, transform: 'translateY(18px)' },
			{ opacity: 1, transform: 'none' }
		]);
		expect(panelRise.durationToken).toBe('--list-entrance-duration');
	});

	it('fades the backdrop in', () => {
		expect(backdropFade.keyframes(() => '')).toEqual([{ opacity: 0 }, { opacity: 1 }]);
	});
});

describe('playReverse', () => {
	it('resolves at once without animate', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const node = document.createElement('div');
		await expect(playReverse(node, panelRise)).resolves.toBeUndefined();
	});

	it('resolves at once with reduced motion, without animating', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: true }));
		const { node, animate } = fakeNode(new Promise(() => {}));
		await expect(playReverse(node, panelRise)).resolves.toBeUndefined();
		expect(animate).not.toHaveBeenCalled();
	});

	it('animates the keyframes reversed and resolves when finished', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node, animate } = fakeNode();
		await playReverse(node, panelRise);
		const [keyframes, options] = (
			animate.mock.calls as unknown as [Keyframe[], KeyframeAnimationOptions][]
		)[0];
		expect(keyframes).toEqual([
			{ opacity: 1, transform: 'none' },
			{ opacity: 0, transform: 'translateY(18px)' }
		]);
		expect(options).toMatchObject({ duration: 600, fill: 'forwards' });
	});

	it('resolves when the animation is cancelled', async () => {
		vi.stubGlobal('matchMedia', () => ({ matches: false }));
		const { node } = fakeNode(Promise.reject(new DOMException('cancelled', 'AbortError')));
		await expect(playReverse(node, backdropFade)).resolves.toBeUndefined();
	});
});
