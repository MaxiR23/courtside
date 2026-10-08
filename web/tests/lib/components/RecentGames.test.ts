// web/tests/lib/components/RecentGames.test.ts
//
// Tests for the RecentGames component.
//
// Tested:
// - Each row's result (win class), date, opponent, score, tag, points and line
// - A linked row is an anchor to the game; an unlinked row has no link and no link class
//
// What is covered:
// - Each case, from props
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/RecentGames.test.ts
//
// SEE: web/src/lib/components/RecentGames.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import RecentGames from '../../../src/lib/components/RecentGames.svelte';
import type { RecentGameRow } from '../../../src/lib/player/types';

const gameHref = (id: string) => `/game/${id}` as ResolvedPathname;

const rows: RecentGameRow[] = [
	{
		gameId: 'g-5',
		linked: true,
		result: 'win',
		resultLabel: 'W',
		date: 'Apr 29',
		opponent: '@ MEM',
		score: '118–104',
		tag: 'West R1 · G4',
		points: '31',
		line: '8 REB · 6 AST'
	},
	{
		gameId: 'g-4',
		linked: false,
		result: 'loss',
		resultLabel: 'L',
		date: 'Apr 26',
		opponent: 'vs MEM',
		score: '101–108',
		tag: null,
		points: '24',
		line: '5 REB · 7 AST'
	}
];

describe('RecentGames', () => {
	it('shows each row with its result, date, opponent, score, tag, points and line', () => {
		const { container } = render(RecentGames, { props: { rows, gameHref } });
		const items = [...container.querySelectorAll('.row')];
		expect(items).toHaveLength(2);
		expect(items[0]?.querySelector('.result')?.classList.contains('win')).toBe(true);
		expect(items[1]?.querySelector('.result')?.classList.contains('win')).toBe(false);
		for (const text of [
			'W',
			'Apr 29',
			'@ MEM',
			'118–104',
			'West R1 · G4',
			'31',
			'8 REB · 6 AST',
			'L',
			'vs MEM',
			'101–108',
			'24',
			'5 REB · 7 AST'
		]) {
			expect(screen.getByText(text)).toBeTruthy();
		}
	});

	it('links only the linked row to its game', () => {
		const { container } = render(RecentGames, { props: { rows, gameHref } });
		const links = screen.getAllByRole('link');
		expect(links).toHaveLength(1);
		expect(links[0]?.getAttribute('href')).toBe('/game/g-5');
		const plain = container.querySelectorAll('li')[1]?.querySelector('.row');
		expect(plain?.tagName).toBe('DIV');
		expect(plain?.classList.contains('link')).toBe(false);
	});
});
