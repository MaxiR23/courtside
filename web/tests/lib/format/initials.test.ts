// web/tests/lib/format/initials.test.ts
//
// Tests for the initials rule of player photos and guest tiles.
//
// Tested:
// - Two words give the first initial of each
// - Three words give the first and the last
// - One word gives its initial alone
// - Extra spaces are ignored
// - Lowercase input is uppercased
// - An empty string gives an empty string
//
// What is covered:
// - Happy path, edge cases (one word, extra spaces) and the empty case
//
// Run with: cd web && pnpm exec vitest run tests/lib/format/initials.test.ts
//
// SEE: web/src/lib/format/initials.ts
import { describe, expect, it } from 'vitest';

import { initials } from '../../../src/lib/format/initials';

describe('initials', () => {
	it('gives the initial of each of two words', () => {
		expect(initials('Chet Holmgren')).toBe('CH');
	});

	it('gives the first and the last initials of three words', () => {
		expect(initials('Harbor City Mariners')).toBe('HM');
	});

	it('gives the initial alone of one word', () => {
		expect(initials('Mariners')).toBe('M');
	});

	it('ignores extra spaces', () => {
		expect(initials('  Harbor   Mariners  ')).toBe('HM');
	});

	it('uppercases lowercase input', () => {
		expect(initials('harbor mariners')).toBe('HM');
	});

	it('gives an empty string for an empty string', () => {
		expect(initials('')).toBe('');
		expect(initials('   ')).toBe('');
	});
});
