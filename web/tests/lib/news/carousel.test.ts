// web/tests/lib/news/carousel.test.ts
//
// Tests for the carousel's current-card index.
//
// Tested:
// - Index 0 at the start, the nearest card mid-scroll, rounding at the half
// - Clamped to the last card past the end and to 0 before the start
// - At the end of the track the last card, with the 1280px numbers; 0 when the track cannot scroll
// - 0 when the step is 0 or negative or there are no cards
//
// What is covered:
// - Pure logic: happy path, edge cases and the degenerate inputs
//
// Run with: cd web && pnpm exec vitest run tests/lib/news/carousel.test.ts
//
// SEE: web/src/lib/news/carousel.ts
import { describe, expect, it } from 'vitest';

import { carouselIndex } from '../../../src/lib/news/carousel';

describe('carouselIndex', () => {
	it('is 0 at the start', () => {
		expect(carouselIndex(0, 320, 10)).toBe(0);
	});

	it('gives the nearest card mid-scroll and rounds at the half', () => {
		expect(carouselIndex(640, 320, 10)).toBe(2);
		expect(carouselIndex(150, 320, 10)).toBe(0);
		expect(carouselIndex(160, 320, 10)).toBe(1);
	});

	it('stays inside the cards', () => {
		expect(carouselIndex(99_999, 320, 10)).toBe(9);
		expect(carouselIndex(-50, 320, 10)).toBe(0);
	});

	it('is 0 with a step of 0 or no cards', () => {
		expect(carouselIndex(500, 0, 10)).toBe(0);
		expect(carouselIndex(500, -1, 10)).toBe(0);
		expect(carouselIndex(500, 320, 0)).toBe(0);
	});

	it('is the last card at the end of a desktop track', () => {
		expect(carouselIndex(1960, 316, 10, 1960)).toBe(9);
		expect(carouselIndex(1959.5, 316, 10, 1960)).toBe(9);
		expect(carouselIndex(1600, 316, 10, 1960)).toBe(5);
	});

	it('is 0 when the track cannot scroll', () => {
		expect(carouselIndex(0, 316, 10, 0)).toBe(0);
	});
});
