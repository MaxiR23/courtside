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
// - A first and last name give the first initial of each, a suffix in the last name is ignored
// - A first and last name with one part, lowercase or empty
//
// What is covered:
// - Happy path, edge cases (one word, extra spaces, a suffix) and the empty case, for both forms
//
// Run with: cd web && pnpm exec vitest run tests/lib/format/initials.test.ts
//
// SEE: web/src/lib/format/initials.ts
import { describe, expect, it } from 'vitest';

import { initials } from '../../../src/lib/format/initials';

describe('initials from a display name', () => {
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

	it('reads a suffix as the last word of a display name', () => {
		expect(initials('Jimmy Butler III')).toBe('JI');
	});
});

describe('initials from a first and last name', () => {
	it('gives the initial of each part', () => {
		expect(initials({ firstName: 'Chet', lastName: 'Holmgren' })).toBe('CH');
	});

	it('ignores a suffix in the last name', () => {
		expect(initials({ firstName: 'Jimmy', lastName: 'Butler III' })).toBe('JB');
	});

	it('gives the first initial alone when the last name is empty', () => {
		expect(initials({ firstName: 'Nene', lastName: '' })).toBe('N');
	});

	it('uppercases lowercase parts', () => {
		expect(initials({ firstName: 'shai', lastName: 'gilgeous-alexander' })).toBe('SG');
	});

	it('gives an empty string for empty parts', () => {
		expect(initials({ firstName: '', lastName: '' })).toBe('');
	});
});
