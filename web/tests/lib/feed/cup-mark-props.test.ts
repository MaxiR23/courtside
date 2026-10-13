// web/tests/lib/feed/cup-mark-props.test.ts
//
// Tests for the props that turn the Cup marks of the core feeds into the tag of a game and the line of a team.
//
// Tested:
// - The tag for each of the four stages, in English and in Spanish
// - No tag for a null mark and for a feed without the key
// - The team line: the group title and the Cup record, in English and in Spanish
// - No team line for a null mark and for a feed without the key
// - The group title helper moved from the Cup page props
//
// What is covered:
// - Pure logic on invented values; no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/cup-mark-props.test.ts
//
// SEE: web/src/lib/feed/cup-mark-props.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { CupRound } from '../../../src/lib/contract/cup';
import { cupTag, cupTeamLine, groupTitle } from '../../../src/lib/feed/cup-mark-props';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

describe('cupTag', () => {
	it('writes the tag for a group play game', () => {
		expect(cupTag({ stage: 'group' })).toBe('NBA Cup · Group play');
	});

	it('writes the tag for each knockout stage', () => {
		expect(cupTag({ stage: 'quarterfinals' })).toBe('NBA Cup · Quarterfinal');
		expect(cupTag({ stage: 'semifinals' })).toBe('NBA Cup · Semifinal');
		expect(cupTag({ stage: 'championship' })).toBe('NBA Cup · Championship');
	});

	it('writes no tag for a game that is not a Cup game', () => {
		expect(cupTag(null)).toBeNull();
	});

	it('writes no tag for a feed without the mark', () => {
		expect(cupTag(undefined)).toBeNull();
	});

	it('writes the Spanish tag for each stage', () => {
		preferLanguages(['es-ES']);
		const stages: [CupRound, string][] = [
			['group', 'Copa NBA · Fase de grupos'],
			['quarterfinals', 'Copa NBA · Cuartos de final'],
			['semifinals', 'Copa NBA · Semifinal'],
			['championship', 'Copa NBA · Final']
		];
		for (const [stage, text] of stages) expect(cupTag({ stage })).toBe(text);
	});
});

describe('cupTeamLine', () => {
	it('writes the team line from the group parts and the Cup record', () => {
		expect(cupTeamLine({ group: { conference: 'east', letter: 'A' }, wins: 3, losses: 1 })).toEqual(
			{ group: 'East Group A', record: '3-1' }
		);
		expect(cupTeamLine({ group: { conference: 'west', letter: 'C' }, wins: 0, losses: 0 })).toEqual(
			{ group: 'West Group C', record: '0-0' }
		);
	});

	it('writes the Spanish group name', () => {
		preferLanguages(['es-ES']);
		expect(cupTeamLine({ group: { conference: 'east', letter: 'A' }, wins: 3, losses: 1 })).toEqual(
			{ group: 'Grupo A del Este', record: '3-1' }
		);
	});

	it('writes no team line without the mark', () => {
		expect(cupTeamLine(null)).toBeNull();
		expect(cupTeamLine(undefined)).toBeNull();
	});
});

describe('groupTitle', () => {
	it('keeps writing the group title as the Cup page does', () => {
		expect(groupTitle({ conference: 'east', letter: 'A' })).toBe('East Group A');
	});
});
