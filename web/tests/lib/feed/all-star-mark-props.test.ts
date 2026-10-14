// web/tests/lib/feed/all-star-mark-props.test.ts
//
// Tests for the props that turn the All-Star marks of the core feeds into the tag and round line of a game and the tag of a player.
//
// Tested:
// - The stage tag and the Round Robin context, in English and in Spanish
// - The Championship context is translated and the mark is flagged as the championship
// - No mark for a null mark and for a feed without the key
// - The player tag "All-Star 2027", in English and in Spanish
// - No player tag for null and for undefined
//
// What is covered:
// - Pure logic on invented values; no clock, no network
//
// Run with: cd web && pnpm exec vitest run tests/lib/feed/all-star-mark-props.test.ts
//
// SEE: web/src/lib/feed/all-star-mark-props.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GameAllStar } from '../../../src/lib/contract/games';
import { allStarMark, allStarPlayerTag } from '../../../src/lib/feed/all-star-mark-props';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

const robin: GameAllStar = { roundLabel: 'Round Robin', championship: false };
const championship: GameAllStar = { roundLabel: 'Championship', championship: true };

describe('allStarMark', () => {
	it('writes the stage tag and the round as the context', () => {
		expect(allStarMark(robin)).toEqual({
			tag: 'All-Star',
			context: 'Round Robin',
			championship: false
		});
	});

	it('writes the Spanish stage tag and keeps the round as the feed writes it', () => {
		preferLanguages(['es-ES']);
		expect(allStarMark(robin)).toEqual({
			tag: 'All-Star',
			context: 'Round Robin',
			championship: false
		});
	});

	it('translates the Championship context and flags it', () => {
		expect(allStarMark(championship)).toEqual({
			tag: 'All-Star',
			context: 'Championship',
			championship: true
		});
		preferLanguages(['es-ES']);
		expect(allStarMark(championship)?.context).toBe('Campeonato');
	});

	it('gives no mark for a null mark and for a feed without the key', () => {
		expect(allStarMark(null)).toBeNull();
		expect(allStarMark(undefined)).toBeNull();
	});
});

describe('allStarPlayerTag', () => {
	it('writes the tag with the year in both languages', () => {
		expect(allStarPlayerTag(2027)).toBe('All-Star 2027');
		preferLanguages(['es-ES']);
		expect(allStarPlayerTag(2027)).toBe('All-Star 2027');
	});

	it('gives no tag for null and for undefined', () => {
		expect(allStarPlayerTag(null)).toBeNull();
		expect(allStarPlayerTag(undefined)).toBeNull();
	});
});
