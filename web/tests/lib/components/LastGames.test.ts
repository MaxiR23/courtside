// web/tests/lib/components/LastGames.test.ts
//
// Tests for the LastGames component.
//
// Tested:
// - The result strip in the given order with win and loss classes
// - The team names link to the team page; the opponent stays plain text
// - Rows with result, date, opponent and score, in the given order
// - A team with fewer than five games and a team with none (empty line, English and Spanish)
// - Only the league side renders when a side is null
//
// What is covered:
// - Each state
//
// Run with: cd web && pnpm exec vitest run tests/lib/components/LastGames.test.ts
//
// SEE: web/src/lib/components/LastGames.svelte
import type { ResolvedPathname } from '$app/types';
import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { LastGamesSection } from '../../../src/lib/game/types';

import { preferLanguages } from '../../prefer-languages';
import LastGames from '../../../src/lib/components/LastGames.svelte';

const lastGames: LastGamesSection = {
	away: {
		code: 'GSW',
		name: 'Warriors',
		strip: [
			{ result: 'loss', label: 'L' },
			{ result: 'win', label: 'W' },
			{ result: 'win', label: 'W' }
		],
		rows: [
			{ result: 'win', resultLabel: 'W', date: 'Oct 5', opponent: 'vs DEN', score: '118–104' },
			{ result: 'win', resultLabel: 'W', date: 'Oct 3', opponent: '@ PHX', score: '110–99' },
			{ result: 'loss', resultLabel: 'L', date: 'Oct 1', opponent: 'vs SAC', score: '100–101' }
		]
	},
	home: { code: 'LAL', name: 'Lakers', strip: [], rows: [] }
};

const teamHref = (code: string) => `/team/${code.toLowerCase()}` as ResolvedPathname;

afterEach(() => {
	vi.restoreAllMocks();
});

describe('LastGames', () => {
	it('shows the team names', () => {
		const { container } = render(LastGames, { props: { lastGames, teamHref } });
		expect([...container.querySelectorAll('h3')].map((h) => h.textContent)).toEqual([
			'Warriors',
			'Lakers'
		]);
	});

	it('shows the strip squares in the given order with win and loss classes', () => {
		const { container } = render(LastGames, { props: { lastGames, teamHref } });
		const squares = [...container.querySelectorAll('.square')];
		expect(squares.map((s) => s.textContent)).toEqual(['L', 'W', 'W']);
		expect(squares.map((s) => s.classList.contains('win'))).toEqual([false, true, true]);
		expect(squares.map((s) => s.classList.contains('loss'))).toEqual([true, false, false]);
	});

	it('shows rows newest first with result, date, opponent and score', () => {
		const { container } = render(LastGames, { props: { lastGames, teamHref } });
		const rows = [...container.querySelectorAll('.row')].map((row) =>
			[...row.children].map((c) => c.textContent)
		);
		expect(rows).toEqual([
			['W', 'Oct 5', 'vs DEN', '118–104'],
			['W', 'Oct 3', '@ PHX', '110–99'],
			['L', 'Oct 1', 'vs SAC', '100–101']
		]);
	});

	it('shows a team with no games with its header, the empty line and no squares or rows', () => {
		const { container } = render(LastGames, { props: { lastGames, teamHref } });
		const teams = container.querySelectorAll('.team');
		expect(teams[1].querySelector('h3')?.textContent).toBe('Lakers');
		expect(teams[1].querySelectorAll('.square')).toHaveLength(0);
		expect(teams[1].querySelectorAll('.row')).toHaveLength(0);
		expect(teams[1].querySelector('.empty')?.textContent).toBe('No games played yet.');
		expect(teams[0].querySelector('.empty')).toBeNull();
	});

	it('shows the empty line in Spanish', () => {
		preferLanguages(['es-ES']);
		const { container } = render(LastGames, { props: { lastGames, teamHref } });
		expect(container.querySelectorAll('.team')[1].querySelector('.empty')?.textContent).toBe(
			'Aún no ha jugado ningún partido.'
		);
	});

	it('links the team names to the team page', () => {
		render(LastGames, { props: { lastGames, teamHref } });
		expect(screen.getByRole('link', { name: 'Warriors' }).getAttribute('href')).toBe('/team/gsw');
		expect(screen.getByRole('link', { name: 'Lakers' }).getAttribute('href')).toBe('/team/lal');
	});

	it('keeps the opponent as plain text', () => {
		render(LastGames, { props: { lastGames, teamHref } });
		expect(screen.getByText('vs DEN')).toBeTruthy();
		expect(screen.queryByRole('link', { name: /DEN|PHX|SAC/ })).toBeNull();
	});
});

describe('LastGames with a guest team', () => {
	it('renders only the league team', () => {
		const { container } = render(LastGames, {
			props: { lastGames: { away: null, home: lastGames.away }, teamHref }
		});
		expect([...container.querySelectorAll('h3')].map((h) => h.textContent)).toEqual(['Warriors']);
	});
});
