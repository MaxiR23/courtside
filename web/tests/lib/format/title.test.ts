// web/tests/lib/format/title.test.ts
//
// Tests for the document title helper.
//
// Tested:
// - Joins one part and the site name
// - Joins two parts in order before the site name
// - Returns the site name alone with no part
// - Drops a null, undefined or blank part, so no doubled separator appears
// - Ends with the site name under a Spanish preference too
//
// What is covered:
// - Happy path, edge cases and the error case (blank parts) of a pure function
//
// Run with: cd web && pnpm exec vitest run tests/lib/format/title.test.ts
//
// SEE: web/src/lib/format/title.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { pageTitle } from '../../../src/lib/format/title';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

describe('pageTitle', () => {
	it('joins one part and the site name', () => {
		expect(pageTitle('Standings')).toBe('Standings · Courtside');
	});

	it('joins two parts in order before the site name', () => {
		expect(pageTitle('Games', 'February 6, 1999')).toBe('Games · February 6, 1999 · Courtside');
	});

	it('returns the site name alone with no part', () => {
		expect(pageTitle()).toBe('Courtside');
	});

	it('drops a null, undefined or blank part, so no doubled separator appears', () => {
		expect(pageTitle(null, undefined, '', '   ', 'Comets')).toBe('Comets · Courtside');
		expect(pageTitle(null)).toBe('Courtside');
	});

	it('ends with the site name under a Spanish preference too', () => {
		preferLanguages(['es']);
		expect(pageTitle('Clasificación')).toBe('Clasificación · Courtside');
	});
});
