// web/tests/lib/playoffs/links.test.ts
//
// Tests for the playoffs route link builders.
//
// Tested:
// - seriesHref: the current season has no season parameter; a past season keeps it
// - bracketHref: the bracket section of /playoffs, with the season kept on a past one
//
// What is covered:
// - Pure logic: the two builders
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/links.test.ts
//
// SEE: web/src/lib/playoffs/links.ts
import { describe, expect, it } from 'vitest';

import { bracketHref, seriesHref } from '../../../src/lib/playoffs/links';

describe('seriesHref', () => {
	it('has no season for the current season', () => {
		expect(seriesHref('east-r1-1', null)).toBe('/playoffs/series?id=east-r1-1');
	});

	it('keeps the season of a past one', () => {
		expect(seriesHref('finals', 2005)).toBe('/playoffs/series?id=finals&season=2005');
	});
});

describe('bracketHref', () => {
	it('points at the bracket section for the current season', () => {
		expect(bracketHref(null)).toBe('/playoffs#bracket');
	});

	it('keeps the season of a past one', () => {
		expect(bracketHref(2005)).toBe('/playoffs?season=2005#bracket');
	});
});
