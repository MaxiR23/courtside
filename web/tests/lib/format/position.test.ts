// web/tests/lib/format/position.test.ts
//
// Tests for the name of a player position in the page language.
//
// Tested:
// - The seven known names in English (unchanged) and in Spanish
// - A hyphenated name whose parts are all known is the translated parts joined by a hyphen
// - An abbreviation, an unknown name, a hyphenated name with an unknown part and an empty string are returned as sent
//
// What is covered:
// - Pure logic on invented values; happy path, edges and errors
//
// Run with: cd web && pnpm exec vitest run tests/lib/format/position.test.ts
//
// SEE: web/src/lib/format/position.ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { positionName } from '../../../src/lib/format/position';
import { preferLanguages } from '../../prefer-languages';

afterEach(() => {
	vi.restoreAllMocks();
});

const NAMES = [
	'Guard',
	'Forward',
	'Center',
	'Point Guard',
	'Shooting Guard',
	'Small Forward',
	'Power Forward'
];

describe('positionName', () => {
	it('reads as the feed writes it in English', () => {
		expect(NAMES.map(positionName)).toEqual(NAMES);
		expect(positionName('Forward-Center')).toBe('Forward-Center');
	});

	it('translates the known names in Spanish', () => {
		preferLanguages(['es']);
		expect(NAMES.map(positionName)).toEqual([
			'Escolta',
			'Alero',
			'Pívot',
			'Base',
			'Escolta',
			'Alero',
			'Ala-pívot'
		]);
	});

	it('translates each part of a hyphenated name', () => {
		preferLanguages(['es']);
		expect(positionName('Forward-Center')).toBe('Alero-Pívot');
		expect(positionName('Guard-Forward')).toBe('Escolta-Alero');
	});

	it('returns an abbreviation, an unknown name and an empty string as sent', () => {
		preferLanguages(['es']);
		expect(positionName('G')).toBe('G');
		expect(positionName('F-C')).toBe('F-C');
		expect(positionName('Swingman')).toBe('Swingman');
		expect(positionName('Guard-Swingman')).toBe('Guard-Swingman');
		expect(positionName('')).toBe('');
	});
});
