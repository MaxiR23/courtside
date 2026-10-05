// web/tests/lib/hero/parallax.test.ts
//
// Tests for the hero parallax helpers.
//
// Tested:
// - pointerPosition maps a pointer to [-1, 1] on each axis
// - parallaxAllowed needs a fine hovering pointer and no reduced motion
//
// What is covered:
// - Happy path, edge cases (clamping, zero-size rect, no matchMedia)
//
// Run with: cd web && pnpm exec vitest run tests/lib/hero/parallax.test.ts
//
// SEE: web/src/lib/hero/parallax.ts
import { describe, expect, it } from 'vitest';

import { parallaxAllowed, pointerPosition } from '../../../src/lib/hero/parallax';

const rect = { left: 100, top: 50, width: 200, height: 100 };

function media(matching: string[]) {
	return (query: string) => ({ matches: matching.includes(query) });
}

const FINE = '(hover: hover) and (pointer: fine)';
const REDUCED = '(prefers-reduced-motion: reduce)';

describe('pointerPosition', () => {
	it('maps the center to zero and the corners to plus or minus one', () => {
		expect(pointerPosition(rect, 200, 100)).toEqual({ x: 0, y: 0 });
		expect(pointerPosition(rect, 100, 50)).toEqual({ x: -1, y: -1 });
		expect(pointerPosition(rect, 300, 150)).toEqual({ x: 1, y: 1 });
	});

	it('clamps a pointer outside the rect', () => {
		expect(pointerPosition(rect, 1000, -500)).toEqual({ x: 1, y: -1 });
	});

	it('returns zero for a zero-size rect', () => {
		expect(pointerPosition({ left: 0, top: 0, width: 0, height: 0 }, 10, 10)).toEqual({
			x: 0,
			y: 0
		});
	});
});

describe('parallaxAllowed', () => {
	it('allows parallax with a fine hovering pointer', () => {
		expect(parallaxAllowed(media([FINE]))).toBe(true);
	});

	it('skips parallax on a touch device', () => {
		expect(parallaxAllowed(media([]))).toBe(false);
	});

	it('skips parallax when reduced motion is requested', () => {
		expect(parallaxAllowed(media([FINE, REDUCED]))).toBe(false);
	});

	it('skips parallax when matchMedia is unavailable', () => {
		expect(parallaxAllowed(undefined)).toBe(false);
	});
});
