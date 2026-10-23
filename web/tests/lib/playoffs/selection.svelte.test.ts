// web/tests/lib/playoffs/selection.svelte.test.ts
//
// Tests for the playoffs bracket selection.
//
// Tested:
// - Defaults: nothing on the map while the Finals has no game, the Finals once it has one, nothing on the tree
// - A first tap selects; a second tap on a complete selected series opens it
// - An unfinished selected series stays selected on a second tap
// - An undecided series is not selectable and changes nothing
// - A tap on another series moves the pick, and a pick the feed lost falls back to the default
//
// What is covered:
// - The reactive module without mounting
//
// Run with: cd web && pnpm exec vitest run tests/lib/playoffs/selection.svelte.test.ts
//
// SEE: web/src/lib/playoffs/selection.svelte.ts
import { describe, expect, it } from 'vitest';

import type { SeriesId } from '../../../src/lib/contract/playoffs';
import { SeriesSelection } from '../../../src/lib/playoffs/selection.svelte';

const list = (finalsGames: number) => [
	{ id: 'east-r1-1' as SeriesId, games: [{}, {}] },
	{ id: 'finals' as SeriesId, games: Array.from({ length: finalsGames }, () => ({})) }
];
const card = (id: SeriesId, complete: boolean, decided: 'both' | 'one' | 'none' = 'both') => ({
	id,
	complete,
	decided
});

describe('SeriesSelection', () => {
	it('selects nothing on the map while the Finals has no game', () => {
		expect(new SeriesSelection().current(list(0), 'desktop')).toBeNull();
	});

	it('selects the Finals on the map once it has a game', () => {
		expect(new SeriesSelection().current(list(1), 'desktop')).toBe('finals');
	});

	it('selects nothing on the tree even with Finals games', () => {
		expect(new SeriesSelection().current(list(3), 'mobile')).toBeNull();
	});

	it('selects on a first tap', () => {
		const selection = new SeriesSelection();
		expect(selection.tap(card('east-r1-1', true), null)).toBe('select');
		expect(selection.current(list(0), 'mobile')).toBe('east-r1-1');
	});

	it('opens a complete selected series on a second tap', () => {
		const selection = new SeriesSelection();
		selection.tap(card('east-r1-1', true), null);
		expect(selection.tap(card('east-r1-1', true), 'east-r1-1')).toBe('open');
	});

	it('keeps an unfinished selected series selected on a second tap', () => {
		const selection = new SeriesSelection();
		selection.tap(card('east-r1-1', false), null);
		expect(selection.tap(card('east-r1-1', false), 'east-r1-1')).toBe('select');
		expect(selection.current(list(0), 'mobile')).toBe('east-r1-1');
	});

	it('opens the default Finals on its first tap when it is complete', () => {
		const selection = new SeriesSelection();
		const current = selection.current(list(4), 'desktop');
		expect(selection.tap(card('finals', true), current)).toBe('open');
	});

	it('ignores a series with an undecided side', () => {
		const selection = new SeriesSelection();
		expect(selection.tap(card('east-r2-1', false, 'one'), null)).toBe('none');
		expect(selection.tap(card('east-r2-2', false, 'none'), null)).toBe('none');
		expect(selection.picked).toBeNull();
	});

	it('moves the pick on a tap on another series', () => {
		const selection = new SeriesSelection();
		selection.tap(card('east-r1-1', true), null);
		expect(selection.tap(card('finals', false), 'east-r1-1')).toBe('select');
		expect(selection.current(list(0), 'desktop')).toBe('finals');
	});

	it('falls back to the default when the picked series is gone', () => {
		const selection = new SeriesSelection();
		selection.tap(card('east-r1-1', true), null);
		expect(selection.current([{ id: 'finals', games: [{}] }], 'desktop')).toBe('finals');
	});
});
