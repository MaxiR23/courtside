// web/tests/lib/all-star/selection.svelte.test.ts
//
// Tests for the All-Star game selection.
//
// Tested:
// - Nothing is picked at first: the current game is the feed's default game, and the tab is away
// - select picks a game and resets the box score tab to the first team
// - showBox switches the team tab
// - A feed update keeps a picked game that still exists and falls back to the default when it is gone
// - A view with no games and no default has no current game
//
// What is covered:
// - The reactive module without mounting
//
// Run with: cd web && pnpm exec vitest run tests/lib/all-star/selection.svelte.test.ts
//
// SEE: web/src/lib/all-star/selection.svelte.ts
import { describe, expect, it } from 'vitest';

import { GameSelection } from '../../../src/lib/all-star/selection.svelte';

const view = (ids: string[], defaultGame: string | null) => ({
	games: ids.map((id) => ({ id })),
	defaultGame
});

describe('GameSelection', () => {
	it('starts on the default game and the away tab', () => {
		const selection = new GameSelection();
		expect(selection.current(view(['a', 'b'], 'b'))).toBe('b');
		expect(selection.tab).toBe('away');
	});

	it('selects a game and resets the box score tab to away', () => {
		const selection = new GameSelection();
		selection.showBox('home');
		expect(selection.tab).toBe('home');
		selection.select('a');
		expect(selection.current(view(['a', 'b'], 'b'))).toBe('a');
		expect(selection.tab).toBe('away');
	});

	it('switches the team tab without touching the selected game', () => {
		const selection = new GameSelection();
		selection.select('a');
		selection.showBox('home');
		expect(selection.tab).toBe('home');
		expect(selection.current(view(['a', 'b'], 'b'))).toBe('a');
	});

	it('keeps the picked game when the feed updates and it still exists', () => {
		const selection = new GameSelection();
		selection.select('a');
		expect(selection.current(view(['a', 'b', 'c'], 'c'))).toBe('a');
	});

	it('falls back to the default game when the picked game is gone', () => {
		const selection = new GameSelection();
		selection.select('a');
		expect(selection.current(view(['b', 'c'], 'c'))).toBe('c');
	});

	it('has no current game without games and without a default', () => {
		const selection = new GameSelection();
		expect(selection.current(view([], null))).toBeNull();
	});
});
