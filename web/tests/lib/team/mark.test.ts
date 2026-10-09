// web/tests/lib/team/mark.test.ts
//
// Tests for the view of a game side or an opponent and its tile and label rules.
//
// Tested:
// - teamTile gives the code, the initials of the city and name for a guest without a code, and the initials of the name alone without a city
// - teamLabel gives the code, else the name, else nothing
// - teamMark treats a missing guest key as a league team and keeps the fields
//
// What is covered:
// - Happy path, the guest without a code and edge cases (no city, no name)
//
// Run with: cd web && pnpm exec vitest run tests/lib/team/mark.test.ts
//
// SEE: web/src/lib/team/mark.ts
import { describe, expect, it } from 'vitest';

import { teamLabel, teamMark, teamTile } from '../../../src/lib/team/mark';

const league = { code: 'DEN', name: 'Nuggets', city: 'Denver', guest: false };
const mariners = { code: null, name: 'Mariners', city: 'Harbor City', guest: true };

describe('teamTile', () => {
	it('gives the code of a team that has one', () => {
		expect(teamTile(league)).toBe('DEN');
		expect(teamTile({ ...mariners, code: 'HCM' })).toBe('HCM');
	});

	it('gives the initials of the city and the name for a guest without a code', () => {
		expect(teamTile(mariners)).toBe('HM');
	});

	it('gives the initials of the name alone for a guest without a city', () => {
		expect(teamTile({ ...mariners, city: null })).toBe('M');
		expect(teamTile({ ...mariners, name: 'Harbor Mariners', city: null })).toBe('HM');
	});

	it('gives the initials of the city for a guest without a name', () => {
		expect(teamTile({ ...mariners, name: null })).toBe('HC');
	});
});

describe('teamLabel', () => {
	it('gives the code of a team that has one', () => {
		expect(teamLabel(league)).toBe('DEN');
	});

	it('gives the name of a guest without a code', () => {
		expect(teamLabel(mariners)).toBe('Mariners');
	});

	it('gives nothing without a code or a name', () => {
		expect(teamLabel({ ...mariners, name: null })).toBe('');
	});
});

describe('teamMark', () => {
	it('treats a missing guest key as a league team', () => {
		expect(teamMark({ code: 'DEN', name: null, city: null }).guest).toBe(false);
	});

	it('keeps the fields and the guest flag', () => {
		expect(teamMark(mariners)).toEqual(mariners);
	});
});
